# pcc-gateway

A virtual-thread HTTP/1.1 gateway kernel and a typed declarative web framework
written in pcc-Python for the [pcc](https://github.com/allstoalls/pcc)
compiler: channel buffers with backpressure, an HTTP/1 codec, routing, reverse
proxy policy, lifecycle/process control, a native DNS transport and a TLS
provider ABI backed by OpenSSL, all on pcc's own virtual threads with no
libpython at run time.

It is an ordinary pcc package: an application does `from pcc_gateway.web import
App, ...` and `pcc1` compiles the framework into the program together with the
application code. The optional native TLS provider is built separately.

## Layout

- `pcc_gateway/` – the gateway kernel (`buffer`, `channel`, `http1`, `routing`,
  `proxy`, `proxy_http1`, `lifecycle`, `control`, `dns`, `dns_native`, `tls`,
  `server`, `config`, `models`).
- `pcc_gateway/web/` – the declarative application framework (`App`,
  `Request`, `Response`, `BodyStream`, route decorators, proxy dispatch).
- `pcc_gateway/include/pcc_tls_provider_v1.h`, `pcc_gateway/native/` – the
  `pcc-native-tls-v1` provider ABI and its OpenSSL implementation (`make` in
  `pcc_gateway/native`, OpenSSL >= 3).
- `local_http_app.py` – a product-shaped local HTTP/1 application (request
  codec, router, framework dispatch, response encoder) that pcc1 compiles.
- `pcc_gateway/structured.py`, `dashboard_app.py` – a task scope and dashboard
  fan-out example, checked by host tests and native execution canaries.
- `tests/` – unit tests and pcc1 canaries; `tests/fixtures/gateway/` the pcc1
  gate programs.
- `docs/pcc-vthread-gateway.md` – design note; `docs/gateway-research/` –
  references.

The process-control primitives the gateway uses (`pcc_gateway_control_*`) are a
generic runtime substrate and stay in the core runtime
(`pcc/py_runtime/py/freestanding_gateway_control.py`).

## Use it

Use the shared, verified compiler at **`~/.local/bin/pcc1`** through PATH,
also used by `pcc-gui`. Versioned installations live under
`~/.local/share/pcc/toolchains/`. Validate a candidate before atomically
switching the shared entry, and retain the previous version for rollback.
See [the core installation contract](https://github.com/allstoalls/pcc#one-installed-compiler-for-multiple-projects).
The initial shared installation is the v84 Stage1/Stage2 baseline with an
installed execution canary. It is not 0.1.8; that newer candidate remains under
qualification, and new application features may require it. A local core build
is not automatically the installed compiler.

```bash
command -v pcc1                     # ~/.local/bin/pcc1
```

Keep this installation separate from application checkouts and core
`build/bootstrap/` outputs. Rebuilding one project must not replace the
compiler another project uses.

After cloning, run from the checkout root. The compiler resolves the adjacent
`pcc_gateway/` package directly; `PCC_PACKAGE_SITE` is not needed here.

```bash
pcc1 local_http_app.py -o local_http_app
./local_http_app
```

Without environment overrides, `pcc1` defaults to `--backend self`,
`--python-libpython off` and `--ir-scaffold on`; ordinary applications need
not repeat these flags.

`ir-scaffold=on` enables native compilation support for the IR-building APIs
used by pcc itself. It is enabled by default; ordinary applications do not
need to configure it.

`PCC_PACKAGE_SITE` only controls dependency locations. If the application is
outside this checkout, add it to pcc's colon-separated package-site list:

```bash
PCC_PACKAGE_SITE=/path/to/pcc-gateway pcc1 /path/to/app.py -o app
```

Install this package through the same environment-aware entry as NumPy or
pcc-gui; manual copying into site-packages is not the normal workflow:

```bash
pcc1 env info --json
pcc1 -m pip install /path/to/pcc-gateway
```

Without `VIRTUAL_ENV`, the default site is
`~/.local/share/pcc/environments/<compatibility-tag>/site-packages`. With an
active virtual environment, all packages use its pcc overlay instead. Install
and compile in the same environment; `pcc1 env info` reports the actual site.
The next qualified compiler defaults to Python 3.15 and records it as
compatibility metadata. Native package paths use pcc's ABI and platform rather
than the Python version, so future target upgrades need no manual path change.
Legacy `py311` sites remain untouched; use the selected compiler's install
command to populate its new default environment.
The first-install command for the compiler itself is documented in the
[core README](https://github.com/allstoalls/pcc#first-native-installation-after-cloning-macos-arm64).
Local-source installation and native execution are separate 0.1.8 qualification
gates; the older v84 baseline does not imply every current app is runnable.

`libpython=off` alone does not establish a build without `cc`. That claim
requires checking runtime construction and the actual assembly/link path as
well as the executable's dynamic dependencies.

## Development environment

Clone `pcc` beside `pcc-gateway`. The uv dependency points at `../pcc`, so host
compilation and tests use that explicit core checkout. Python is pinned to
**3.15.0rc1**, matching the core repository; dependency versions are recorded in
`uv.lock`.

```bash
uv sync --locked
uv run python --version
uv run pcc --backend self local_http_app.py -o local_http_app
uv run pcc1 dashboard_app.py -o dashboard_app
```

`uv run pcc` uses the host compiler. `uv run pcc1` resolves the native compiler
through PATH. Neither command requires `PCC_PACKAGE_SITE` for these examples.

## Tests

```bash
uv run pytest -q \
  tests/test_gateway_structured_concurrency.py \
  tests/test_gateway_http1_codec.py \
  tests/test_gateway_local_streaming.py \
  tests/test_gateway_server.py
```

The default suite has **285 passing tests**. Native integration
tests are excluded by the default marker. Run the documented example gates with
`uv run pytest -q -x -m integration tests/test_native_examples.py`;
`PCC_TEST_PCC1=/path/to/pcc1` selects a candidate wrapper.
The local HTTP and dashboard examples must separately print `PCC1_GATEWAY_HTTP1_LOCAL_OK` and
`PCC1_DASHBOARD_STRUCTURED_OK`. Exit code 0 alone is insufficient.

## Structured concurrency

`TaskScope` adopts handles from `virtual_thread.spawn(...)`, joins in fork
order, cancels and drains later siblings after a failure, and cleans up
unjoined children in `finally`. Rejected forks also retire the already-spawned
handle. Use each scope from one parent virtual thread.

`run_until_complete(thread)` drives one root task from outside the scheduler.
It preserves `virtual_thread.run()` as a stepping API, waits briefly when idle,
and propagates task failures. Child operations use `sleep_current()` to park.
The dashboard combines two concurrent fetches into sorted JSON and checks a
200 and a 404 through the HTTP/1 codec and framework dispatch.

## Reproducible performance comparison

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

### Latest optimization results (2026-09-07)

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

Raw evidence: [empty-poll A/B](benchmarks/results/2026-09-07-empty-io-poll-ab.json),
[runtime attribution](benchmarks/results/2026-09-07-empty-io-poll-attribution.json),
and [reference-store A/B](benchmarks/results/2026-09-07-self-store-ab.json).
The first control includes a 3,931.5 QPS outlier; all runs are retained.
The core changes are included in
[pcc checkpoint `77cdf411`](https://github.com/allstoalls/pcc/commit/77cdf4119b6ebca31061ba7457863eed195d6e55).

**A throughput win over asyncio has not been established.** The optimized
runtime A/B above uses host pcc; a fresh optimized host-pcc/pcc1/asyncio matrix
is still required. The complete three-way baseline below remains the measured
pcc1 comparison. The qualification candidate completed Stage1 and Stage2;
Stage3/fixed-point and shared-installation promotion are still pending.

The latest diagnostic compared experimental bulk generator-frame initialization
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
[latest diagnostic](benchmarks/results/2026-09-07-frame-init-frozen-counters.json)
and [result index](benchmarks/results/README.md), including failed and noisy
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
sample counts. See the [complete table](benchmarks/results/2026-09-06-macos-arm64.md)
and [raw samples and provenance](benchmarks/results/2026-09-06-macos-arm64.json)
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
  --binary benchmarks/build/host-pcc --rounds 2000 \
  --output benchmarks/build/my-native-profile
uv run python benchmarks/profile.py asyncio \
  --python ../pcc/.venv/bin/python-tachyon --rounds 2000 \
  --output benchmarks/build/my-asyncio-profile
```

Native profiling requires macOS; the Tachyon interpreter requires the core's
debugger-entitled Python setup. Profiles diagnose hotspots and are kept apart
from unprofiled performance comparisons. pcc1 does not yet implement Python's
`profiling.sampling` interface.
