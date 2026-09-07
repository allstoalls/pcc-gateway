# Memory register selection: contended diagnostic

The adjacent JSON contains 42 validated runs, but is **not a throughput
acceptance result**. A concurrent golangci-lint process used about six CPU
cores and a virtual machine used about one. Both LLVM and asyncio also
slowed dramatically. Do not compare these QPS numbers with earlier rounds or
attribute the noisy within-round QPS differences to the compiler change.

The process instruction medians were 10.591B → 10.432B on owned IR and
10.393B → 10.256B on LLVM-O2 IR. Native code generation and a quiet matched
QPS rerun are still required before accepting a throughput claim.

Workload: 100 concurrent handler tasks per barrier batch, zero delay, 20,000
requests per run, seven rotating repetitions, one carrier, GC0; no HTTP.
The five runtime IR inputs, application objects and remaining archive are
fixed across each before/after pair. Raw commands and hashes are in the JSON.
