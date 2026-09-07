# Owned mem2reg in the runtime archive: gateway runtime A/B (2026-09-08)

Single variable. Both arms were produced by wiping `pcc/py_runtime/build_py/*.o`
and rebuilding the runtime once through the ordinary production path, one with
`PCC_RUNTIME_PYTHON_IR_PASSES=off` and one with `default`. All 170 archive
members in both arms carry the same `codegen_checksum` (`ae203824aa5d`), so the
compiler is identical and only the pass mode differs. Measured with
`benchmarks/runtime_ab.py`, `benchmark_native.py`, concurrency 100, delay 0,
5 repeats of 5000 requests, one host compiler, under the core performance lock.

## What changed in the compiler

`pcc/native_ir/mem2reg.py` is new: the full Cytron algorithm (dominance
frontiers, phi placement, dominator-tree renaming) over pcc's own IR model,
with no llvmlite. The default `mem2reg,sroa` manifest used to be claimed by a
textual single-block subset that could not promote anything needing a phi, and
because the self backend is the default, that subset was what every self compile
and every runtime archive member actually got.

Archive IR, 170 members:

```
                              alloca    load   store
before (textual subset)        17218   71035   34837
after  (owned native_ir)        1730   14781    7382
LLVM function(mem2reg,sroa)     1728   14777    7376
```

90.0% of the allocas are gone, and the owned pass lands within two allocas of
LLVM's own mem2reg+sroa on real emitted IR.

## Throughput

```
arm                                 QPS median   instructions/request
control  (passes off)                   24890                 481998
candidate (owned mem2reg,sroa)          38747                 373890
CPython asyncio                         77150                 227080
```

+55.7% QPS, -22.4% instructions per request. The gap to asyncio narrows from
3.10x to 1.99x; asyncio is still ahead.

Receipt: `2026-09-08-owned-mem2reg-runtime-ab.json`.

## Extending the owned pass list

A second A/B added the owned `instsimplify`, `instcombine` and `dce` on top:

```
arm                                 QPS median   instructions/request
mem2reg,sroa                            39812                 373570
+ instsimplify, instcombine, dce        40981                 371403
CPython asyncio                         86058                 227137
```

+2.9% QPS for a 9.8% smaller static archive (369341 -> 333311 instruction
lines), so the whole runtime win is mem2reg. The default manifest was left at
`mem2reg,sroa`.

The owned `simplifycfg` cannot be added yet: after a memory-promotion pass it
emits a duplicate local value name and LLVM refuses the module, which fails the
archive build on `py_int_parse.o`. Recorded in the core repository as
`docs/investigations/owned-simplifycfg-value-namespace.md`. It reproduces from
the old textual tier too, so it predates this work.

Receipt: `2026-09-08-owned-five-pass-runtime-ab.json`.

## Claim boundary

These are host-compiler numbers for the runtime the gateway executes. They do
not prove a pcc1 compile-throughput change, a bootstrap fixed point, or
five-GC equality; those need their own gates.
