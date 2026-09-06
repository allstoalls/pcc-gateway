# Recorded benchmark evidence

Reports retain the original measurements and local artifact identities.
`complete: true` means the workload and count checks passed; it does not by
itself establish an optimization win. Compare paired arms within one report.
Machine load and compiler/runtime identities differ between reports.

| Report | Status and interpretation |
|---|---|
| [2026-09-07-first-entry-idle-ab.json](2026-09-07-first-entry-idle-ab.json) | Complete host-pcc compiler A/B after other CPU-intensive programs stopped; 42 runs / 441,000 requests. Zero-wait C100 median 37,943.8 → 39,368.2 QPS (+3.8%); same-run asyncio 86,549.5. Native pcc1 qualification pending. |
| [2026-09-07-first-entry-ab-v2.json](2026-09-07-first-entry-ab-v2.json) | Incomplete: 21 zero-wait runs recorded, then native min/max summary incorrectly returned zero for the 100 ms latency array. No accepted result. |
| [2026-09-07-first-entry-ab.json](2026-09-07-first-entry-ab.json) | Incomplete: compiler rejected the copied source root before any requests because its AGENTS.md root marker was absent. |
| [2026-09-07-optimized-three-way.json](2026-09-07-optimized-three-way.json) / [table](2026-09-07-optimized-three-way.md) | **Latest three-way comparison**, both native arms use the optimized runtime; 90 valid runs. Zero-wait/concurrency 100: 22,092.9 / 22,241.0 / 42,647.1 QPS (host pcc / pcc1 / asyncio). |
| [2026-09-06-macos-arm64.json](2026-09-06-macos-arm64.json) / [table](2026-09-06-macos-arm64.md) | Complete original host-pcc/pcc1/CPython 3.15.0rc1 asyncio baseline, before runtime optimization; 90 runs. |
| [2026-09-07-empty-io-poll-ab.json](2026-09-07-empty-io-poll-ab.json) | Complete, accepted: zero-wait median 8,758.9 → 36,556.9 QPS. All 20 runs retained, including a slow control outlier. |
| [2026-09-07-empty-io-poll-attribution.json](2026-09-07-empty-io-poll-attribution.json) | Runtime-module attribution for the preceding A/B, not a throughput report. Normalized IR differs only in the virtual-thread runtime module. |
| [2026-09-07-self-store-ab.json](2026-09-07-self-store-ab.json) | Complete, accepted: zero-wait median 36,739.3 → 38,239.2 QPS; 20 runs. Both arms already include the empty-poll optimization. |
| [2026-09-07-frame-init-ab.json](2026-09-07-frame-init-ab.json) | Complete, noisy experiment; zero-wait median 24,270.2 → 23,241.1 QPS. No accepted gain; 20 runs. |
| [2026-09-07-frame-runtime-control-ab.json](2026-09-07-frame-runtime-control-ab.json) | **Incomplete and invalid for performance conclusions.** A live compiler/new ABI was paired with older archives; execution failed with missing `_py_obj_eq_value`. Zero completed request runs. |
| [2026-09-07-frame-runtime-frozen-control-v2.json](2026-09-07-frame-runtime-frozen-control-v2.json) | Complete frozen-compiler retry under variable load. Bulk frame initialization disabled in both arms; zero-wait median 19,678.2 → 18,899.5 QPS with overlapping ranges. All 20 runs retained; its summary contains only zero-wait rows. |
| [2026-09-07-frame-init-frozen-counters.json](2026-09-07-frame-init-frozen-counters.json) | Bulk-frame diagnostic: 15 runs, 20,000 requests each, zero wait, summary output, same-run asyncio witness. Instructions/request fall 3.7%, user CPU/request unchanged, QPS ranges overlap. Bulk frame initialization remains disabled by default. |

The latest three-way report measures both host pcc and native pcc1 with the
optimized runtime. Earlier runtime A/B experiments use host pcc only. The
remaining high-concurrency throughput gap is tracked in
[pcc #188](https://github.com/allstoalls/pcc/issues/188). These reports measure
handler throughput, not HTTP socket QPS.

Run the checked-in [comparison](../compare.py), [runtime A/B](../runtime_ab.py)
and [profiling](../profile.py) scripts from the repository uv environment.
See the [benchmark notes](../README.md) for
commands, workload details, timing boundaries and qualification limits.
