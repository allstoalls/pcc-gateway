# Structured-concurrency comparison

Run: 2026-09-09T03:56:44.119389+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 8508.8 | 8202.3–8784.6 | 0.063 | 0.096 | 28.23 |
| 0 | 1 | host-pcc | 36136.0 | 33977.1–36716.7 | 0.012 | 0.014 | 14.34 |
| 0 | 1 | pcc1 | 36012.7 | 32152.4–36368.7 | 0.012 | 0.014 | 14.34 |
| 0 | 10 | asyncio | 48692.7 | 48196.0–48778.2 | 0.119 | 0.155 | 28.19 |
| 0 | 10 | host-pcc | 51847.6 | 49669.6–52416.7 | 0.082 | 0.097 | 14.36 |
| 0 | 10 | pcc1 | 50243.8 | 49235.9–51231.5 | 0.084 | 0.099 | 14.34 |
| 0 | 100 | asyncio | 83210.6 | 74892.1–84365.1 | 0.732 | 0.913 | 28.70 |
| 0 | 100 | host-pcc | 52969.7 | 52712.2–53405.4 | 0.798 | 0.938 | 14.97 |
| 0 | 100 | pcc1 | 52213.3 | 51675.8–52396.8 | 0.813 | 0.940 | 14.97 |
| 100 | 1 | asyncio | 9.9 | 9.9–9.9 | 101.159 | 101.452 | 26.92 |
| 100 | 1 | host-pcc | 10.0 | 10.0–10.0 | 100.373 | 100.916 | 3.62 |
| 100 | 1 | pcc1 | 10.0 | 9.9–10.0 | 100.206 | 101.078 | 3.64 |
| 100 | 10 | asyncio | 98.6 | 98.6–98.6 | 101.234 | 101.834 | 27.06 |
| 100 | 10 | host-pcc | 99.4 | 99.0–99.7 | 100.357 | 101.195 | 3.78 |
| 100 | 10 | pcc1 | 99.5 | 99.2–99.6 | 100.438 | 101.054 | 3.77 |
| 100 | 100 | asyncio | 969.5 | 956.6–973.1 | 102.145 | 104.845 | 27.61 |
| 100 | 100 | host-pcc | 972.4 | 965.0–976.5 | 101.219 | 102.538 | 4.83 |
| 100 | 100 | pcc1 | 973.1 | 964.1–976.8 | 101.248 | 102.930 | 4.81 |

Raw samples and provenance: [2026-09-09-compact-final-three-way.json](2026-09-09-compact-final-three-way.json).
