# Reproduce and interpret benchmarks

The scripts and each run's receipts define the workload and execution path.
Use Python **3.15.0rc1**, a compatible compiler/runtime pair, a quiet machine
and a new output name. The runners acquire the core performance lock and
reject source/archive changes during a measurement.

## Prepare the runtime

The optimized-runtime reproduction needs an archive and its matching
`build_py/*.ll` inputs. From the adjacent core checkout, prepare them with
the same source and Python environment:

```bash
env -u LC_ALL uv run python scripts/run_process_tree_sample.py \
  --result build/runtime-reproduce.json \
  --samples build/runtime-reproduce.samples \
  --stdout build/runtime-reproduce.stdout --stderr build/runtime-reproduce.stderr \
  --timeout 600 --max-tree-rss-bytes 4294967296 -- \
  make -j4 -C pcc/py_runtime PCC="$PWD/.venv/bin/pcc" \
  PYTHON="$PWD/.venv/bin/python" PCC_REPO_ROOT="$PWD" \
  PCC_WITH_THREADS=0 libpy_runtime_pcc_py.a
```

Use an up-to-date runtime: the builder verifies recorded IR hashes, and the
geometry-cache result requires the core allocator source containing that cache.
Runtime IR merging and O0 object emission in this experiment still use
external LLVM. Host pcc executes the owned passes; this does not establish
native toolchain independence. Do not edit inputs while measuring.
`benchmarks/reproduce.py` records the current artifact identities, GC checks,
QPS, peak process RSS and raw repetitions. Exact timings vary by machine/load.

## Three-way handler comparison

[compare.py](compare.py) builds [benchmark_native.py](../benchmark_native.py)
with host pcc and native pcc1, and runs
[benchmark_asyncio.py](../benchmark_asyncio.py) under CPython:

```bash
uv run python benchmarks/compare.py --pcc1 /path/to/pcc1 \
  --compiler-source /path/to/frozen/pcc \
  --runtime-archive /path/to/libpy_runtime_pcc_py.a \
  --output benchmarks/results/my-three-way.json
```

Inspect the script's current options. `--pcc1-binary` and `--pcc1-receipt`
bind the native compiler to its build receipt when needed. Explicit compiler
flags/environment are part of an experiment; historical settings are not
proof of today's defaults or installed toolchain qualification.

Both workloads start two children, join and validate identical sorted JSON.
Concurrency is batch width: complete C requests before starting the next batch.
Defaults are C=1/10/100, child wait=0/100 ms, two warmup batches and five repeats
with rotating arm order. This is handler throughput, excluding HTTP sockets,
compilation and process startup. CPU/RSS totals include startup and warmups.

Reports retain QPS ranges, latency samples/percentiles, process counters and
source/compiler identities. Only complete, validated reports support a result.
Batch QPS is not a steady-load HTTP server benchmark or a CPU-thread count.

## Runtime and compiler attribution

[runtime_ab.py](runtime_ab.py) holds the workload constant while comparing
explicit runtime archives and compiler sources:

```bash
uv run python benchmarks/runtime_ab.py \
  --compiler-source /path/to/frozen/pcc \
  --control-runtime /path/to/control/libpy_runtime_pcc_py.a \
  --candidate-runtime /path/to/candidate/libpy_runtime_pcc_py.a \
  --asyncio --output benchmarks/results/my-runtime-ab.json
```

For optimizer comparison, hold pre-pass IR and object emission constant; for
backend comparison, hold optimized IR and target options constant. Record the
actual pass implementation, cache identity and archive members changed.
[build_runtime_variants.py](build_runtime_variants.py) is a diagnostic entry;
audit its selected passes against production rather than assuming parity.
External LLVM references do not establish pcc1-owned compilation.

[profile.py](profile.py) reuses core native and CPython 3.15 sampling tools.
[batch_costs.py](batch_costs.py) analyzes batch overhead. Profiling/counting runs
are separate from uninstrumented throughput; retain instructions per request
as well as QPS when attributing a change.

## Compiler memory follow-up (2026-09-09)

The [latest owner checkpoint](results/2026-09-09-owner-checkpoint.json) records
the newer tuple/temporary-owner/GC4 fixes, native optimizer gate and failed
compiler builds. The earlier normal-mode [90-run comparison](results/2026-09-09-owner-final-three-way.json)
uses pcc1 `b45582507e80` and runtime `1ee0b1bb5e2b`; C100 is 56,443 versus
asyncio 89,947 QPS. This compiler's separate native-direct smoke failed.
Its normal-mode results do not turn the failed Stage1 receipt into a pass.
The [77,154-QPS owned runtime experiment](results/2026-09-09-owned-cfg-runtime-reference.json)
has a different runtime/pass scope and remains unqualified for default use.

The [string-memory receipt](results/2026-09-09-string-memory-followup.json)
replays the same 36.26 MB server IR through a native standalone optimizer.
After dict-default, comprehension and container ownership fixes, plus early
opcode rejection and lazy SROA name collection, peak RSS is **815.8 MB**;
the earlier dict-default-only source used **1,214.5 MB**. The last parser
change reduces replay time from 62.30 to 52.15 seconds with byte-identical
output. These are optimizer measurements, separate from complete application
compilation and serving RSS. The instrumented allocation run uses an external
C observer and the pinned runtime uses external LLVM object emission.

[Full native qualification](results/2026-09-09-native-memory-qualification.json)
records the isolated compiler and its scope. A Stage1 build alone does not
qualify a fixed point or replace the shared installed compiler. Final HTTP
compilation and handler measurements are recorded separately.

## Recorded results

- [Main README](../README.md): published performance table.
- [2026-09-08 memory-promotion A/B](results/2026-09-08-owned-mem2reg-runtime-ab.json)
  and [five-pass A/B](results/2026-09-08-owned-five-pass-runtime-ab.json):
  complete recorded runs, with identities and limits in each receipt.
- [Result index](results/README.md): raw experiments, including failed runs.
- [History through 2026-09-07](history-through-2026-09-07.md): earlier tables,
  rejected experiments and superseded implementation descriptions.

Compare arms within one controlled run. A historical result, a host-only gate
or a Stage1 build does not qualify the current pcc1 installation or all five GC
backends. Optimization remains tracked in
[pcc #188](https://github.com/allstoalls/pcc/issues/188).


The 2026-09-09 proven-reference candidate adds `PCC_KNOWN_OBJECT_REFS=1`
to the three recorded virtual-thread flags. Both comparison harnesses record
this setting. Keep the compiler's linked runtime identity separate from the
application runtime: that round's application archive additionally fixes raw
waiter initialization. The standalone reference-check diagnostic enables the
checked lane before main and requires an observed zero counter, including the
local HTTP probe; missing observation is not zero. See
[qualification](results/2026-09-09-known-reference-qualification.json) and
[waiter audit](results/2026-09-09-waiter-initialization-audit.json).
