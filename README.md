# pcc-gateway

An HTTP/1.1 gateway and web framework written in Python for
[pcc](https://github.com/allstoalls/pcc), with native virtual threads,
structured concurrency, streaming, routing, reverse proxying, DNS and a TLS
provider ABI. Compiled applications run without libpython.

## Run

Install a qualified `pcc1` through the
[core installation guide](https://github.com/allstoalls/pcc#one-installed-compiler-for-multiple-projects),
then run from this checkout:

```bash
pcc1 local_http_app.py -o local_http_app
./local_http_app

pcc1 dashboard_app.py -o dashboard_app
./dashboard_app
```

Use the shared `~/.local/bin/pcc1` through PATH. The compiler resolves
`pcc_gateway/` from the checkout; `PCC_PACKAGE_SITE` is not needed here.
Default pcc1 options are sufficient.

The dashboard uses `TaskScope` to run two child operations concurrently,
join their results, and cancel/drain children on failure. See
[dashboard_app.py](dashboard_app.py) for the complete example.

## Develop and test

Clone `pcc` beside `pcc-gateway`. Both projects use **Python 3.15.0rc1**;
uv resolves the compiler from `../pcc`.

```bash
uv sync --locked
uv run pcc --backend self --python-libpython off local_http_app.py -o local_http_app
uv run pytest -q

# Compile and execute examples with both pcc and pcc1:
uv run pytest -q -x -m integration tests/test_native_examples.py
```

Native integration tests run separately;
`PCC_TEST_PCC1=/path/to/pcc1` selects a candidate compiler.

## Performance

### Latest measurement — 2026-09-14

The [six-arm comparison](benchmarks/results/2026-09-14-six-arm/README.md)
completed **180 validated runs** on Apple M2 Max, macOS 26.5.1 and
CPython 3.15.0rc1. These are handler requests/s, excluding HTTP sockets,
compilation and startup. Each request runs two child tasks, joins them and
validates the same JSON response.

Zero child wait, 5,000 requests per repeat, five rotating repeats; medians:

| Implementation | C1 requests/s | C10 requests/s | C100 requests/s | C100 peak RSS |
|---|---:|---:|---:|---:|
| host pcc · virtual threads | 13,268 | 18,577 | 18,075 | 6.42 MiB |
| pcc1 · virtual threads | 13,309 | 18,419 | 18,092 | 6.38 MiB |
| host pcc · asyncio/vthread prototype | 7,335 | 9,292 | 9,087 | 30.03 MiB |
| pcc1 · asyncio/vthread prototype | 7,295 | 9,398 | 9,087 | 30.05 MiB |
| CPython asyncio TaskGroup | 8,725 | 49,056 | 82,007 | 27.67 MiB |
| CPython asyncio gather | 8,836 | 46,670 | 78,105 | 27.70 MiB |

At C100, pcc1 virtual threads reached **18,092 requests/s**, versus **82,007
for asyncio TaskGroup**; the high-concurrency performance target remains open.
At C1, pcc1 reached 13,309 versus asyncio's 8,725. With 100 ms child waits,
C100 medians were 941 requests/s for pcc1 and 971 for asyncio TaskGroup.
The full matrix, latency distributions and process counters are in the
[raw results](benchmarks/results/2026-09-14-six-arm/comparison.json).

The host arm uses the current frozen compiler source; the native arm uses
the latest available experimental pcc1 U binary, which predates the final
closure-cell fix and has not passed full Stage1 qualification. Both compile
fresh applications using the self backend and the same pinned, prebuilt
pcc-Python runtime; all 171 runtime objects were self-emitted. Application IR
passes use the default `mem2reg,sroa` selection. Runtime construction was not
repeated in this run. Native execution uses GC0; this is not a new five-GC or
cold-toolchain qualification. [Artifact identities and limits](benchmarks/results/2026-09-14-six-arm/README.md#toolchain-and-scope)
record these boundaries.

Compilation took 8.49 s / 52.68 s for the ordinary host-pcc / pcc1 arms and
8.37 s / 54.79 s for their prototype arms, all within the unchanged 300 s limit.
The asyncio/vthread arm is a `run`/`gather`/`sleep` prototype, not full asyncio
compatibility. Peak RSS includes startup, warmups and retained latency samples.

### Historical LLVM-assisted reference — 2026-09-10

The result below is a **historical LLVM-assisted reference**, recorded on
2026-09-10. LLVM merged and emitted the runtime; pcc ran the owned IR passes
and emitted/linked the application. It does **not** demonstrate that the
LLVM-free toolchain outperforms asyncio, or describe the current default.
That performance target remains open.

On Apple M2 Max, macOS 26.5.1 and Python 3.15.0rc1, this reference runtime
reached **86,862 requests/s**, versus **84,456 for asyncio** — a
**2.9% higher median in this run**, and higher in six of the seven paired
repeats.

| Implementation | Median requests/s | Median peak RSS |
|---|---:|---:|
| pcc application + LLVM-emitted reference runtime | **86,862** | 37.1 MiB |
| CPython asyncio | 84,456 | 34.9 MiB |

These came from `benchmarks/reproduce.py` and the compiler/runtime identities
in the linked receipt. Rerunning against another source or runtime measures
that configuration; it does not reproduce the recorded artifact automatically.

Measured at concurrency 100, zero child wait, 200,000 requests per repeat and
seven rotating repeats. Each request runs two child tasks, joins them and
validates its JSON result. This measures handler throughput on one carrier /
event loop; HTTP sockets, compilation and startup are excluded.
Peak RSS includes warmups and storage of the 200,000 latency measurements.

Memory depends on how much a run retains. This historical runtime started smaller than
asyncio and grows faster, so it uses **less** memory up to roughly 175,000
requests and more beyond it:

| Requests | pcc with reference runtime | CPython asyncio |
|---:|---:|---:|
| 10,000 | **6.1 MiB** | 27.8 MiB |
| 100,000 | **21.0 MiB** | 30.9 MiB |
| 200,000 | 37.1 MiB | 35.0 MiB |
| 400,000 | 69.8 MiB | **44.3 MiB** |

For the reference experiment, first prepare the [matching core runtime and IR](benchmarks/README.md#prepare-the-runtime), then run:

```bash
env -u LC_ALL uv run python benchmarks/reproduce.py \
  --pcc-source ../pcc \
  --runtime-archive ../pcc/pcc/py_runtime/libpy_runtime_pcc_py.a \
  --output-dir benchmarks/build/reproduce
```

Use a fresh output directory for each run. The runner builds the runtime
variants, checks GC0–4 behavior, and compares the optimized executable with
asyncio under time, memory and process-lifetime limits.

The runtime configuration, per-repeat results and correctness gates behind
these numbers are recorded in the
[reproduction receipt](benchmarks/results/2026-09-10-reproduce-clean/README.md),
with how the work got here in the
[throughput receipt](benchmarks/results/2026-09-10-object-start-inline/README.md)
and the [memory receipt](benchmarks/results/2026-09-10-ownership-leaks/README.md).
See [benchmark methods](benchmarks/README.md) for reproduction and
[non-HTTP comparisons](benchmarks/results/2026-09-09-runtime-progress/non-http.json)
for object, container and string workloads.
