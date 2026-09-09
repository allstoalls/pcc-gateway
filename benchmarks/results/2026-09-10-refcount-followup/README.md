# Refcount follow-up — 2026-09-10

User resumed after the historical 5% checkpoint and requested no further
quota polling or correctness suites. This receipt supersedes the pending-work
state in `checkpoint.json`, which remains an immutable historical receipt.

The retained core and gateway commits remain `23dec4e9` and `8e0e72f`.
No implementation candidate was promoted, installed, committed or pushed.
The original speed improvements remain intact.

## Measurements

Each experiment rotates retained native, candidate native and CPython asyncio:
concurrency 100, child wait 0 ms, 100,000 requests per run, 5 repetitions.
These are handler batches, not live HTTP. Intrinsic work checks remained on.
The paired column is the median of candidate/control ratios within each repeat;
instructions compare process medians and include startup and warmups.

| Experiment | Retained QPS | Candidate QPS | asyncio QPS | Paired QPS change | Instruction change |
|---|---:|---:|---:|---:|---:|
| direct-release | 80,093 | 80,568 | 79,256 | +0.14% | -0.19% |
| immortal-order | 81,438 | 82,039 | 85,148 | +0.74% | -0.54% |
| cache1024 | 80,350 | 80,829 | 83,730 | +0.60% | -0.73% |

The small changes do not establish a substantial throughput gain. Absolute
QPS across separate experiments is not a causal comparison. The last two
candidate medians did not exceed their same-run asyncio median. Native median
peak RSS was approximately 53.6 MiB in these shorter runs; this is not directly
comparable to the longer README workload's RSS. Raw runs are adjacent files
`../2026-09-10-{direct-release,immortal-order,cache1024}-runtime.json`.

- Direct release passes terminal values instead of storing and reloading a
  prepared record. Kept only as a patch; no new cleanup/GC suite was run.
- Immortal order returns before special-object classification, after pointer
  and type checks. Kept only as a patch.
- Cache1024 expands the exact positive cache from 2 to 8 KiB while retaining
  each hit's acquire LIVE check. The capacity change is independent of the
  two refcount experiments. Kept only as a patch.

After inlining, existing owned mem2reg, sroa and instsimplify are all no-ops
on the actual retained optimized IR. Another simplifycfg sweep removes 54
loads, 18 stores, 6 calls and 58 branches; its candidate was emitted but not
executed. This does not establish a missing memory-pass deployment benefit.

## Reproduction and scope

`comparisons.json` records paired ratios and decisions. Each experiment folder
contains its patch, construction script, build report and watchdog commands.
Those scripts preserve the original local artifact layout under
`benchmarks/build/2026-09-09-runtime-followup`; they are build receipts, not
standalone replacements for the public `benchmarks/reproduce.py` command.
Construction uses the same application objects, frozen owned pass source and
external LLVM O0 emission as the retained experiment. Runtime rebuilds use
compiler checksum `a92b2af96ce95efe8ded06c440b8f8349f0ba8cab8f3ec814a858fcfe4db594c`.
Performance runs use the core lock and capped process-tree watchdog.
No new GC0–4, non-HTTP, native bootstrap or live HTTP/HTTPS qualification ran.

The fresh retained-runtime profile remains the useful owner evidence:
`py_decref` 10.53%, `py_incref` 7.35%, exact object-start validation 9.70%
of 2,516 leaf samples. Further work should reduce repeated operations in
these paths rather than keep tuning branch order or cache size without a
larger measured effect. Full compiler peak memory and native-direct worker
Bus error remain separate unresolved core work.
