# Structured-concurrency comparison

Run: 2026-09-13T17:05:04.057207+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.
Status: COMPLETE.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 8725.4 | 7608.9–9194.2 | 0.062 | 0.090 | 27.33 |
| 0 | 1 | asyncio-gather | 8835.8 | 8158.8–9094.3 | 0.063 | 0.089 | 27.22 |
| 0 | 1 | host-pcc | 13268.0 | 11958.0–13422.9 | 0.032 | 0.040 | 5.47 |
| 0 | 1 | pcc1 | 13308.6 | 13033.9–13390.3 | 0.032 | 0.039 | 5.41 |
| 0 | 1 | host-pcc-asyncio-vthread-prototype | 7334.9 | 7146.2–7384.7 | 0.078 | 0.100 | 31.92 |
| 0 | 1 | pcc1-asyncio-vthread-prototype | 7294.8 | 7086.1–7410.0 | 0.077 | 0.100 | 31.94 |
| 0 | 10 | asyncio | 49056.0 | 48465.8–49842.2 | 0.120 | 0.147 | 27.44 |
| 0 | 10 | asyncio-gather | 46670.2 | 38933.2–47629.3 | 0.126 | 0.172 | 27.28 |
| 0 | 10 | host-pcc | 18576.7 | 18409.8–18732.5 | 0.221 | 0.257 | 5.48 |
| 0 | 10 | pcc1 | 18419.4 | 17220.5–18711.4 | 0.221 | 0.260 | 5.42 |
| 0 | 10 | host-pcc-asyncio-vthread-prototype | 9292.4 | 9177.9–9580.0 | 0.673 | 0.822 | 29.02 |
| 0 | 10 | pcc1-asyncio-vthread-prototype | 9398.4 | 9246.2–9493.4 | 0.674 | 0.815 | 29.03 |
| 0 | 100 | asyncio | 82006.8 | 80171.9–85475.6 | 0.739 | 0.916 | 27.67 |
| 0 | 100 | asyncio-gather | 78104.7 | 77574.4–80977.2 | 0.783 | 0.978 | 27.70 |
| 0 | 100 | host-pcc | 18075.4 | 16820.0–18897.9 | 2.188 | 2.683 | 6.42 |
| 0 | 100 | pcc1 | 18092.1 | 17067.1–18471.5 | 2.202 | 2.699 | 6.38 |
| 0 | 100 | host-pcc-asyncio-vthread-prototype | 9086.9 | 8874.7–9302.1 | 7.078 | 8.047 | 30.03 |
| 0 | 100 | pcc1-asyncio-vthread-prototype | 9087.0 | 8902.4–9106.7 | 7.067 | 8.212 | 30.05 |
| 100 | 1 | asyncio | 9.9 | 9.9–9.9 | 101.153 | 101.277 | 26.80 |
| 100 | 1 | asyncio-gather | 9.9 | 9.9–9.9 | 101.163 | 101.297 | 26.86 |
| 100 | 1 | host-pcc | 10.0 | 9.9–10.0 | 100.419 | 100.997 | 4.39 |
| 100 | 1 | pcc1 | 10.0 | 10.0–10.0 | 100.231 | 101.124 | 4.34 |
| 100 | 1 | host-pcc-asyncio-vthread-prototype | 9.9 | 9.9–10.0 | 100.415 | 101.122 | 4.44 |
| 100 | 1 | pcc1-asyncio-vthread-prototype | 9.9 | 9.9–9.9 | 100.577 | 101.127 | 4.44 |
| 100 | 10 | asyncio | 98.7 | 98.6–98.8 | 101.234 | 101.674 | 26.83 |
| 100 | 10 | asyncio-gather | 98.6 | 98.5–98.8 | 101.249 | 101.781 | 26.83 |
| 100 | 10 | host-pcc | 99.2 | 98.0–99.4 | 100.607 | 101.431 | 4.52 |
| 100 | 10 | pcc1 | 98.6 | 98.1–99.4 | 100.678 | 101.800 | 4.47 |
| 100 | 10 | host-pcc-asyncio-vthread-prototype | 98.3 | 96.4–98.5 | 101.085 | 102.422 | 5.02 |
| 100 | 10 | pcc1-asyncio-vthread-prototype | 97.6 | 97.4–98.6 | 101.171 | 102.406 | 5.02 |
| 100 | 100 | asyncio | 970.7 | 962.5–976.2 | 102.028 | 104.046 | 27.61 |
| 100 | 100 | asyncio-gather | 975.6 | 963.1–977.6 | 101.972 | 104.024 | 27.44 |
| 100 | 100 | host-pcc | 943.7 | 919.8–945.5 | 102.673 | 105.484 | 5.73 |
| 100 | 100 | pcc1 | 941.0 | 940.6–946.0 | 102.553 | 103.493 | 5.67 |
| 100 | 100 | host-pcc-asyncio-vthread-prototype | 909.9 | 900.3–916.2 | 104.781 | 107.604 | 11.06 |
| 100 | 100 | pcc1-asyncio-vthread-prototype | 915.2 | 902.2–920.9 | 104.434 | 106.721 | 11.06 |

Raw samples and provenance: [comparison.json](comparison.json).
