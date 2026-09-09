# Standalone memory-tier repair: a measured gain, still behind asyncio

The two-module diagnostic improves zero-wait/C100 handler throughput from
24,531.3 to 31,079.2 QPS (+26.7%). Same-run CPython 3.15.0rc1 asyncio reaches
66,105.5 QPS, a remaining 2.13x gap. This does **not** establish a production
pcc/pcc1 speedup or a fully pcc1-owned runtime build.

## Change and execution ownership

`pcc/native_ir/driver.py` previously rejected `mem2reg,sroa`. It now uses
the production `run_owned_passes` dispatcher, preserving the combined memory
tier and subsequent pass order. Gateway's `build_runtime_variants.py` now
includes this tier. The normal frontend already selected memory promotion;
this repair closes the standalone entry's gap rather than changing its default.

The A/B holds application PCOs, pre-pass IR, self emitter, target options and
remaining runtime archive constant. Only `py_obj` and `py_list` are replaced.
Host CPython runs the owned optimizer, self AArch64 emitter and owned linker;
LLVM imports are blocked in the optimizer/emitter process. Remaining archive
members are prebuilt **external-LLVM-emitted** objects. This is GC0 diagnostic
execution, with two real children, joins, cleanup and identical JSON validation.
It excludes HTTP and TLS.

Both arms receive fresh IR compiled with `PCC_PYTHON_IR_PASSES=off`, using the
runtime-port ABI source route (`py_runtime_ab/py`). The control passes are
`instsimplify,simplifycfg,inline-defined,instsimplify,simplifycfg,instcombine,dce`;
the candidate prepends `mem2reg,sroa`. Optimization and emission use the same
frozen core source in both arms, without an emission cache.

| Module | Control allocas / loads / stores | Candidate allocas / loads / stores |
|---|---:|---:|
| py_obj | 178 / 829 / 370 | 7 / 191 / 107 |
| py_list | 608 / 2,226 / 1,112 | 105 / 271 / 159 |

## Same-run measurements

Five rotating repeats, C=1/10/100, waits=0/100 ms; 20,000 measured requests per
zero-wait run and ten batches per waiting run. The core performance lock,
240-second process-group watchdog and 2 GiB tree-RSS cap cover the measurements.
All 90 runs completed. Request/warmup/round counts, finite latency bounds and
the minimum elapsed/child-wait bounds were checked. QPS excludes startup,
warmups and final formatting; process counters include them.

| Zero-wait concurrency | Without memory tier | With memory tier | asyncio |
|---:|---:|---:|---:|
| 1 | 18,021.6 | 22,813.6 | 8,260.0 |
| 10 | 24,455.9 | 30,013.4 | 43,677.6 |
| 100 | 24,531.3 | 31,079.2 | 66,105.5 |

At C100, QPS ranges are 22,363.5–28,198.3 / 30,057.1–35,040.6 /
52,026.9–81,333.9. There is substantial host variability; the deterministic
signals also improve: instructions/request 531,667.6 → 471,688.5 (-11.3%),
CPU/request 40.5 → 32.0 microseconds, peak RSS 17.64 → 17.61 MiB.
Asyncio uses 175,781.7 instructions/request, 15.5 microseconds CPU/request and
28.19 MiB peak RSS. CPU time has the resolution of Darwin `time -lp`.

At 100 ms/C100 the three medians are 967.1 / 973.7 / 976.3 QPS. The waiting
workload provides a correctness/timer check and is not a CPU-throughput win.

## Baseline, profiling and rejected preparation

The separate [initial comparison](2026-09-08-asyncio-challenge-baseline.md)
uses current frozen host compiler sources and a provenance-verified historical
five-pass runtime. It completes 36 runs; C100 is 29,830.0 versus 66,651.8 QPS.
Small host tests overlapped part of that initial diagnostic sweep; use the
subsequent isolated A/B for the optimization comparison. Installed pcc1 was
omitted after it failed to compile `continuation_factory` and `c_obj`.
The live worktree runtime archive was rejected because `py_obj.py` did not
match its receipt. No mismatching archive was used for timing.

The [baseline profile](2026-09-08-asyncio-challenge-profile.json) completes
one million validated requests, with 4,188 on-CPU samples. `py_list_set` has
22.06% inclusive samples, and object-start validation has 12.63% leaf samples.
These shares overlap and must not be added. [Folded stacks](2026-09-08-asyncio-challenge-profile.folded)
bind the observations to the profiled binary.

An initial A/B on historical `.input.ll` produced **byte-identical binaries**:
that IR already contained memory promotion. No timing gain is claimed for it.
One fresh-IR preparation outside the runtime-port source route generated
strict-no-libpython stubs and failed its control smoke execution. It was
rejected before measurement; the successful run uses explicit runtime ABI
exports and suppresses implicit managed roots as the normal runtime build does.

## Validation and open gate

38 core host optimizer checks pass, including standalone CLI execution with
LLVM imports blocked, pass order, loop PHIs, escaping pointers and volatile
memory. A separate branch-and-loop regression optimizes IR, emits AArch64,
links with the owned linker and executes the resulting native program.
The 21 gateway structured-concurrency/workload checks and the new benchmark
pass-manifest regression pass. `git diff --check` is clean in both repositories.

Building the complete standalone native optimizer with the self backend
**times out at 300 seconds**, in the huge-module emit worker (peak tree RSS
754,581,504 bytes). The watchdog terminates its process group. Native optimizer
execution is therefore still unqualified; the small emitted-program test is
a narrower boundary. No bootstrap fixed point, all-five-GC qualification,
live HTTP or HTTPS result is claimed. Production GC/runtime source is unchanged
by this work, and the experimental artifacts are not installed.

Next work remains in [pcc #188](https://github.com/allstoalls/pcc/issues/188):
make the standalone optimizer's native build complete within a bounded gate,
then repeat emitted memory-tier and full gateway cleanup execution before
qualifying it. The throughput target remains open; the two-module repair
leaves a 2.13x gap and does not replace profiling the remaining core costs.

## Receipts and reproduction

- [Raw 90-run A/B](2026-09-08-standalone-memory-ab.json),
  [build receipt](2026-09-08-standalone-memory-ab-build.json).
- [Source/artifact audit](2026-09-08-asyncio-challenge-audit.json),
  [frozen input hashes](2026-09-08-asyncio-challenge-inputs.json),
  [native build timeout receipt](2026-09-08-standalone-memory-native-timeout.json).
- [Dated reproduction script](2026-09-08-standalone-memory-ab-reproduce.py).

The retained local snapshot is
`benchmarks/build/2026-09-08-asyncio-challenge`. It contains the frozen compiler
sources, raw IR/source inputs, archive and application PCOs. The script accepts
that snapshot and a **new** output directory; run it under the existing core
process-tree watchdog/performance lock, then use `artifact_compare.py`:

```bash
env -u LC_ALL uv run python ../pcc/scripts/run_process_tree_sample.py \
  --result /tmp/memory-repeat.json --samples /tmp/memory-repeat.samples \
  --stdout /tmp/memory-repeat.stdout --stderr /tmp/memory-repeat.stderr \
  --timeout 240 --max-tree-rss-bytes 6442450944 -- \
  .venv/bin/python benchmarks/results/2026-09-08-standalone-memory-ab-reproduce.py \
  benchmarks/build/2026-09-08-asyncio-challenge /tmp/memory-repeat-build

env -u LC_ALL uv run python ../pcc/scripts/run_process_tree_sample.py \
  --no-performance-lock --result /tmp/memory-timing.json \
  --samples /tmp/memory-timing.samples --stdout /tmp/memory-timing.stdout \
  --stderr /tmp/memory-timing.stderr --timeout 240 --max-tree-rss-bytes 2147483648 -- \
  .venv/bin/python benchmarks/artifact_compare.py \
  --native without-memory=/tmp/memory-repeat-build/control \
  --native with-memory=/tmp/memory-repeat-build/candidate \
  --build-report /tmp/memory-repeat-build/build.json \
  --concurrency 1,10,100 --delays 0,100 --requests 20000 --repeats 5 \
  --output /tmp/memory-repeat-results.json
```

The timing runner owns the lock in the second command. The source snapshot
contains pre-existing core work; its hashes, not merely the commit name, bind
these results. Runtime archives and binaries are local artifacts, not included
in the source-only receipts.
