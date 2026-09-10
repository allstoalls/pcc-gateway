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
with no libpython fallback anywhere, and still does not complete a run**: one
blocker remains, reproduced in 18 lines below.

Getting from "does not compile" to "compiles clean and runs into asyncio" took
seven fixes in core, each with its own reproduction:

| Blocker | Fix |
|---|---|
| `TaskGroup.create_task` forwarded `**kwargs`; a `**` expansion needs a statically dict-typed operand | written out as the keyword-only signature the loop method already uses |
| `await` inside an `except` handler got no delegation frame slot | `ExceptHandler` added to the generic AST field table; every collector built on it had been skipping handler bodies |
| `heapq` is CPython's, and it opens `from _heapq import *` | pure Python `heapq`, 1,989 differential assertions against CPython, zero mismatches |
| `gather` awaited in argument position (`out.append(await child)`) | bound to a local; the receiver is not spilled across the suspension, recorded as a compiler gap with a 16-line repro |
| `contextvars.copy_context()` resolved through CPython, stubbing `Task.__init__` | `contextvars` given a compiled provider, joining platform and subprocess |
| a field initialised `self._x = None` stayed NoneType forever, so every read fell back | a non-`__init__` write widens it to Dyn; the cleanup-sentinel protection it was guarding is kept |
| `[None]` typed its element NoneType, so `_BOX = [None]` made every reader NoneType | an all-`None` list literal gets a Dyn element, as `[]` already did |

`benchmark_asyncio_gather.py` itself needed the same await-in-argument rewrite
(`samples.extend(await batch(...))`). Both arms run the identical rewritten
source, so the comparison is unaffected.

## The NoneType root cause is fixed

Two narrow inference rules in core, `aebb8cfb`:

- a field the constructor only initialises to `None` and that another method
  writes is Dyn — the skip that made the constructor's `None` final exists to
  stop a cleanup sentinel erasing a real type, and still does, because the
  widening applies only when the known type is NoneType
- a list literal whose elements are all `None` has a Dyn element type, which is
  what the line above it already gives `[]`

**Every libpython stub in asyncio is gone**, including `_run_once`, and so is
the gateway's own `pcc_gateway.dns.step`. Reproductions kept in `repro/`:
`none_attribute_method.py` (a guarded `self._x.method()` after `self._x = None`)
and `none_list_box.py` (the `_BOX = [None]` mutable-cell idiom feeding an
attribute). Both compile natively and match CPython now.

## One blocker remains, and there is still no native throughput number

`repro/super_keyword_only.py`, 18 lines:

```python
class Base:
    def __init__(self, *, loop=None) -> None:
        self.loop = loop

class Child(Base):
    def __init__(self, coro, *, loop=None) -> None:
        super().__init__(loop=loop)
        self.coro = coro
```

CPython prints `7 42`; native raises **`TypeError: native function got too many
positional arguments`**. `super().__init__(kw=value)` against a keyword-only
base parameter is lowered as a positional call, and the runtime binder in
`py_func.py` correctly refuses it — the signature it is handed has two formals
of which one is not positional, and two positionals arrive.

The failure is reached through `asyncio.run` -> `run_until_complete` ->
`ensure_future` -> `loop.create_task`, and lldb confirms the binder is entered
from inside `_Loop.create_task` rather than from a misdispatch: the correct
method is called. Making `Future.__init__`'s `loop` positional-or-keyword did
NOT clear it, so the exact call inside `create_task` has not been pinned; the
18-line reproduction is the reliable artifact, not that hypothesis.

Until it is fixed there is **no throughput figure for the pcc-compiled asyncio
arm**. Running the arm under `--python-libpython=on` would produce a number,
but not a native one, so it is not reported.

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
