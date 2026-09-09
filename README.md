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

On Apple M2 Max, macOS 26.5.1 and Python 3.15.0rc1, the latest optimized native
runtime reaches **79,801 requests/s**, versus **76,504 for asyncio** — a
**4.3% higher median in this run**.

| Implementation | Median requests/s | Median peak RSS |
|---|---:|---:|
| pcc optimized native runtime | **79,801** | 102.8 MiB |
| CPython asyncio | 76,504 | 34.9 MiB |

Measured at concurrency 100, zero child wait, 200,000 requests per repeat and
seven rotating repeats. Each request runs two child tasks, joins them and
validates its JSON result. This measures handler throughput on one carrier /
event loop; HTTP sockets, compilation and startup are excluded.
Peak RSS includes warmups and storage of the 200,000 latency measurements.

To reproduce, first prepare the [matching core runtime and IR](benchmarks/README.md#prepare-the-runtime), then run:

```bash
env -u LC_ALL uv run python benchmarks/reproduce.py \
  --pcc-source ../pcc \
  --runtime-archive ../pcc/pcc/py_runtime/libpy_runtime_pcc_py.a \
  --output-dir benchmarks/build/reproduce
```

Use a fresh output directory for each run. The runner builds the runtime
variants, checks GC0–4 behavior, and compares the optimized executable with
asyncio under time, memory and process-lifetime limits.

The optimized runtime configuration and detailed results are recorded in the
[benchmark report](benchmarks/results/2026-09-09-owned-runtime-exact-cache-long.json).
See [benchmark methods](benchmarks/README.md) for reproduction and
[non-HTTP comparisons](benchmarks/results/2026-09-09-runtime-progress/non-http.json)
for object, container and string workloads.
