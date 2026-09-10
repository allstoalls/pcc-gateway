# The pcc-compiled asyncio arm — 2026-09-10

Everything published so far compares **two different programs**: pcc running
`benchmark_native.py` (TaskScope, virtual threads) against CPython running
`benchmark_asyncio.py` (asyncio). That answers "which stack is faster", not
"is pcc's async faster than CPython's", because the sources differ.

`benchmark_asyncio_gather.py` closes that gap: one asyncio source, an
`asyncio.gather` shape matching the existing two-child/JSON-validate request,
run twice — once compiled natively by pcc, once by CPython.
`benchmarks/artifact_compare.py` grew `--asyncio-script` so the CPython arm
can be pointed at the same file a native arm was built from.

## Status

The harness is finished and the CPython arm runs. **The native arm compiles
but does not yet complete a run**, and what remains is one root cause rather
than a list.

Getting from "does not compile" to "compiles and runs into asyncio" took five
fixes in core, each with its own reproduction:

| Blocker | Fix |
|---|---|
| `TaskGroup.create_task` forwarded `**kwargs`; a `**` expansion needs a statically dict-typed operand | written out as the keyword-only signature the loop method already uses |
| `await` inside an `except` handler got no delegation frame slot | `ExceptHandler` added to the generic AST field table; every collector built on it had been skipping handler bodies |
| `heapq` is CPython's, and it opens `from _heapq import *` | pure Python `heapq`, 1,989 differential assertions against CPython, zero mismatches |
| `gather` awaited in argument position (`out.append(await child)`) | bound to a local; the receiver is not spilled across the suspension, recorded as a compiler gap with a 16-line repro |
| `contextvars.copy_context()` resolved through CPython, stubbing `Task.__init__` | `contextvars` given a compiled provider, joining platform and subprocess |

`benchmark_asyncio_gather.py` itself needed the same await-in-argument rewrite
(`samples.extend(await batch(...))`). Both arms run the identical rewritten
source, so the comparison is unaffected.

## What is left is one root cause

**A value whose inferred type is NoneType does not widen when something
assigns it a real object, and using it as an object falls back to libpython.**
The IR says so directly: `py_cpy_from_pcc_none(%self._loop)`.

It accounts for all of the remaining failures:

- five asyncio stubs — `self._loop`, `self._waiter`, `self._on_completed_fut`,
  `self._parent_task`, all initialised to `None` in `__init__`
- `loop.create_task(awaitable)` raising "native function got too many
  positional arguments": `get_event_loop()` returns `_LOOP_BOX[0]` where
  `_LOOP_BOX = [None]`, so the loop is NoneType and the method call
  misdispatches to the module-level `create_task`, which takes one positional
- the gateway's own `pcc_gateway.dns.step`, via `py_cpy_from_pcc_none(%self.server)`

Reproduces in 30 lines: `__init__` sets `self._x = None`, a setter assigns a
real object, and a guarded `self._x.method()` is enough. Copying the attribute
to a local and calling a *builtin* on it compiles natively; calling a method
on the attribute does not, and annotating the setter's parameter does not
change the outcome.

Class field types come from `_class_fields_from_def` and `_append_field` in
`pcc/py_frontend/type_infer.py`, whose merge is last-write-wins with no
widening. Since annotating the setter changes nothing, the setter's assignment
is evidently not reaching that merge at all — which of the two it is has not
been established, and widening a core inference rule wants its own gate run.

## Running it

```bash
# CPython arm alone, to check the workload
python3 benchmark_asyncio_gather.py 100 0 200 --summary

# once the native arm runs: same source, both arms
env -u LC_ALL uv run python benchmarks/artifact_compare.py \
  --native pcc_asyncio=<native binary built from benchmark_asyncio_gather.py> \
  --asyncio-script benchmark_asyncio_gather.py \
  --requests 200000 --repeats 7 --output <result.json>
```

Native build line (needs the matching core runtime archive):

```bash
env PYTHONPATH=../pcc PCC_SOURCE_ROOT=../pcc PCC_REPO_ROOT=../pcc \
  PCC_RUNTIME_ARCHIVE=../pcc/pcc/py_runtime/libpy_runtime_pcc_py.a \
  PCC_RUNTIME_CC=/usr/bin/false \
  python -m pcc --backend self --python-libpython=off --ir-scaffold=on \
  benchmark_asyncio_gather.py -o build/gather_native
```

`PCC_DEBUG_STRICT_NOLIB_STUB=1` with `PCC_PY_FRONTEND_JOBS=1` prints the
`py_cpy_*` call behind every fail-closed stub; without the serial frontend the
worker's diagnostic never reaches stderr.
