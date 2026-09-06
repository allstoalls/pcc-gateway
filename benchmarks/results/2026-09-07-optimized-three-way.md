# Structured-concurrency comparison

Run: 2026-09-06T18:55:09.277616+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 5701.0 | 5519.2–5922.8 | 0.073 | 0.203 | 27.44 |
| 0 | 1 | host-pcc | 15550.5 | 14611.9–15689.4 | 0.031 | 0.044 | 46.59 |
| 0 | 1 | pcc1 | 15194.2 | 14351.8–16025.3 | 0.031 | 0.046 | 46.67 |
| 0 | 10 | asyncio | 20800.4 | 9737.1–25898.7 | 0.263 | 0.714 | 27.59 |
| 0 | 10 | host-pcc | 21301.6 | 15742.1–21606.4 | 0.211 | 0.366 | 45.59 |
| 0 | 10 | pcc1 | 18749.3 | 15368.6–20979.9 | 0.213 | 0.458 | 45.66 |
| 0 | 100 | asyncio | 42647.1 | 26369.7–47616.9 | 1.481 | 2.904 | 27.72 |
| 0 | 100 | host-pcc | 22092.9 | 20396.6–24287.8 | 2.021 | 3.014 | 46.72 |
| 0 | 100 | pcc1 | 22241.0 | 20396.0–23759.9 | 1.991 | 2.863 | 46.80 |
| 100 | 1 | asyncio | 9.9 | 9.7–9.9 | 101.291 | 102.411 | 27.09 |
| 100 | 1 | host-pcc | 10.0 | 9.9–10.0 | 100.174 | 101.360 | 3.66 |
| 100 | 1 | pcc1 | 10.0 | 9.9–10.0 | 100.279 | 101.101 | 3.77 |
| 100 | 10 | asyncio | 98.4 | 96.0–98.7 | 101.461 | 103.876 | 27.03 |
| 100 | 10 | host-pcc | 99.0 | 98.4–99.2 | 100.608 | 101.472 | 4.78 |
| 100 | 10 | pcc1 | 99.1 | 98.4–99.3 | 100.478 | 101.903 | 4.92 |
| 100 | 100 | asyncio | 953.0 | 899.6–962.2 | 103.529 | 109.199 | 27.70 |
| 100 | 100 | host-pcc | 940.7 | 929.1–949.0 | 102.931 | 106.855 | 13.55 |
| 100 | 100 | pcc1 | 944.0 | 927.1–949.0 | 102.963 | 105.012 | 13.62 |

Raw samples and provenance: [2026-09-07-optimized-three-way.json](2026-09-07-optimized-three-way.json).
