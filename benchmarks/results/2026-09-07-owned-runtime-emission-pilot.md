# Owned runtime emission pilot — 2026-09-07

**Reference correction:** the historical LLVM archive contains additional
diagnostic entrypoints in three modules; it is not a strict same-source arm.
The self-control/owned-pass comparison remains valid. Use the later
[same-IR optimizer/codegen matrix](2026-09-07-self-llvm-ir-codegen-matrix.json)
for backend attribution: its five LLVM objects match the exact source/IR
receipt used for the self inputs. Do not describe this first pilot as holding
all runtime source files identical across its LLVM/self arms.

[Raw results](2026-09-07-owned-runtime-emission-pilot.json). Darwin arm64,
CPython 3.15.0rc1, one carrier, GC0. Seven rotating repetitions, concurrency
100, zero wait, 20,000 measured requests per run: 28 runs and 560,000 validated
responses. Handler batches only; these are not HTTP socket QPS.

| Variant | Median QPS | Range |
|---|---:|---:|
| Self runtime emission, control | 19,763.3 | 19,394.1–20,069.7 |
| Self runtime emission, owned passes | 22,185.0 | 22,039.7–22,495.0 |
| Historical LLVM O2 runtime reference | 57,777.4 | 54,442.2–58,311.6 |
| CPython asyncio | 86,080.5 | 84,164.1–88,578.9 |

The owned passes improve self-control QPS by 12.3%; process instructions fall
5.1%. Process counters include startup and two warmup batches. Native artifacts
share the same two application PCOs. Five runtime modules differ: `py_obj`,
`py_list`, `py_gen`, `py_gc_backend`, `freestanding_gc_index_table`.

This is not a pcc-versus-pcc1 frontend comparison. Optimization and PCO emission
run in native tools with host Python/cc disabled and `PATH=/nonexistent`.
Host pcc-owned parsing, indexed encoding and Mach-O linking still run on
CPython. Other archive members are prebuilt, including historical LLVM-built
code. There is no full dependency-free runtime-build, full O2, installation
qualification or asyncio-win claim.

## Reproduce construction

Use [build_runtime_variants.py](../build_runtime_variants.py). It accepts an
explicit JSON manifest; paths below are placeholders for matching local
artifacts, not environment variables needed by applications:

```json
{
  "pcc_root": "/path/to/pcc",
  "pcc1": "/path/to/isolated/pcc1",
  "optimizer": "/path/to/native/pcc-opt",
  "runtime_archive": "/path/to/libpy_runtime_pcc_py.a",
  "reference_provenance": "Describe how the reference archive was built",
  "app_ir": ["/path/to/app-0.ll", "/path/to/app-1.ll"],
  "runtime_ir": {
    "py_obj": "/path/to/py_obj.input.ll",
    "py_list": "/path/to/py_list.input.ll",
    "py_gen": "/path/to/py_gen.input.ll",
    "py_gc_backend": "/path/to/py_gc_backend.input.ll",
    "freestanding_gc_index_table": "/path/to/freestanding_gc_index_table.input.ll"
  }
}
```

Generate application IR from `benchmark_native.py` with
`PCC_DEBUG_SELF_IR_DUMP_DIR` on a full self compilation. The core's
`scripts/probe_pcc1_self_runtime.py` can generate native runtime IR inputs.
Build `pcc/native_ir/driver.py` as the isolated native `pcc-opt`; the matching
uncommitted compiler fixes described in core's native-optimizer handoff are
required. Source-to-IR generation and the runtime archive are explicit inputs,
not secretly rebuilt by this script. Changing source/compiler inputs reruns
the same experiment but need not reproduce these exact numbers or hashes.

From the gateway repository (adjust the core path if it is not a sibling):

```sh
uv run python ../pcc/scripts/run_process_tree_sample.py \
  --result /tmp/runtime-build-monitor.json --samples /tmp/runtime-build-rss.tsv \
  --stdout /tmp/runtime-build.stdout --stderr /tmp/runtime-build.stderr \
  --cwd . --timeout 240 --max-tree-rss-bytes 4294967296 -- \
  "$PWD/.venv/bin/python" benchmarks/build_runtime_variants.py \
  --manifest /path/to/manifest.json --output-dir /tmp/runtime-variants
```

The builder refuses an existing output directory, denies LLVM imports in host
helpers, hashes inputs and checks they stay unchanged. It validates PCOs and
executes each linked workload. A verification rebuild with this retained
script produced byte-identical 12 PCOs and three programs relative to the
original pilot. [Build report](2026-09-07-owned-runtime-reproduction-build.json)
and [input manifest](2026-09-07-owned-runtime-reproduction-manifest.json) retain
the local artifact identities; these files do not bundle the toolchain binaries
or promise a clean-checkout turnkey build of this still-uncommitted experiment.

## Reproduce timing

```sh
uv run python benchmarks/artifact_compare.py \
  --native llvm-runtime-reference=/tmp/runtime-variants/reference-linked \
  --native self-runtime-control=/tmp/runtime-variants/self-control-linked \
  --native self-runtime-owned-passes=/tmp/runtime-variants/self-owned-linked \
  --build-report /tmp/runtime-variants/build-report.json \
  --concurrency 100 --delays 0 --requests 20000 --repeats 7 \
  --output /tmp/runtime-emission-timing.json
```

Use a previously unused output path. The script adds the current interpreter's
asyncio arm, validates counts and workload output, rotates order and checks
artifact hashes before/after timing. Use the repository's pinned interpreter.
