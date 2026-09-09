# Structured-concurrency comparison

Run: 2026-09-08T17:29:15.367283+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 9304.9 | 9167.1–9365.8 | 0.062 | 0.071 | 28.36 |
| 0 | 1 | host-pcc | 31588.6 | 31085.7–31698.5 | 0.014 | 0.015 | 14.34 |
| 0 | 1 | pcc1 | 31189.9 | 31092.5–31344.7 | 0.014 | 0.015 | 14.38 |
| 0 | 10 | asyncio | 51218.6 | 48395.3–51530.6 | 0.114 | 0.138 | 28.34 |
| 0 | 10 | host-pcc | 46139.8 | 45786.3–46606.4 | 0.095 | 0.105 | 14.36 |
| 0 | 10 | pcc1 | 45813.5 | 45254.6–45933.9 | 0.096 | 0.106 | 14.38 |
| 0 | 100 | asyncio | 88735.6 | 85947.0–90622.0 | 0.701 | 0.779 | 28.77 |
| 0 | 100 | host-pcc | 48398.1 | 47635.3–48604.0 | 0.907 | 0.994 | 14.97 |
| 0 | 100 | pcc1 | 48003.8 | 47240.9–48297.2 | 0.914 | 0.995 | 14.98 |
| 100 | 1 | asyncio | 9.8 | 9.8–9.8 | 101.943 | 102.576 | 26.88 |
| 100 | 1 | host-pcc | 10.0 | 9.9–10.0 | 100.431 | 101.146 | 3.66 |
| 100 | 1 | pcc1 | 10.0 | 9.9–10.0 | 100.313 | 101.319 | 3.66 |
| 100 | 10 | asyncio | 98.0 | 97.6–98.1 | 102.162 | 102.821 | 26.89 |
| 100 | 10 | host-pcc | 99.2 | 98.9–99.3 | 100.670 | 101.535 | 3.80 |
| 100 | 10 | pcc1 | 99.0 | 99.0–99.2 | 100.563 | 101.383 | 3.78 |
| 100 | 100 | asyncio | 953.9 | 947.2–959.2 | 103.981 | 105.834 | 27.53 |
| 100 | 100 | host-pcc | 961.8 | 953.6–962.2 | 101.987 | 104.167 | 4.81 |
| 100 | 100 | pcc1 | 958.0 | 953.1–960.6 | 101.964 | 104.865 | 4.83 |

Raw samples and provenance: [2026-09-09-final-three-way.json](2026-09-09-final-three-way.json).
