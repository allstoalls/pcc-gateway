# Gateway six-arm comparison — 2026-09-14

**COMPLETE: 180/180 validated runs.** Started 2026-09-13T17:05:04.057207+00:00; completed
2026-09-13T17:12:25.903637+00:00 (September 14 in Asia/Singapore).
Total watchdog time: 441.97 seconds. Apple M2 Max, 12 logical CPUs,
macOS 26.5.1, arm64, CPython 3.15.0rc1.

## Results

Zero child wait, median handler requests/s across five rotating repeats:

| Implementation | C1 requests/s | C10 requests/s | C100 requests/s | C100 peak RSS |
|---|---:|---:|---:|---:|
| host pcc · virtual threads | 13,268 | 18,577 | 18,075 | 6.42 MiB |
| pcc1 · virtual threads | 13,309 | 18,419 | 18,092 | 6.38 MiB |
| host pcc · asyncio/vthread prototype | 7,335 | 9,292 | 9,087 | 30.03 MiB |
| pcc1 · asyncio/vthread prototype | 7,295 | 9,398 | 9,087 | 30.05 MiB |
| CPython asyncio TaskGroup | 8,725 | 49,056 | 82,007 | 27.67 MiB |
| CPython asyncio gather | 8,836 | 46,670 | 78,105 | 27.70 MiB |

C100 ordinary pcc1 reaches 22.1% of asyncio TaskGroup throughput in this run.
The two ordinary native arms are close, as are the two prototype arms.
These observations do not attribute the remaining gap to an optimizer or
scheduler mechanism, nor establish a regression against a different run.

The full [36-row table](comparison.md) and [raw report](comparison.json)
include C=1/10/100, child wait=0/100 ms, five repeats and six implementations.
At zero wait, each repeat measures 5,000 requests; with 100 ms waits, each
repeat measures ten batches. Every process performs two warmup batches.
All requests execute two child operations and validate the JSON bytes.
Each reported latency array and request/warmup count is checked by the runner.
This workload uses no HTTP sockets. Native runs use GC0 and one carrier;
CPython uses one event loop. RSS and process counters include startup/warmups.

## Toolchain and scope

- Host compiler: frozen current source, manifest identity
  `ecaf4d7d5b3b59d82297c55b4f16a21a6a12e3512279d31458c1799db851cd3d`; see [source manifest](compiler-source-manifest.json).
- Native compiler: existing experimental U component binary,
  `e39a998cc0cb51677fb8973735904a817486f3b472a77c3965cf562bf8f42a92`; its B42
  [source manifest](pcc1-source-manifest.json) predates the host's final
  closure-cell correction. The [full Stage1 attempt](pcc1-stage1-attempt.json)
  exceeded 420 seconds; the subsequently linked binary successfully compiled
  and executed both gateway programs here. This run does not turn that failed
  full build into a passing Stage1/fixed-point receipt.
- Application runtime: the same prebuilt archive for all four native arms,
  `923a7bd54b0c02a500bd0d8bbdb4b9fd6e050e1867a24436372aecaa3b7d4db7`. Its [member provenance](runtime-provenance.json)
  records 171 pcc-Python members, all emitted by
  `pcc-self-backend-object-writer`, all `uses_host_cc=false`. It came from the
  existing Make/ar build route; this run did not rebuild the runtime or qualify
  cold-build ownership.
- Compiler entry flags: `--backend self --python-libpython off --ir-scaffold on`.
  `PCC_PYTHON_IR_PASSES` was unset; source policy selects the existing owned
  `mem2reg,sroa` default, including the direct-worker route. No extra pass or
  runtime optimization variant was selected for this measurement. This is
  an end-to-end application comparison, not an isolated pass-effect audit.
- Effective environment: `PCC_NO_AUTO_PCC1=1`, `PCC_GC_BACKEND=0`,
  `PCC_WITH_THREADS=0`, `PCC_RUNTIME_HIGH=py`,
  `PCC_DISABLE_BULK_GENERATOR_FRAME_INIT=1`; a fixed `PCC_RUNTIME_ARCHIVE`,
  `PCC_RUNTIME_CC=/usr/bin/false`, and the frozen compiler source root.
  Existing compiler caches were not cleared; compile times are not cold-build
  measurements or a controlled compiler A/B.
- All four fresh application executables link only `/usr/lib/libSystem.B.dylib`.
  Their hashes, compile times and linkage are in [artifacts](artifacts.json).
  This is successful pcc1 compilation and native execution evidence, not a
  complete external-tool-denial audit, fresh five-GC gate or self-host fixed point.
- The prototype is the checked-in asyncio-on-vthreads `run`/`gather`/`sleep`
  experiment. It is not general asyncio compatibility.

## Reproduction and evidence

The unmodified [compare.py](../../compare.py) was run from a frozen gateway
snapshot with `--include-asyncio-vthread`, the compiler/runtime paths in
[inputs](inputs.json), and default matrix sizes. Gateway source commit:
`5453ad2dadb46f277712759a6d894ea33f856910`; core base commit:
`8812f926193eec30be2830d238155f9810a4316b` plus the recorded worktree source manifests.
Do not substitute that base commit alone for the frozen compiler source.

The exact invocation is retained in [watchdog receipt](watch.json), with
[stdout](run.stdout), [stderr](run.stderr) and [tree RSS samples](rss.tsv).
The runner held the shared core performance lock; the outer watchdog used
`--no-performance-lock`, a 1,800 s limit and an 8 GiB tree-RSS cap. Peak sampled
tree RSS was 1.08 GiB. Compilation limits remained
300 s per arm, and benchmark process limits remained 60 s.

See [benchmark instructions](../../README.md#six-arm-handler-comparison) for
the command structure. To reproduce these exact artifacts, retain the frozen
inputs identified here; substituting a newer compiler or archive is a new
measurement. Original absolute artifact/log paths are preserved in the raw
JSON; the four compile logs are also copied into this result directory.
No compiler rebuild, runtime rebuild, installation, commit or push was done.
