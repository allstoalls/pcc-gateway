# Object-start inlining — 2026-09-10

The predecessor session ran out of budget mid-experiment. Its last recorded
intent was to split the object-address validation, and its runtime build had
just failed: a freestanding module requires `@c_abi_export` on every function,
and the newly outlined private slow path had none. Adding that one decorator
was the only change made to its candidate. The experiment was then finished,
extended twice, and promoted.

Unlike the predecessor receipt, correctness was **not** waived here. GC0–4,
structured failure cleanup and the core weakref/resurrection/refcount
regression all ran on the promoted candidate.

## What was promoted

Owner: `pcc/py_runtime/py/freestanding_allocator.py` in core, applied to the
worktree and **not committed**. Exact diff in `runtime.patch`.

1. **Split the hot predicate.** `pcc_gc_granule_is_object_start` kept only the
   exact-cache hit; the descriptor and radix validation moved to
   `_granule_object_start_uncached`. Every check keeps its original order. The
   point is size: the hit path is now small enough for the existing
   `inline-defined` pass to place it in its callers.
2. **Seed the cache where the answer is already known.** Every allocation
   reaches `pcc_gc_granule_object_publish`, which calls `_granule_object_slot`
   and so has *just proved* the cell that the predicate would recompute on a
   first probe. The publish now writes the exact positive cache entry.
3. **Grow the exact object cache** from 256 to 8192 entries (64 KiB).

Each hit still acquire-loads the LIVE lifecycle word, so an entry left behind
by a retired cell answers −1, never a false positive.

## Why this worked where branch and cache tuning did not

The predecessor measured three candidates at +0.14%, +0.74% and +0.60% and
promoted none. Two things changed.

The predicate was one fused function that the inliner refused, so **every one
of its 130 call sites paid a call, a frame and root bookkeeping** to answer a
question that is two loads on a hit. Splitting it removed that, and the IR
shows it: 130 predicate calls became 84 plus 47 outlined miss calls, and the
exact-cache global went from 3 references to 49 — the probe was inlined into
46 further sites. The gain landed in **cycles (−5.0%), not instructions
(−0.20%)**, exactly as removed call and frame overhead should.

The split then created something that did not exist before: **a place where a
check is free on the hit path.** That is what let the other two changes pay.
It also explains the earlier `256 → 1024` result — measured inside the fused
function, where call cost masked the miss.

The profiles drove the last step. After the split the outlined miss path was
5.0% of samples, and after seeding it was still 5.8% — seeding did not lower
it, because the miss callers are steady-state `store_ptr`, `dealloc_list`,
`instance_get_field` and `release`, not first touches. The table memoizes an
*address*, so allocation churn sets its miss floor and 256 entries were
thrashing under a 100-way concurrent working set. Capacity was then measured
rather than assumed.

## Measurements

Rotating arms, concurrency 100, child wait 0 ms, under the core performance
lock and a capped process-tree watchdog. Handler batches, not live HTTP;
intrinsic work checks on. Paired columns are per-repeat ratios, so they are
causal within a run; absolute QPS across runs is not.

### Promotion chain (100,000 requests × 5)

| Step | Paired QPS vs previous | Paired instructions vs previous | Note |
|---|---:|---:|---|
| split vs retained | +3.65% (5/5) | −0.20% (5/5) | cycles −5.0% |
| publish-seed vs split | +1.68% (3/5) | **−0.41% (5/5)** | promoted on the instruction reduction |
| 8192 entries vs seed | +0.51% (3/5) | **−1.49% (5/5)** | best cycles of the sweep |
| 65536 entries vs seed | −0.03% (2/5) | −2.01% (5/5) | **DENIED** |

65536 entries removed more instructions yet regressed cycles against 8192
(4.008e9 vs 3.959e9): a 512 KiB table stops being data-cache resident, so the
extra saving does not convert.

### Claim-grade confirmation (200,000 requests × 7 — the public README protocol)

| | retained | promoted | asyncio |
|---|---:|---:|---:|
| Median QPS | 81,569 | **86,264** | 83,945 |
| Paired QPS vs retained | — | **+5.62%, 7/7, worst +4.80%** | — |
| Paired QPS vs asyncio | — | **+4.01%, 7/7, worst +1.68%** | — |
| Instructions | 3.877e10 | 3.796e10 (−2.08%, 7/7) | 3.202e10 |
| Cycles | 8.271e9 | 7.830e9 | 7.344e9 |
| Median peak RSS | 102.8 MiB | 102.9 MiB | 34.9 MiB |

Raw runs: `../2026-09-10-{object-start-split,publish-seed,cache-sweep}-runtime.json`,
`../2026-09-10-{publish-seed,cache8k}-confirm.json`. Build reports, measure
scripts, gate reports and both profiles are adjacent files.

## Correctness

`benchmarks/combined_runtime.py --extra-module freestanding_allocator` on the
candidate archive, for the split and again for the promoted 8192-entry
candidate. Three programs — the handler benchmark, the structured
failure-cleanup fixture, and core's own weakref/resurrection/refcount
regression with `VERIFY_CHECKS=1` — across four compilation arms and
`PCC_GC_BACKEND=0..4`. **60 runs per candidate, all passed**
(`gates-split.json`, `gates-cache8k.json`).

Live HTTP, live HTTPS, non-HTTP workloads and native bootstrap remain separate
validation scopes and did not run.

## Open, and one pre-existing defect found

**Memory is still the front that is not won.** 102.9 MiB against 34.9 MiB
(2.95×), unchanged by this work. Throughput now leads asyncio on every paired
repeat; memory does not, so GC0 is not yet a comprehensive win.

**The work gap remains real.** The promoted runtime still executes 18.6% more
instructions and 6.6% more cycles than asyncio for the same requests, and
leads on QPS through concurrency rather than through less work. `py_decref`
and `py_incref` are together about 18% of leaf samples and are the largest
remaining owner; `pcc_gc_index_py_remove`/`_insert` add ~3%, the graph-lock
fallback ~2%, and `_tlv_get_addr` ~2%.

**Pre-existing and independent of this change:** `py/freestanding_mem_str.py`
does not compile from unmodified core `23dec4e9` —
`freestanding module emitted managed-runtime reference in define external void
@bzero(ptr %dst, i64 %size): call void @pcc_gc_release(...)`. It reproduces
with the untouched file, so it is not caused by this work, but it blocks every
from-scratch runtime rebuild. That is why the focused granule pytest gates,
whose fixture rebuilds the shared runtime, could not run and the GC0–4
evidence above goes through the incremental archive instead. Reproduce from
`pcc/py_runtime`:

```bash
pcc --python-library --emit-llvm=/tmp/x.ll py/freestanding_mem_str.py
```

Full compiler peak memory and the native-direct worker Bus error remain
unresolved from earlier sessions.

## Predecessor experiments that were measured but never written up

The predecessor's own receipt (`../2026-09-10-refcount-followup/README.md`)
stops at three rejected candidates. Three more had already run, and their raw
results were left in `benchmarks/results/` unrecorded. None is promoted; they
are listed so the series is complete and not repeated.

| Experiment | Paired QPS vs retained | Paired instructions | Raw result |
|---|---:|---:|---|
| backend-once | +2.74% (4/5) | **+0.40%** (worse) | `../2026-09-10-backend-once-runtime.json` |
| backend-split | +1.61% (3/5) | −0.70% | `../2026-09-10-backend-split-runtime.json` |
| early-cse | +2.57% (5/5) | −0.03% | `../2026-09-10-early-cse-runtime.json` |

`early-cse` is the local common-subexpression pass the predecessor described
as reducing IR while barely moving executed instructions; these numbers agree,
and its candidate lost to asyncio in 4 of 5 repeats. None reaches the
promoted chain's effect and none was carried forward.
