# Structured-concurrency comparison

Run: 2026-09-07T00:31:22.555152+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 9255.1 | 8896.5–9295.3 | 0.061 | 0.076 | 27.28 |
| 0 | 1 | host-pcc | 32569.7 | 29912.7–32730.0 | 0.013 | 0.016 | 7.06 |
| 0 | 1 | pcc1 | 31741.6 | 31500.0–32333.4 | 0.013 | 0.016 | 7.17 |
| 0 | 10 | asyncio | 49385.8 | 46853.2–51039.8 | 0.120 | 0.152 | 27.28 |
| 0 | 10 | host-pcc | 47676.3 | 47190.3–48006.3 | 0.092 | 0.106 | 7.23 |
| 0 | 10 | pcc1 | 46705.4 | 41329.8–47342.2 | 0.093 | 0.109 | 7.34 |
| 0 | 100 | asyncio | 86611.5 | 85695.8–89962.7 | 0.710 | 0.827 | 27.62 |
| 0 | 100 | host-pcc | 49087.9 | 48274.7–49640.1 | 0.887 | 0.999 | 7.88 |
| 0 | 100 | pcc1 | 48457.6 | 48337.2–49048.0 | 0.893 | 0.983 | 7.98 |
| 100 | 1 | asyncio | 9.9 | 9.8–9.9 | 101.327 | 101.614 | 26.80 |
| 100 | 1 | host-pcc | 10.0 | 9.9–10.0 | 100.204 | 100.973 | 3.55 |
| 100 | 1 | pcc1 | 10.0 | 9.9–10.0 | 100.253 | 101.112 | 3.66 |
| 100 | 10 | asyncio | 98.4 | 98.2–98.4 | 101.472 | 101.958 | 26.80 |
| 100 | 10 | host-pcc | 99.2 | 98.7–99.4 | 100.317 | 101.209 | 3.69 |
| 100 | 10 | pcc1 | 98.9 | 98.8–99.3 | 100.542 | 101.571 | 3.80 |
| 100 | 100 | asyncio | 945.7 | 945.1–951.6 | 104.155 | 105.435 | 27.56 |
| 100 | 100 | host-pcc | 942.5 | 937.4–959.6 | 102.469 | 104.646 | 4.94 |
| 100 | 100 | pcc1 | 941.6 | 932.3–952.0 | 102.776 | 104.526 | 5.05 |

Raw samples and provenance: [2026-09-07-field-owners-three-way.json](2026-09-07-field-owners-three-way.json).
