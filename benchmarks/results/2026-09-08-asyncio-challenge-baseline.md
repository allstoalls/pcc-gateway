# Structured-concurrency comparison

Diagnostic baseline only: current frozen host compiler plus a verified
historical five-pass runtime whose objects were emitted by external LLVM.
Installed pcc1 failed the current API compile gate and is absent. Some small
host tests overlapped this initial sweep; use the subsequent
[isolated memory-tier A/B](2026-09-08-standalone-memory-ab.md) for attribution.

Run: 2026-09-08T06:20:36.609893+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 7178.6 | 7169.6–7262.1 | 0.067 | 0.129 | 30.73 |
| 0 | 1 | host-pcc | 21384.9 | 17598.7–23616.5 | 0.018 | 0.026 | 39.27 |
| 0 | 10 | asyncio | 45764.5 | 44105.9–47208.7 | 0.125 | 0.163 | 30.66 |
| 0 | 10 | host-pcc | 35722.8 | 31701.9–36234.9 | 0.119 | 0.139 | 39.25 |
| 0 | 100 | asyncio | 66651.8 | 60565.6–72367.1 | 0.904 | 1.210 | 30.77 |
| 0 | 100 | host-pcc | 29830.0 | 26822.3–34638.6 | 1.250 | 1.767 | 40.20 |
| 100 | 1 | asyncio | 9.9 | 9.8–9.9 | 101.126 | 101.218 | 26.98 |
| 100 | 1 | host-pcc | 10.0 | 10.0–10.0 | 100.245 | 100.829 | 3.58 |
| 100 | 10 | asyncio | 98.8 | 98.8–98.8 | 101.242 | 101.324 | 26.89 |
| 100 | 10 | host-pcc | 99.5 | 99.3–99.6 | 100.284 | 101.264 | 3.73 |
| 100 | 100 | asyncio | 974.9 | 971.6–976.3 | 102.120 | 102.769 | 27.45 |
| 100 | 100 | host-pcc | 970.6 | 968.8–972.1 | 101.328 | 101.844 | 5.47 |

Raw samples and provenance: [2026-09-08-asyncio-challenge-baseline.json](2026-09-08-asyncio-challenge-baseline.json).
