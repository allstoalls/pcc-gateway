# Structured-concurrency comparison

Run: 2026-09-06T22:37:28.718335+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 9398.3 | 9244.9–9640.8 | 0.060 | 0.070 | 27.16 |
| 0 | 1 | host-pcc | 31185.3 | 30520.9–32189.7 | 0.015 | 0.022 | 46.70 |
| 0 | 1 | pcc1 | 31771.9 | 30327.3–32151.4 | 0.015 | 0.022 | 46.56 |
| 0 | 10 | asyncio | 51590.1 | 48961.2–52717.1 | 0.117 | 0.129 | 27.20 |
| 0 | 10 | host-pcc | 46043.5 | 44743.9–46739.9 | 0.106 | 0.123 | 45.70 |
| 0 | 10 | pcc1 | 46597.5 | 45371.6–46822.2 | 0.105 | 0.120 | 45.56 |
| 0 | 100 | asyncio | 90630.4 | 81588.0–94357.2 | 0.691 | 0.830 | 27.64 |
| 0 | 100 | host-pcc | 48665.6 | 47920.3–49450.1 | 1.000 | 1.098 | 46.83 |
| 0 | 100 | pcc1 | 48532.9 | 47535.3–49792.4 | 0.992 | 1.119 | 46.69 |
| 100 | 1 | asyncio | 9.8 | 9.8–9.8 | 101.955 | 102.497 | 26.72 |
| 100 | 1 | host-pcc | 9.9 | 9.9–10.0 | 100.493 | 101.217 | 3.77 |
| 100 | 1 | pcc1 | 9.9 | 9.9–10.0 | 100.538 | 101.162 | 3.62 |
| 100 | 10 | asyncio | 97.7 | 97.7–98.2 | 101.969 | 102.922 | 26.83 |
| 100 | 10 | host-pcc | 98.7 | 98.6–99.0 | 100.841 | 101.582 | 4.89 |
| 100 | 10 | pcc1 | 98.9 | 98.5–98.9 | 100.742 | 101.620 | 4.72 |
| 100 | 100 | asyncio | 938.4 | 931.0–943.7 | 105.319 | 106.863 | 27.55 |
| 100 | 100 | host-pcc | 931.2 | 926.6–936.8 | 103.848 | 105.326 | 13.66 |
| 100 | 100 | pcc1 | 930.9 | 927.0–932.1 | 103.981 | 105.534 | 13.52 |

Raw samples and provenance: [2026-09-07-factory-three-way.json](2026-09-07-factory-three-way.json).
