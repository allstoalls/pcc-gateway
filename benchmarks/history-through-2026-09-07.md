# Benchmark experiment history through 2026-09-07

> Historical record. "Latest", "current", defaults, pending gates and local
> artifacts in the text below refer to those experiments, not today's source
> or installation. Use [the benchmark guide](README.md), current scripts and
> matching receipts. Raw measurements and their original explanations are
> preserved so later findings can be compared without rewriting the evidence.

The repository contains `benchmark_native.py`, `benchmark_asyncio.py` and
`benchmarks/compare.py`. The runner compiles the native workload with both host
pcc and pcc1, then compares them with CPython `asyncio.TaskGroup`:

```bash
uv run python benchmarks/compare.py --output benchmarks/results/latest.json
# Select a specific qualified native compiler when needed:
uv run python benchmarks/compare.py --pcc1 /path/to/pcc1 \
  --output benchmarks/results/candidate.json
```

All arms perform two child waits, join their results, and validate identical
sorted JSON bytes. This measures the handler workload, excluding HTTP sockets
and network transport. It uses one carrier/event loop, concurrency 1/10/100,
waits of 0/100 ms, two warmup batches and five repeats with rotating arm order.
Zero-delay runs process at least 5,000 requests each; 100 ms runs use ten
batches. Compilation, process startup and warmups are outside request timing.

The JSON report retains every latency sample, median/min/max QPS, p50/p95,
Darwin process peak RSS and CPU totals, source hashes and compiler identities.
Process memory and CPU include startup and warmups. Incomplete runs are marked
as such and cannot supply performance conclusions.

## Interpreting concurrency and batch overhead

Concurrency is the batch width: start C request tasks, wait for all of them,
then start the next batch. Every request creates two child tasks, even at C1.
Both implementations use one execution thread; these are not CPU-thread or
HTTP-connection counts. The runner varies batch size and maximum in-flight
requests together, so it does not isolate continuous-load concurrency scaling.

The [batch-cost diagnostic](results/2026-09-07-batch-costs.json) fits
`batch time = fixed cost + C × incremental request cost` to the C10/C100
zero-wait measurements. Approximate fitted values are:

| Implementation | Fixed cost per batch (µs) | Incremental cost per request (µs) |
|---|---:|---:|
| pcc | 6.7 | 20.3 |
| pcc1 | 8.6 | 20.6 |
| asyncio | 96.7 | 10.6 |

These are two-point fits, not separately timed phases. A counting-only probe
of the unchanged asyncio workload observes **7 selector.select(0) calls per
batch** at C1, C10 and C100: respectively 7, 0.7 and 0.07 calls per request.
The local Python 3.15 event loop polls the selector before each ready-callback
batch. This supports fixed loop/polling cost amortization, but does not assign
all fitted fixed time to I/O. No throughput result comes from the instrumented
runs. Reproduce the analysis and counts with:

```bash
uv run python benchmarks/batch_costs.py \
  --comparison benchmarks/results/2026-09-07-field-owners-three-way.json \
  --output benchmarks/results/my-batch-costs.json
```

pcc1 throughput rises from 31,741.6 to 48,457.6 QPS as C increases; its
relative advantage disappears because asyncio amortizes much more fixed work.
A comparison that replenishes completed requests to maintain a fixed number
in flight is still needed before generalizing to steady service throughput.
The current evidence points to reducing pcc's per-request frame/task/ownership
work, rather than interpreting the C1 win as a cheaper complete task lifecycle.

## Latest diagnostic pcc/pcc1/asyncio result (2026-09-07)

The [latest table](results/2026-09-07-runtime-o2-three-way.md) and
[raw samples](results/2026-09-07-runtime-o2-three-way.json) use newly built
pcc1 `2b08f3a7aac1` and the same source/runtime for host pcc. Zero-wait/C100
medians are **57,469.9 / 57,662.8 / 85,437.0 QPS**, with peak RSS
**7.97 / 7.95 / 27.83 MiB**. All 90 runs / 241,650 requests passed.
The first-entry, completed-result and direct-generator flags are enabled in
both native arms. These artifacts used LLVM O2 on five runtime modules.
The automatic O2 build policy has since been withdrawn: the numbers describe
this diagnostic, not the current default or a fully LLVM-free runtime build.
Withdrawn frame experiments do not affect generated applications.
Stage1 and startup/compile/run smoke checks passed for the recorded artifacts.
Shared-installation promotion and new-source Stage2/Stage3 qualification
remain pending; the shared PATH installation is still the historical toolchain.

The new pcc1 passed eight field/suspended-iterator sources across GC0–4
(40 executions, 77.43 s) and all three native HTTP/dashboard/failure-cleanup
examples (261.24 s). Normal runtime native checks pass, along with 76
optimizer/provenance/cache checks and the 290-test gateway default suite.

The preceding [field-owner comparison](results/2026-09-07-field-owners-three-way.md)
used pcc1 `0ff76d8bf139`, before runtime module optimization, and remains
available with its own source/runtime identity and application gates.

The preceding [factory comparison](results/2026-09-07-factory-three-way.md)
used pcc1 `53978d6bf7db` before the latest task/ownership changes; its raw
samples remain available as historical evidence.

## Earlier optimized three-way run (2026-09-07)

The [complete table](results/2026-09-07-optimized-three-way.md) and
[raw report](results/2026-09-07-optimized-three-way.json) contain the latest
host-pcc/pcc1/asyncio comparison: 90 runs, 241,650 measured requests, all
validated. Both compilers rebuilt the current workload against the same
optimized application runtime, SHA-256 `514ed8bf2d4b731e5be980c85f31fdd4a621605974e6629270ba77750102f829`.
The compiler source is the fixed gateway v5 snapshot; pcc1's binary SHA-256
starts `c5ae2affdb02`. Its Stage1 build receipt describes the compiler's own
original runtime; the separate `application_runtime` entry identifies the
optimized runtime linked into both benchmark programs. Both programs link
only libSystem on this Mac. Bulk frame initialization is disabled.

At concurrency 100, zero-wait median QPS is 22,092.9 / 22,241.0 / 42,647.1
(host pcc / pcc1 / asyncio); p50/p95 and CPU/RSS are retained in the reports.
The pcc1 gap is 1.92× in this run. At 100 ms, medians are 940.7 / 944.0 / 953.0
QPS. This is a new same-run comparison, not a ratio between separate dates.

The one-minute load average was 17.8 at the start and 19.8 at the end;
per-run load averages and QPS ranges are recorded. System load was variable,
so absolute QPS should not be compared with the earlier 38,239-QPS runtime
A/B as evidence of a regression. The original data is preserved below.

To select a fixed source tree and matching optimized application archive:

```bash
PCC_HOST_PYTHON="$PWD/.venv/bin/python" PCC_SELF_BACKEND_JOBS=2 \
uv run python benchmarks/compare.py --pcc1 /path/to/qualified/pcc1 \
  --compiler-source /path/to/frozen/pcc \
  --runtime-archive /path/to/libpy_runtime_pcc_py.a \
  --output benchmarks/results/my-optimized-three-way.json
```

The selected pcc1 must match the source tree. If it is an environment wrapper,
ensure it respects the supplied source/runtime variables. Optional
`--pcc1-binary` and `--pcc1-receipt` record and validate the native compiler's
Stage1 identity. The runner takes the core performance lock, checks source
and archive hashes before/after measurement, and rejects existing output names.
Application binaries and compilation logs go under `benchmarks/build/<output-stem>/`.

## Runtime optimization A/B (2026-09-07)

Both runtime A/B arms use the same LLVM target-machine object emitter; this
compares additional optimization, not self versus LLVM object generation.
The control uses target-machine emission after
bounded IR cleanup, without LLVM's full module optimization. Optimizing only
`py_obj`, `py_list`, and `py_gen`, with identical source and all other archive
members unchanged, improves **49,193.0 → 55,135.9 QPS (+12.1%)**;
instructions/request fall **7.1%**. Adding `py_gc_backend` and
`freestanding_gc_index_table` improves **55,401.7 → 59,032.4 (+6.6%)** in a
separate A/B. Both reports have 42 valid runs. The latter's same-run asyncio
is **88,549.8 QPS**. Do not combine percentages from separate runs into a new
measured result. [Three-module report](results/2026-09-07-runtime-ir-o2-ab.json)
and [five-module report](results/2026-09-07-runtime-ir-o2-five-ab.json).

The core's `scripts/reoptimize_runtime_ir.py` retains input/output hashes,
LLVM version and verifies exactly which archive members changed. It emits
objects through llvmlite and preserves Python-source provenance. Libc and
allocator implementations are excluded pending libcall-recursion checks.
These are explicit LLVM oracle results. The automatic default-build O2 policy
was withdrawn; self-path improvements must reproduce the useful transformations
through pcc's own selected passes and pass separate native-pcc1 qualification.

The self frontend's default tier selects only `mem2reg,sroa`; having more
translated passes in the repository does not mean this path runs them.
The optimized application's [profile](results/2026-09-07-runtime-o2-profile.folded)
still spends 852/2302 leaf samples (37.0%) in the five leading object-validation
and reference-count helpers. This does not establish how much is caused by
code generation versus operation counts. Per-request task/object/frame/ownership
counts and uninstrumented A/B timing are the next attribution boundary.

The [self capability probe](results/2026-09-07-self-runtime-capability.json)
confirms native pcc1 can lower all five sources and emit their ARM64/PCO code
without host Python or cc. A generator linked with those PCOs returns 42;
the remaining runtime members are prebuilt and pcc's linker still runs on
CPython. Explicit `simplifycfg` and `inline` currently attempt llvmlite imports
and fail the dependency guard. This is an emission capability check, not O2
parity or the completed dependency contract in `AGENTS.md`. Reproduce with
core's `scripts/probe_pcc1_self_runtime.py --pcc1 NATIVE_BINARY --source-root
PCC_SOURCE --runtime-archive RUNTIME_ARCHIVE --output-dir NEW_DIRECTORY`.

An explicit [application-only Clang -O2 control](results/2026-09-07-llvm-o2-application-ab.json)
is flat: **51,647.0 / 51,338.8 QPS**. The earlier self/LLVM comparison used
default application emission, so its 0.45% difference does not bound runtime
optimization potential. `benchmarks/clang_o2` supplies the explicit optimizer
oracle; `runtime_ab.py` records and verifies compiler-wrapper identities.

The [bidirectional frame-owner trial](results/2026-09-07-frame-owner-roundtrip-ab.json)
also has no accepted throughput gain: **50,166.3 → 50,270.1 (+0.21%)**, with
overlapping ranges and unchanged user CPU. Its application flag/path was
withdrawn. Runtime contracts and exact experimental sources remain available
for diagnosis; current application code retains the established frame path.

The [save-only ownership-transfer experiment](results/2026-09-07-frame-owner-transfer-ab.json)
also establishes **no throughput gain**: 48,508.0 → 47,949.2 QPS with
overlapping ranges, instructions/request -0.91%, and unchanged user CPU.
All 42 runs passed. Restoration still retained every frame value, leaving
the duplicate frame/local lifetime largely intact. This is diagnostic
evidence for completing transfer in both directions, not an accepted result.

The [bulk frame-save experiment](results/2026-09-07-bulk-frame-save-ab.json)
is **rejected**: batching existing slot stores reduces zero-wait/C100 QPS
from **48,279.4 to 46,711.8 (-3.25%)**, with instructions/request increasing
**1.08%**. All 42 runs passed workload checks, but the added address-array and
dispatch work did not reduce the reference protocol. Application activation
was withdrawn. Reproduction requires the experimental compiler source at core
`34c3d139`, its matching runtime, and the recorded per-arm environment; current
code ignores the old `PCC_BULK_GENERATOR_FRAME_SAVE` switch.

The [self/LLVM application diagnostic](results/2026-09-07-self-llvm-application-ab.json)
holds the fixed source, runtime, workload and flags constant. Seven repeats
give **51,056.2 / 51,288.2 / 89,852.4 QPS** (self / LLVM / asyncio), just
**0.45%** between the native backends. Both use 19.5 us process user CPU per
measured request. All 42 runs passed. This does not establish a meaningful
speed improvement: the generated continuation/frame/ownership workload
remains the measured target. The runtime itself is unchanged; its Python
members were already emitted with llvmlite's target machine.

Reproduce this diagnostic with `runtime_ab.py --control-backend self
--candidate-backend llvm`, one `--compiler-source`, the same archive in
`--control-runtime` and `--candidate-runtime`, `--summary --asyncio
--requests 20000 --repeats 7`, and the three flags in the main reproduction
command. The LLVM arm is an explicit oracle and is separate from the default
self-backend pcc/pcc1 comparison.

The [field-owner repair A/B](results/2026-09-07-field-owners-ab.json) measures
the complete workload after fixing retained field/iterator references.
Zero-wait/C100 QPS changes **53,489.8 → 50,870.8 (-4.9%)**; peak RSS drops
**141.31 → 17.48 MiB**, versus asyncio **88,804.3 QPS / 27.95 MiB**.
All 42 runs passed. This is a correctness repair with a measured throughput
cost; it does not close the asyncio gap. The new native
[profile](results/2026-09-07-field-owners-profile.json) and
[folded stacks](results/2026-09-07-field-owners-profile.folded) contain 2,303
on-CPU samples, with 403 passing through `py_list_set` and 2,098 through
`py_gen_next`. These inclusive counts overlap and are diagnostic, not QPS.

The checked-in `benchmarks/lifetime.py` derives its probe from the unchanged
handler functions and repeats them in one process. The unsafe live-object
counter is isolated in `benchmarks/heap_observer.py` so it does not change
the workload module's compilation mode. With three invocations of 5,000
measured requests plus warmups, retained counts are
**28 → 78,084 → 156,140 → 234,196**
[before](results/2026-09-07-field-owners-lifetime-control.json), and
**28 → 32 → 36 → 40**
[after](results/2026-09-07-field-owners-lifetime.json).
The small residual remains under investigation; this is not a zero-leak claim.

```bash
PCC_GENERATOR_FIRST_ENTRY_INIT=1 PCC_FAST_COMPLETED_CONTINUATIONS=1 \
PCC_DIRECT_GENERATOR_TASKS=1 uv run python benchmarks/lifetime.py \
  --compiler-source /path/to/frozen/pcc \
  --runtime-archive /path/to/libpy_runtime_pcc_py.a \
  --output benchmarks/results/my-lifetime.json
```

`runtime_ab.py` accepts `--control-compiler-source` and
`--candidate-compiler-source` for compiler ownership repairs, alongside the
existing runtime and workload controls. Both source trees are hashed before
and after measurement. Per-arm environment switches are retained in reports.

The [direct generator A/B](results/2026-09-07-direct-generator-ab.json)
removes the extra typed continuation object, stack descriptor and slot array
around each generator task. Seven-repeat zero-wait/C100 QPS improves
**50,862.8 → 52,908.8 (+4.0%)**, instructions/request fall **3.5%**, and peak
RSS falls **171.20 → 141.31 MiB**. Same-run asyncio is **88,979.1 QPS**.
This is opt-in via `PCC_DIRECT_GENERATOR_TASKS=1`. Both arms predate the
subsequently discovered field-iteration retention bug; these are historical
allocation measurements, not evidence of stable service memory usage.

The [completed-result handoff A/B](results/2026-09-07-completed-handoff-ab.json)
measures the next compiler/runtime slice: seven-repeat zero-wait/C100 QPS
improves **45,764.6 → 50,280.9 (+9.9%)**, process instructions/request fall
**6.9%**, and same-run asyncio is **91,584.1 QPS**. All 42 runs validate counts
and latency bounds; the 100 ms row is essentially unchanged. The
`PCC_FAST_COMPLETED_CONTINUATIONS=1` path preserves ordinary generator and
pending-exception behavior, and is opt-in pending fresh pcc1 qualification.

The [continuation-factory A/B](results/2026-09-07-continuation-factory-ab.json)
keeps the public TaskScope API and the complete handler workload. A fixed
compiler/runtime compiles frozen control and candidate package trees. Across
seven rotating repeats, zero-wait/C100 median QPS rises from **42,473.8 to
47,228.3 (+11.2%)**, with process instructions per measured request down
**10.9%**. Same-run asyncio is **91,354.7 QPS**. All 42 runs validate counts and
latencies. The candidate's normal fork/close paths return completed
continuations without full local-variable frames; waiting cleanup remains
deferred. Native pcc1 application qualification subsequently passed; see the current three-way result above.

The [handler-layer diagnostic](results/2026-09-07-handler-layers.json), produced
by `benchmarks/layers.py`, isolates the larger remaining cost. Five rotated
repeats at zero wait/C100 give **39,266.7 QPS** for TaskScope, **62,125.3** with
the request's structured child joins/cleanup written directly, and **86,322.4**
for asyncio. Native instructions/request fall from 339,683 to 213,667 when
the scope wrappers are expanded. Five host-model tests check payload and
failure cancellation/draining for these diagnostic variants.

The JSON-only ablation reaches 141,280.9 QPS but removes child tasks/waits;
it is a diagnostic floor, not an application result. The goal is to recover
scope-wrapper overhead while keeping the public TaskScope API and full
workload, not to replace the benchmark with an ablation.

```bash
uv run python benchmarks/layers.py \
  --runtime-archive /path/to/libpy_runtime_pcc_py.a \
  --output benchmarks/results/my-handler-layers.json
```

The [first-entry compiler A/B](results/2026-09-07-first-entry-idle-ab.json)
completed after other CPU-heavy programs were stopped: 42 runs / 441,000
requests, seven rotating repeats and the same fixed compiler/runtime in both
native arms. Skipping known-None frame reads on first entry raises zero-wait
C100 QPS from **37,943.8 to 39,368.2 (+3.8%)**; same-run asyncio is **86,549.5**.
At 100 ms, the medians are **966.2 / 966.4 / 973.8**. This remains a host-pcc
application result; fresh pcc1 qualification is pending and activation is
currently opt-in via `PCC_GENERATOR_FIRST_ENTRY_INIT=1`.

Raw latency samples validated every request. Process CPU/instructions include
final array formatting, which is expensive in the native JSON implementation;
they are not request-only CPU counters. The earlier summary-mode attempt
failed validation because compiled min/max returned zero for a dynamic float
list. It is retained as incomplete evidence, alongside the first attempt's
missing source-root marker. These attempts do not supply accepted results.

The [optimized pcc1 application profile](results/2026-09-07-optimized-pcc1-profile.json)
and [folded stacks](results/2026-09-07-optimized-pcc1-profile.folded) contain
2,488 on-CPU samples: 2,249 include `py_gen_next`, 610 include request resume,
and 412 have the granule object-start check as their leaf. Inclusive counts
overlap. This profiles execution of the compiled benchmark, not compilation
by pcc1. The remaining investigation targets generated resumable calls and
their frame/reference work.

The core's historical million-task benchmark is a scheduler-capacity test:
its C driver creates tasks with `py_None`, polls ready tasks and marks them
complete. It does not execute generated Python handlers, TaskScope or JSON.
Its tasks/s and ready-queue `resume` timings are not gateway request QPS.

Two runtime changes have measured gains. Each row below is a separate A/B
comparison using one host pcc compiler, the same workload, concurrency 100,
GC 0 and five alternating repeats. Zero-wait runs execute 5,000 requests;
100 ms runs execute 1,000. The second comparison starts with the first
optimization already enabled.

| Runtime change | Zero-wait QPS, before → after | Gain | 100 ms QPS, before → after |
|---|---:|---:|---:|
| Skip nonblocking I/O polling when there are no I/O waiters | 8,758.9 → 36,556.9 | 4.17× | 909.6 → 965.3 |
| Skip redundant retain/release for an unchanged GC 0 reference slot | 36,739.3 → 38,239.2 | +4.1% | 963.7 → 965.0 |

With both changes, the second A/B's candidate has a **38,239.2 QPS median**
(38,033.8–38,993.0 across five runs), with **1.227/1.527 ms p50/p95** at
zero wait. At 100 ms, its p50/p95 is **101.846/102.446 ms**. These are
handler timings; this is not an HTTP socket throughput test.

The empty-poll regression test checks the syscall directly: 100 empty polls
previously caused 101 `kevent` calls, and now cause zero. Native on-CPU
profiling after this change attributes 63.3% of 2,499 samples to GC/ownership
work, which guided the reference-store change. The latter preserves the
reference-consuming `store_root_take` operation and GC 1–4 barriers.
The 4.17× figure is a wall-time throughput gain, not a measured CPU reduction.

Raw evidence: [empty-poll A/B](results/2026-09-07-empty-io-poll-ab.json),
[runtime attribution](results/2026-09-07-empty-io-poll-attribution.json),
and [reference-store A/B](results/2026-09-07-self-store-ab.json).
The first control includes a 3,931.5 QPS outlier; all runs are retained.
The core changes are included in
[pcc checkpoint `77cdf411`](https://github.com/allstoalls/pcc/commit/77cdf4119b6ebca31061ba7457863eed195d6e55).

**A throughput win over asyncio at concurrency 100 has not been established.**
These earlier runtime A/B measurements use host pcc; the latest three-way run
above measures both compilers with the optimized runtime. The qualification
candidate completed Stage1 and Stage2; Stage3/fixed-point and promotion to
the shared installation are still pending. The installed v84 baseline should
not be assumed to support all the current gateway examples.

A bulk-frame diagnostic compared experimental bulk generator-frame initialization
with its disabled control and a same-run asyncio witness. It used frozen
compiler sources, 20,000 requests per run, concurrency 100, zero wait and five
rotating repeats. Final latency-array formatting was suppressed in all arms.

| Diagnostic arm | Median QPS | Min–max QPS | Instructions/request | User CPU/request |
|---|---:|---:|---:|---:|
| host pcc, bulk frame initialization disabled | 11,770.5 | 10,020.4–13,316.5 | 353,997 | 43 µs |
| host pcc, bulk frame initialization enabled | 12,458.3 | 10,576.5–13,163.8 | 340,787 | 43 µs |
| CPython 3.15.0rc1 asyncio | 17,466.9 | 14,835.4–21,169.6 | 177,947 | 30 µs |

The machine was heavily loaded during this diagnostic (observed one-minute
load average about 114); these absolute QPS values must not be compared with
the earlier tables. Instructions and CPU are whole-process totals divided by
measured requests, including startup and warmups. The experiment reduced
instructions about 3.7%, but did not establish a CPU-time improvement and its
QPS ranges overlap. **Bulk frame initialization remains disabled by default**;
it is not counted as an accepted optimization. See the
[bulk-frame diagnostic](results/2026-09-07-frame-init-frozen-counters.json)
and [result index](results/README.md), including failed and noisy
experiments. Remaining work is tracked in
[pcc issue #188](https://github.com/allstoalls/pcc/issues/188).

### Three-way baseline (2026-09-06, before optimization)

Apple M2 Max, macOS 26.5.1, CPython **3.15.0rc1**. Both native artifacts use
self backend, libpython off, GC 0 and the same pcc-Python runtime. The pcc1 arm
uses the freshly built gateway qualification candidate (SHA-256 starts
`c5ae2affdb02`), not the installed v84 baseline. Its full source/runtime receipt
identity is retained in the raw report. Both compilers passed the local HTTP
and dashboard execution gates. The native scope failure/cancellation canary
also passed under this pcc1.

Median handler QPS across five runs:

| Child wait (ms) | Concurrency | host pcc | pcc1 | CPython asyncio |
|---:|---:|---:|---:|---:|
| 0 | 1 | 7,014.1 | 6,956.4 | 8,741.6 |
| 0 | 10 | 8,587.5 | 8,558.8 | 47,753.5 |
| 0 | 100 | 8,671.8 | 8,844.1 | 85,873.9 |
| 100 | 1 | 10.0 | 10.0 | 9.9 |
| 100 | 10 | 98.6 | 98.7 | 98.7 |
| 100 | 100 | 909.2 | 908.5 | 973.9 |

At 100 ms / 100 concurrency, p50/p95 latency was **106.119/107.579 ms**
(host pcc), **106.072/107.438 ms** (pcc1), and **102.148/102.746 ms**
(asyncio). Median process peak RSS was **13.66 / 13.62 / 27.59 MiB** respectively.
At zero wait / 100 concurrency, peak RSS was **46.81 / 46.75 / 27.91 MiB**;
that scenario executes 5,000 requests per run, versus 1,000 in the 100 ms case.

pcc and pcc1 produce similar runtime throughput. Relative to asyncio, pcc1 is
about **6.7% lower** on the 100 ms / 100 concurrency workload and about
**9.7× slower** on the zero-wait workload at the same concurrency. These
measurements establish the baseline for the active
[throughput optimization](https://github.com/allstoalls/pcc/issues/188).
The five-repeat ranges expose warmup/system variability; the first host-pcc
zero-wait/serial run was notably slower than subsequent runs.

All **90 runs / 241,650 measured requests** validated their JSON output and
sample counts. See the [complete table](results/2026-09-06-macos-arm64.md)
and [raw samples and provenance](results/2026-09-06-macos-arm64.json)
for QPS ranges, latency percentiles, process CPU and memory. Native examples
exercise the HTTP codec separately; these QPS figures exclude HTTP parsing,
sockets and network I/O.

### Reproduce runtime A/B and profiles

To compare runtime changes, build two archives against a compatible, fixed
compiler source tree using the core runtime build tools, then run:

```bash
uv run python benchmarks/runtime_ab.py \
  --compiler-source /path/to/frozen/pcc \
  --control-runtime /path/to/control/libpy_runtime_pcc_py.a \
  --candidate-runtime /path/to/candidate/libpy_runtime_pcc_py.a \
  --asyncio --output benchmarks/results/my-runtime-ab.json
```

Use a new output name for each run. The runner records archive, executable and
source hashes, rejects source/archive changes during the run, and takes the
core performance lock. Historical absolute paths in reports identify local
artifacts; they are not installation prerequisites. Compiler and runtime ABI
must match: mixing an old archive with a newer compiler invalidated one
recorded attempt before any requests ran.

Add `--summary --requests 20000 --delays 0` for the latest counter-diagnostic
workload. For bulk-frame A/B, use the same compatible archive in both arms and
add `--control-env PCC_DISABLE_BULK_GENERATOR_FRAME_INIT=1` and
`--candidate-env PCC_DISABLE_BULK_GENERATOR_FRAME_INIT=0`.

The profiling wrapper reuses the core native flamegraph and Python 3.15
`profiling.sampling`/Tachyon tools:

```bash
uv run python benchmarks/profile.py native \
  --binary benchmarks/build/latest/host-pcc --rounds 2000 \
  --output benchmarks/build/my-native-profile
uv run python benchmarks/profile.py asyncio \
  --python ../pcc/.venv/bin/python-tachyon --rounds 2000 \
  --output benchmarks/build/my-asyncio-profile
```

Native profiling requires macOS; the Tachyon interpreter requires the core's
debugger-entitled Python setup. Profiles diagnose hotspots and are kept apart
from unprofiled performance comparisons. pcc1 does not yet implement Python's
`profiling.sampling` interface.
