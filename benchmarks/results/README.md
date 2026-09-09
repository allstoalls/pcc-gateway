# Recorded benchmark evidence

Reports retain the original measurements and local artifact identities.
`complete: true` means the workload and count checks passed; it does not by
itself establish an optimization win. Compare paired arms within one report.
Machine load and compiler/runtime identities differ between reports.

| Report | Status and interpretation |
|---|---|
| [Latest cache long comparison](2026-09-09-owned-runtime-exact-cache-long.json) | 21 runs, 200k requests/repeat: owned runtime 77,958, same plus cache 79,801, asyncio 76,504 QPS. Cache wins 4/7 paired asyncio comparisons; paired median ratio 1.0018×, so no stable-lead claim. |
| [Non-HTTP operation comparison](2026-09-09-runtime-progress/non-http.json) | 192 runs, eight unchanged core workloads, N/2N startup subtraction, CPython-matching outputs. Most object/container/string instruction counts fall 21–28% against the original runtime; wall-time gains are workload-dependent. |
| [Corrected-runtime CFG reproduction](2026-09-09-current-owned-cfg-runtime.json) | 35 runs: 55,233 -> 77,070 QPS, asyncio 84,288. Each runtime arm passes scoped GC0–4 handler, failure-cleanup and ownership checks. |
| [Earlier compiler comparison](2026-09-09-owner-final-three-way.json) / [table](2026-09-09-owner-final-three-way.md) | 90 validated normal-mode runs: C100 host pcc 56,563, pcc1 56,443, asyncio 89,947 QPS. C1/C10 lead; C100 remains 37.2% behind. Separate native-direct compiler smoke fails. |
| [Owner checkpoint](2026-09-09-owner-checkpoint.json) | Native tuple/relocation/cleanup GC0–4 pass; earlier full Stage1 4.20 GB, latest text route memory limit 4.86 GB, direct-built candidate 3.98 GB with failed native-direct smoke. Native full runtime-IR optimizer completes in 51.3 s but retains 1.10 GB live heap. |
| [Owned CFG runtime experiment](2026-09-09-owned-cfg-runtime-reference.json) | 42 runs: control 55,894 -> owned second round 77,154 QPS (+38.0%); asyncio 82,354; external LLVM-O2 reference 84,960. Earlier runtime, 12 combined modules, host-executed owned passes and external LLVM emission; no whole-runtime/default qualification. |
| [2026-09-09 final three-way comparison](2026-09-09-final-three-way.json) / [table](2026-09-09-final-three-way.md) | 90 validated runs, same current source/runtime. Zero-wait/C100: host pcc 48,398, pcc1 48,004, asyncio 88,736 QPS. High-concurrency parity remains unmet. |
| [2026-09-09 native qualification](2026-09-09-native-memory-qualification.json) | 63 pcc1-compiled ownership cases passed; native HTTP/dashboard/structured-failure examples passed. HTTP compile: pcc1 187.1 s / 2.35 GB, host pcc 81.5 s / 1.76 GB. Isolated Stage1, externally emitted runtime, no fixed-point or live-network claim. |
| [2026-09-09 current native profile](2026-09-09-current-native-profile.json) / [stacks](2026-09-09-current-native-profile.folded) | Complete 1M-request diagnostic, 3,842 samples. Disjoint provenance/refcount/barrier/graph-lock leaf groups total 54.4%; profiled QPS is not used as a comparative speed result. |
| [2026-09-09 string-memory follow-up](2026-09-09-string-memory-followup.json) | Same 36.26 MB IR and pinned runtime: 1,214.5 → 815.8 MB peak RSS, 488.2 → 275.3 MB live strings. Last parser step: 62.30 → 52.15 s, identical output. Standalone native optimizer; full compiler/gateway qualification is separate. |
| [2026-09-08 standalone memory-tier A/B](2026-09-08-standalone-memory-ab.md) / [raw](2026-09-08-standalone-memory-ab.json) | Complete 90-run, two-module diagnostic: 24,531.3 → 31,079.2 QPS (+26.7%), instructions/request -11.3%; same-run asyncio 66,105.5. Host executes owned passes/self emission/linking, other runtime members prebuilt with external LLVM. Fixes a standalone dispatcher/benchmark manifest gap; normal frontend already selected memory promotion. Native optimizer build times out; no production pcc1 or five-GC qualification. |
| [Owned runtime emission pilot](2026-09-07-owned-runtime-emission-pilot.json) / [notes and reproduction](2026-09-07-owned-runtime-emission-pilot.md) | Complete 28-run diagnostic, same application objects. Self-control 19,763.3 → owned passes 22,185.0 QPS (+12.3%); historical LLVM-runtime reference 57,777.4, same-run asyncio 86,080.5. Partial runtime emission experiment, not whole-runtime independence or a new pcc/pcc1 frontend comparison. |
| [Optimized-runtime pcc1 profile](2026-09-07-runtime-o2-profile.json) / [stacks](2026-09-07-runtime-o2-profile.folded) | Completed 1M-request diagnostic, 2,302 CPU samples. Object-start validation remains the largest leaf (368 samples); profiled QPS is not comparative throughput evidence. |
| [2026-09-07-runtime-o2-three-way.json](2026-09-07-runtime-o2-three-way.json) / [table](2026-09-07-runtime-o2-three-way.md) | Earlier three-way comparison, normal optimized runtime and pcc1 2b08f3a7aac1; 90 valid runs. Zero-wait/C100: 57,469.9 / 57,662.8 / 85,437.0 QPS; pcc1 gap 1.48×. |
| [Three-module runtime O2](2026-09-07-runtime-ir-o2-ab.json) / [build receipt](2026-09-07-runtime-ir-o2-build.json) | Complete, 42 runs. Same runtime source, only py_obj/py_list/py_gen IR optimized: 49,193.0 → 55,135.9 QPS (+12.1%), instructions/request -7.1%. |
| [Five-module runtime O2](2026-09-07-runtime-ir-o2-five-ab.json) / [build receipt](2026-09-07-runtime-ir-o2-five-build.json) | Complete, 42 runs. Add GC backend/index-table optimization: 55,401.7 → 59,032.4 QPS (+6.6%), CPU/request 18 → 17 µs; same-run asyncio 88,549.8. Normal-build/pcc1 qualification follows separately. |
| [Application Clang O2](2026-09-07-llvm-o2-application-ab.json) | Complete, 42 runs: default LLVM application emission 51,647.0 / explicit -O2 51,338.8 QPS. No gain. This holds the runtime unchanged. |
| [Frame-owner round trip](2026-09-07-frame-owner-roundtrip-ab.json) | Complete but not accepted as a speed improvement: 50,166.3 → 50,270.1 QPS (+0.21%), overlapping ranges. Application activation withdrawn. |
| [2026-09-07-frame-owner-transfer-ab.json](2026-09-07-frame-owner-transfer-ab.json) | Complete save-only transfer diagnostic, 42 runs. 48,508.0 → 47,949.2 QPS, overlapping ranges; instructions/request -0.91%, user CPU unchanged. No accepted speed gain. |
| [2026-09-07-bulk-frame-save-ab.json](2026-09-07-bulk-frame-save-ab.json) | Complete but rejected, 42 runs. Bulk save dispatch: 48,279.4 → 46,711.8 QPS (-3.25%), instructions/request +1.08%. Compiler activation withdrawn; original experimental source is core 34c3d139. |
| [2026-09-07-batch-costs.json](2026-09-07-batch-costs.json) | Analysis of the current three-way report plus counting-only asyncio runs: 7 zero-timeout selector calls per batch at C1/C10/C100. Fixed/incremental costs are two-point fits, not separately timed phases or a new QPS result. |
| [2026-09-07-self-llvm-application-ab.json](2026-09-07-self-llvm-application-ab.json) | Complete application-backend diagnostic, 42 runs: self 51,056.2 / LLVM 51,288.2 / asyncio 89,852.4 QPS. Same compiler source, runtime and workload; +0.45% does not establish a meaningful speed fix. |
| [2026-09-07-field-owners-three-way.json](2026-09-07-field-owners-three-way.json) / [table](2026-09-07-field-owners-three-way.md) | Earlier comparison, pcc1 0ff76d8bf139 before runtime optimization; 90 valid runs. Zero-wait/C100: 49,087.9 / 48,457.6 / 86,611.5 QPS, peak RSS 7.88 / 7.98 / 27.62 MiB. |
| [2026-09-07-field-owners-ab.json](2026-09-07-field-owners-ab.json) | Complete host A/B, 42 runs. Ownership repair: 53,489.8 → 50,870.8 QPS (-4.9%), peak RSS 141.31 → 17.48 MiB; asyncio 88,804.3 QPS / 27.95 MiB. Correctness gain with a throughput cost; new pcc1 qualification pending. |
| [Lifetime control](2026-09-07-field-owners-lifetime-control.json) / [candidate](2026-09-07-field-owners-lifetime.json) | Three same-process 5,000-request invocations. Tracked objects grow by 78,056 per invocation before and 4 after. The residual remains open. Produced by `benchmarks/lifetime.py`. |
| [Field-owner profile](2026-09-07-field-owners-profile.json) / [stacks](2026-09-07-field-owners-profile.folded) | Completed native diagnostic, 2,303 on-CPU samples; generator/list frame work remains prominent. Profiled QPS is not comparative throughput evidence. |
| [2026-09-07-direct-generator-ab.json](2026-09-07-direct-generator-ab.json) | Complete host A/B, 42 runs. Direct generator task ownership: 50,862.8 → 52,908.8 QPS (+4.0%), process instructions/request -3.5%, peak RSS 171.20 → 141.31 MiB. Same-run asyncio 88,979.1. Predates the field-owner lifetime repair; pcc1 qualification pending. |
| [2026-09-07-completed-handoff-ab.json](2026-09-07-completed-handoff-ab.json) | Complete host compiler/runtime A/B, 42 runs. Completed-value handoff: 45,764.6 → 50,280.9 QPS (+9.9%), instructions/request -6.9%; same-run asyncio 91,584.1. Fresh pcc1 qualification pending. |
| [2026-09-07-factory-three-way.json](2026-09-07-factory-three-way.json) / [table](2026-09-07-factory-three-way.md) | Earlier comparison, pcc1 53978d6bf7db, scope factories and first-entry optimization; 90 valid runs. Zero-wait/C100: 48,665.6 / 48,532.9 / 90,630.4 QPS. |
| [2026-09-07-continuation-factory-ab.json](2026-09-07-continuation-factory-ab.json) | Complete full-workload host-pcc source A/B, 42 runs. Normal fork/close avoid full frames: 42,473.8 → 47,228.3 QPS (+11.2%), instructions/request -10.9%; same-run asyncio 91,354.7. Native pcc1 application qualification subsequently passed; see the current three-way report. |
| [2026-09-07-handler-layers.json](2026-09-07-handler-layers.json) | Complete diagnostic ablations, 20 runs. TaskScope 39,266.7 / explicit joins and cleanup 62,125.3 / asyncio 86,322.4 QPS. JSON-only 141,280.9 removes child tasks/waits and is not a valid replacement application comparison. |
| [2026-09-07-first-entry-idle-ab.json](2026-09-07-first-entry-idle-ab.json) | Complete host-pcc compiler A/B after other CPU-intensive programs stopped; 42 runs / 441,000 requests. Zero-wait C100 median 37,943.8 → 39,368.2 QPS (+3.8%); same-run asyncio 86,549.5. Native pcc1 application qualification subsequently passed; see the current three-way report. |
| [2026-09-07-first-entry-ab-v2.json](2026-09-07-first-entry-ab-v2.json) | Incomplete: 21 zero-wait runs recorded, then native min/max summary incorrectly returned zero for the 100 ms latency array. No accepted result. |
| [2026-09-07-first-entry-ab.json](2026-09-07-first-entry-ab.json) | Incomplete: compiler rejected the copied source root before any requests because its AGENTS.md root marker was absent. |
| [2026-09-07-optimized-three-way.json](2026-09-07-optimized-three-way.json) / [table](2026-09-07-optimized-three-way.md) | Earlier three-way comparison, both native arms use the optimized runtime; 90 valid runs. Zero-wait/concurrency 100: 22,092.9 / 22,241.0 / 42,647.1 QPS (host pcc / pcc1 / asyncio). |
| [2026-09-06-macos-arm64.json](2026-09-06-macos-arm64.json) / [table](2026-09-06-macos-arm64.md) | Complete original host-pcc/pcc1/CPython 3.15.0rc1 asyncio baseline, before runtime optimization; 90 runs. |
| [2026-09-07-empty-io-poll-ab.json](2026-09-07-empty-io-poll-ab.json) | Complete, accepted: zero-wait median 8,758.9 → 36,556.9 QPS. All 20 runs retained, including a slow control outlier. |
| [2026-09-07-empty-io-poll-attribution.json](2026-09-07-empty-io-poll-attribution.json) | Runtime-module attribution for the preceding A/B, not a throughput report. Normalized IR differs only in the virtual-thread runtime module. |
| [2026-09-07-self-store-ab.json](2026-09-07-self-store-ab.json) | Complete, accepted: zero-wait median 36,739.3 → 38,239.2 QPS; 20 runs. Both arms already include the empty-poll optimization. |
| [2026-09-07-frame-init-ab.json](2026-09-07-frame-init-ab.json) | Complete, noisy experiment; zero-wait median 24,270.2 → 23,241.1 QPS. No accepted gain; 20 runs. |
| [2026-09-07-frame-runtime-control-ab.json](2026-09-07-frame-runtime-control-ab.json) | **Incomplete and invalid for performance conclusions.** A live compiler/new ABI was paired with older archives; execution failed with missing `_py_obj_eq_value`. Zero completed request runs. |
| [2026-09-07-frame-runtime-frozen-control-v2.json](2026-09-07-frame-runtime-frozen-control-v2.json) | Complete frozen-compiler retry under variable load. Bulk frame initialization disabled in both arms; zero-wait median 19,678.2 → 18,899.5 QPS with overlapping ranges. All 20 runs retained; its summary contains only zero-wait rows. |
| [2026-09-07-frame-init-frozen-counters.json](2026-09-07-frame-init-frozen-counters.json) | Bulk-frame diagnostic: 15 runs, 20,000 requests each, zero wait, summary output, same-run asyncio witness. Instructions/request fall 3.7%, user CPU/request unchanged, QPS ranges overlap. Bulk frame initialization remains disabled by default. |

The earlier [proven-reference report](2026-09-09-compact-final-three-way.json)
contains 90 validated runs with the proven-reference candidate and corrected
waiter initialization. At zero wait pcc1 reaches 36,013 / 50,244 / 52,213 QPS
at C1 / C10 / C100, versus asyncio 8,509 / 48,693 / 83,211. C10 leads by
3.2% in this run; C100 remains behind. The [native on/off A/B](2026-09-09-compact-native-ab.json)
is a separate 21-run comparison (+15.1% QPS, -11.5% instructions at C100).
See [scoped qualification](2026-09-09-known-reference-qualification.json),
[waiter defect and fix](2026-09-09-waiter-initialization-audit.json),
[updated profile](2026-09-09-compact-native-profile.json), and
[294 gateway tests](2026-09-09-compact-gateway-tests.json).

The initial known-frame/compact host experiments used incremental archives
with mixed compiler checksums and remain explicitly experimental. Their
Stage1 rejection is retained in `2026-09-09-compact-stage1.json`; the coherent
rebuild succeeds in `2026-09-09-compact-full-stage1.json`. The unchecked
refcount ceiling is diagnostic only and is not an accepted implementation.

The three-way reports measure host pcc and native pcc1 with a common application
runtime. The compact native A/B also uses native pcc1; earlier runtime A/B
experiments use host pcc. The
remaining high-concurrency throughput gap is tracked in
[pcc #188](https://github.com/allstoalls/pcc/issues/188). These reports measure
handler throughput, not HTTP socket QPS.

Run the checked-in [comparison](../compare.py), [runtime A/B](../runtime_ab.py)
and [profiling](../profile.py) scripts from the repository uv environment.
See the [benchmark notes](../README.md) for
commands, workload details, timing boundaries and qualification limits.
