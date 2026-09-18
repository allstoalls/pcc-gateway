# Structured-concurrency comparison

Run: 2026-09-18T07:56:01.167576+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.
Status: COMPLETE.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 9299.7 | 9088.5–9539.9 | 0.061 | 0.076 | 27.19 |
| 0 | 1 | host-pcc | 13318.4 | 12939.0–13643.1 | 0.032 | 0.038 | 5.48 |
| 0 | 1 | pcc1 | 13356.4 | 13010.6–13448.0 | 0.032 | 0.038 | 5.45 |
| 0 | 10 | asyncio | 50781.4 | 48100.8–51203.3 | 0.118 | 0.147 | 27.22 |
| 0 | 10 | host-pcc | 18268.5 | 18060.9–18678.3 | 0.224 | 0.258 | 5.53 |
| 0 | 10 | pcc1 | 18732.4 | 14604.6–19006.8 | 0.221 | 0.260 | 5.48 |
| 0 | 100 | asyncio | 86584.7 | 83282.8–90664.9 | 0.707 | 0.856 | 27.64 |
| 0 | 100 | host-pcc | 19245.5 | 18897.7–19894.4 | 2.119 | 2.332 | 6.45 |
| 0 | 100 | pcc1 | 18998.1 | 18519.5–19169.6 | 2.154 | 2.487 | 6.44 |
| 100 | 1 | asyncio | 9.9 | 9.8–9.9 | 101.253 | 101.908 | 26.73 |
| 100 | 1 | host-pcc | 9.9 | 9.9–9.9 | 100.521 | 101.290 | 4.44 |
| 100 | 1 | pcc1 | 9.9 | 9.9–9.9 | 100.348 | 101.474 | 4.39 |
| 100 | 10 | asyncio | 98.0 | 97.9–98.2 | 101.663 | 102.623 | 27.02 |
| 100 | 10 | host-pcc | 96.1 | 95.6–97.6 | 101.549 | 103.244 | 4.56 |
| 100 | 10 | pcc1 | 96.3 | 95.6–96.8 | 101.785 | 103.049 | 4.52 |
| 100 | 100 | asyncio | 932.8 | 922.8–960.8 | 104.862 | 107.379 | 27.38 |
| 100 | 100 | host-pcc | 795.8 | 791.0–932.3 | 108.500 | 116.107 | 5.75 |
| 100 | 100 | pcc1 | 823.0 | 802.1–929.8 | 107.170 | 115.545 | 5.73 |

Raw samples and provenance: [2026-09-18-selfhost-gates.json](2026-09-18-selfhost-gates.json).
