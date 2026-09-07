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

## Performance (2026-09-07)

Apple M2 Max, macOS 26.5.1, Python **3.15.0rc1**. Both native arms use the
same compiler source and runtime, including the latest task and ownership fixes.
Each request runs two child waits and validates the joined JSON result;
one carrier/event loop, five repeats. Figures are median handler QPS,
excluding HTTP sockets, compilation and startup.
Concurrency is the number of requests started per batch; the entire batch
finishes before the next begins.

| Child wait (ms) | Concurrency | pcc QPS | pcc1 QPS | asyncio QPS |
|---:|---:|---:|---:|---:|
| 0 | 1 | 32,569.7 | 31,741.6 | 9,255.1 |
| 0 | 10 | 47,676.3 | 46,705.4 | 49,385.8 |
| 0 | 100 | 49,087.9 | 48,457.6 | 86,611.5 |
| 100 | 1 | 10.0 | 10.0 | 9.9 |
| 100 | 10 | 99.2 | 98.9 | 98.4 |
| 100 | 100 | 942.5 | 941.6 | 945.7 |

At zero wait / concurrency 100, pcc1 is still **1.79× slower than asyncio**;
peak RSS is **7.98 MiB**, versus asyncio's **27.62 MiB**.
All **90 runs / 241,650 requests** passed output and sample-count checks.
System load varied during the run; use the recorded ranges when comparing results.

Reproduce with the checked-in scripts:

```bash
PCC_GENERATOR_FIRST_ENTRY_INIT=1 PCC_FAST_COMPLETED_CONTINUATIONS=1 \
PCC_DIRECT_GENERATOR_TASKS=1 uv run python benchmarks/compare.py \
  --pcc1 /path/to/qualified/pcc1 \
  --output benchmarks/results/my-comparison.json
```

See the [full results](benchmarks/results/2026-09-07-field-owners-three-way.md),
[raw samples](benchmarks/results/2026-09-07-field-owners-three-way.json) and
[benchmark notes](benchmarks/README.md) for latency, CPU/RSS, compiler/runtime
selection, profiling and earlier experiments. Optimization is tracked in
[pcc #188](https://github.com/allstoalls/pcc/issues/188).
