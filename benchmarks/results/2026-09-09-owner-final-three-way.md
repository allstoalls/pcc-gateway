# Structured-concurrency comparison

Run: 2026-09-09T13:07:01.942280+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 9499.5 | 9271.7–9585.0 | 0.060 | 0.070 | 28.22 |
| 0 | 1 | host-pcc | 37890.8 | 37589.7–38738.7 | 0.011 | 0.013 | 14.44 |
| 0 | 1 | pcc1 | 38227.8 | 37922.1–38420.9 | 0.011 | 0.012 | 14.30 |
| 0 | 10 | asyncio | 49718.6 | 49262.3–51895.5 | 0.119 | 0.134 | 28.25 |
| 0 | 10 | host-pcc | 54127.6 | 53421.1–54638.8 | 0.080 | 0.093 | 14.42 |
| 0 | 10 | pcc1 | 53478.1 | 52117.5–54412.4 | 0.081 | 0.095 | 14.28 |
| 0 | 100 | asyncio | 89946.5 | 87251.5–90130.7 | 0.695 | 0.773 | 28.70 |
| 0 | 100 | host-pcc | 56562.5 | 55449.6–57475.1 | 0.765 | 0.863 | 15.05 |
| 0 | 100 | pcc1 | 56443.4 | 54862.3–57004.7 | 0.769 | 0.862 | 14.91 |
| 100 | 1 | asyncio | 9.8 | 9.8–9.9 | 101.735 | 102.397 | 26.77 |
| 100 | 1 | host-pcc | 10.0 | 9.9–10.0 | 100.239 | 101.044 | 3.70 |
| 100 | 1 | pcc1 | 10.0 | 9.9–10.0 | 100.397 | 101.139 | 3.56 |
| 100 | 10 | asyncio | 97.9 | 97.3–98.3 | 102.005 | 102.896 | 26.92 |
| 100 | 10 | host-pcc | 99.3 | 99.1–99.5 | 100.465 | 101.204 | 3.84 |
| 100 | 10 | pcc1 | 99.3 | 98.9–99.5 | 100.418 | 101.176 | 3.70 |
| 100 | 100 | asyncio | 955.9 | 951.6–959.2 | 103.589 | 106.399 | 27.38 |
| 100 | 100 | host-pcc | 957.8 | 954.3–965.8 | 101.845 | 103.904 | 4.89 |
| 100 | 100 | pcc1 | 960.2 | 957.4–964.9 | 101.831 | 104.114 | 4.77 |

Raw samples and provenance: [2026-09-09-owner-final-three-way.json](2026-09-09-owner-final-three-way.json).
