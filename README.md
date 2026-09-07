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
Default pcc1 options are sufficient. The tested compiler candidate and
installation qualification status are recorded in the [benchmark notes](benchmarks/README.md).

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

The default suite passes **290 tests**. Native integration tests run separately;
`PCC_TEST_PCC1=/path/to/pcc1` selects a candidate compiler.

## Performance (2026-09-08)

Apple M2 Max, macOS 26.5.1, Python 3.15.0rc1, self backend with the owned
`mem2reg,sroa` IR pass tier and `PCC_GENERATOR_FIRST_ENTRY_INIT=1
PCC_FAST_COMPLETED_CONTINUATIONS=1 PCC_DIRECT_GENERATOR_TASKS=1`. Median
handler QPS over five repeats, one run, all arms measured together;
compilation, startup and HTTP sockets excluded. Concurrency is the number of
requests started per batch, and the batch finishes before the next begins.

| Child wait (ms) | Concurrency | pcc QPS | pcc1 QPS | LLVM-O2 runtime QPS | asyncio QPS |
|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 27,898 | 31,728 | 30,411 | 8,802 |
| 0 | 10 | 39,587 | 45,762 | 41,592 | 50,544 |
| 0 | 100 | 39,097 | 46,551 | 43,056 | 80,502 |
| 100 | 1 | 10.0 | 10.0 | 10.0 | 9.9 |
| 100 | 10 | 99.5 | 99.6 | 99.6 | 98.7 |
| 100 | 100 | 972.3 | 977.5 | 974.2 | 976.8 |

`pcc1` is the native self-hosted compiler and is the fastest pcc arm, 19% ahead
of the host compiler at concurrency 100.

The `LLVM-O2 runtime` column is not an LLVM backend. Every arm emits its code
through the self backend; that column only replaces the owned IR pass tier with
LLVM `default<O2>` over the same 170 runtime archive members, which is the only
way to vary the optimizer without also varying the code generator. `pcc1` is
8.1% ahead of it at concurrency 100, so the owned pass tier now beats LLVM O2
on this runtime.

Against asyncio, pcc is 3.2x to 3.6x faster at concurrency 1 and 1.73x slower
at concurrency 100. Under a real child wait every arm lands within 0.3%,
because the wait dominates. Peak RSS is 8.2 MiB against asyncio's 27.6 MiB.

```bash
PCC_GENERATOR_FIRST_ENTRY_INIT=1 PCC_FAST_COMPLETED_CONTINUATIONS=1 \
PCC_DIRECT_GENERATOR_TASKS=1 uv run python benchmarks/compare.py \
  --pcc1 /path/to/pcc1 --output benchmarks/results/my-comparison.json
```

[Receipts](benchmarks/results/) and [benchmark notes](benchmarks/README.md).
Optimization is tracked in [pcc #188](https://github.com/allstoalls/pcc/issues/188).
