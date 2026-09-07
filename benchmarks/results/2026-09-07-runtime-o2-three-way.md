# Structured-concurrency comparison

This retained diagnostic uses LLVM O2 on five runtime modules. The automatic
build policy was subsequently withdrawn; these results do not describe the
current default toolchain or prove an LLVM-free runtime build.

Run: 2026-09-07T05:49:35.038449+00:00; macOS-26.5.1-arm64-arm-64bit-Mach-O; Apple M2 Max.

Two concurrent child waits and validated JSON per request; one carrier/event loop.
These are handler requests/s, excluding HTTP and network transport.
QPS is the median of repeated runs; percentiles pool measured requests.
Process peak RSS includes startup and warmups.

| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
|---:|---:|---|---:|---:|---:|---:|---:|
| 0 | 1 | asyncio | 9014.5 | 8745.7–9057.0 | 0.063 | 0.081 | 27.53 |
| 0 | 1 | host-pcc | 38743.8 | 37719.1–38926.6 | 0.011 | 0.014 | 7.16 |
| 0 | 1 | pcc1 | 38822.3 | 38447.6–39188.3 | 0.011 | 0.013 | 7.14 |
| 0 | 10 | asyncio | 48116.3 | 43925.2–49575.5 | 0.122 | 0.147 | 27.48 |
| 0 | 10 | host-pcc | 55892.2 | 55670.6–56509.3 | 0.078 | 0.092 | 7.33 |
| 0 | 10 | pcc1 | 55807.9 | 50584.8–56145.7 | 0.078 | 0.095 | 7.31 |
| 0 | 100 | asyncio | 85437.0 | 71767.8–86439.8 | 0.738 | 0.977 | 27.83 |
| 0 | 100 | host-pcc | 57469.9 | 55896.5–57642.9 | 0.758 | 0.892 | 7.97 |
| 0 | 100 | pcc1 | 57662.8 | 57081.5–58035.6 | 0.754 | 0.863 | 7.95 |
| 100 | 1 | asyncio | 9.9 | 9.8–9.9 | 101.223 | 101.799 | 27.11 |
| 100 | 1 | host-pcc | 10.0 | 9.9–10.0 | 100.394 | 101.001 | 3.66 |
| 100 | 1 | pcc1 | 10.0 | 10.0–10.0 | 100.275 | 100.898 | 3.64 |
| 100 | 10 | asyncio | 98.4 | 98.1–98.6 | 101.493 | 101.813 | 27.11 |
| 100 | 10 | host-pcc | 99.3 | 99.1–99.5 | 100.381 | 101.282 | 3.78 |
| 100 | 10 | pcc1 | 99.4 | 99.0–99.6 | 100.222 | 101.139 | 3.78 |
| 100 | 100 | asyncio | 956.5 | 950.4–960.5 | 103.495 | 104.743 | 27.62 |
| 100 | 100 | host-pcc | 947.7 | 942.6–968.7 | 102.140 | 103.932 | 5.03 |
| 100 | 100 | pcc1 | 948.6 | 944.0–975.5 | 102.128 | 103.601 | 5.00 |

Raw samples and provenance: [2026-09-07-runtime-o2-three-way.json](2026-09-07-runtime-o2-three-way.json).
