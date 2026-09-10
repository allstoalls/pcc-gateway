# The public reproduction, from a clean tree — 2026-09-10

`benchmarks/reproduce.py` is the command the product README points at, so it
is the only number that matters to anyone outside this checkout. Before this
run it could not complete: a compiler regression on 2026-09-09 had left two
freestanding runtime modules uncompilable and a container-literal store
over-releasing, so a from-scratch runtime build either failed outright or
produced a runtime that aborted on `import io`.

This receipt is that command completing, and the figures the product README
now publishes.

## Result

200,000 requests per repeat, seven rotating repeats, concurrency 100, zero
child wait, under the core performance lock and a capped process-tree
watchdog.

| | pcc native | CPython asyncio |
|---|---:|---:|
| Median requests/s | **86,862** | 84,456 |
| Paired vs asyncio | **+2.27% median, 6 of 7 repeats, worst −0.18%** | — |
| Median delta | **+2.85%** | — |
| Instructions | 3.827e10 | 3.202e10 |
| Cycles | 7.752e9 | 7.283e9 |
| Median peak RSS | 37.1 MiB | 34.9 MiB |

Against what the README claimed before this run — 85,665 against 82,716 — the
native throughput is **higher** (86,862) and peak RSS is **identical** (37.1
MiB). The margin over asyncio is slightly smaller because asyncio itself
measured 2.1% faster in this run; that is run-to-run variance, and the paired
column is the part that is causal within a run.

Memory, same protocol, `/usr/bin/time -l`:

| Requests | pcc native | CPython asyncio |
|---:|---:|---:|
| 10,000 | **6.1 MiB** | 27.8 MiB |
| 100,000 | **21.0 MiB** | 30.9 MiB |
| 200,000 | 37.1 MiB | 35.0 MiB |
| 400,000 | 69.8 MiB | **44.3 MiB** |

Native starts at less than a quarter of asyncio's footprint and grows about
163 bytes per retained request against asyncio's 38, so it uses less memory up
to roughly 175,000 requests and more beyond.

## Correctness came with it

`reproduce.py` runs the GC0–4 gates itself as part of the build step. On this
from-scratch runtime: **60 gate runs, zero failures** (`build-report.json`) —
three programs, four compilation arms, `PCC_GC_BACKEND=0..4`. Every earlier
gate run in this series merged pre-regression object IR; this one did not.

## What made it reproducible

Three fixes in core, each attributed by revert rather than by inference:

1. Freestanding modules stopped emitting managed-runtime references, which
   restored from-scratch runtime builds. Verified as a restoration: 60 of 61
   freestanding modules reproduce the `ir_sha256` recorded in the committed
   archive provenance byte-for-byte, and the one difference is the allocator
   this session deliberately optimized.
2. A container literal's stored value is no longer over-released. A module
   registering itself as `{"source": <self>}` holds a borrowed self-reference;
   the extra release drove it to refcount 0 while its own slot still pointed
   at it, and `py_dealloc_dict` tripped its fail-closed guard. `test_py_corpus`
   went 177 failed to 177 passed.
3. A return annotation that pcc's own inference rejects was removed from the
   frontend, which had broken collection of the entire core suite.

And one documentation fix that matters more than it looks:
`benchmarks/README.md`'s prepare step now forces `make -B`. Every runtime
module is compiled by the pcc frontend, and `make` has no dependency edge from
the frontend to `build_py/*.o`. That gap is why the regression survived a day
unnoticed and why the numbers published before this run described a runtime
that could no longer be built. Without `-B`, the identity you record is not
the identity you measured.

## Scope

Handler batches on one carrier, not live HTTP; sockets, compilation and
startup are excluded, and peak RSS includes warmups and the 200,000 retained
latency samples. Live HTTP, live HTTPS, non-HTTP workloads and native
bootstrap remain separate validation scopes and did not run here.

Raw run: `comparison.json`. Build and gate evidence: `build-report.json`
(`source_hashes` reduced to a count and digest to keep the receipt small).
