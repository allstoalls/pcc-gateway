# Per-request memory: compiler ownership leaks — 2026-09-10

Companion to `../2026-09-10-object-start-inline/`, which won throughput but
left peak RSS untouched at 2.96x asyncio. This receipt is the memory front.

## The gap was never baseline memory

| Requests | leaky | json fix | + clocks | + float literals | asyncio |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 9.4 MiB | 7.7 | 6.9 | **6.0** | 28.0 |
| 50,000 | 29.1 | 20.7 | 16.6 | **12.7** | 29.0 |
| 100,000 | 53.7 | 36.3 | 28.7 | **20.9** | 31.1 |
| 200,000 | 102.9 | 68.2 | 52.9 | **37.1** | 34.7 |
| 400,000 | — | — | — | 69.7 | 44.6 |

Native baseline memory was always the better one — 6.9 MiB against asyncio's
27.9 at 10k requests, a quarter of it. The entire loss was **per-request
growth**: 516 bytes per request against asyncio's 38. So the question was never
"why is the runtime fat", it was "what does each request retain".

With all three fixes that slope is 164 bytes, peak RSS at the 200k protocol
is 37.1 MiB against asyncio's 34.7 — **1.06x, from 2.96x** — and the crossover
moved from about 50k requests to about 215k.

## Diagnosis: measure live bytes, not RSS

RSS cannot distinguish reachable retention from mapped memory an allocator
never reuses. The runtime already accounts for both, so the probes read
`pcc_allocator_live_requested`, `pcc_allocator_live_usable`,
`pcc_allocator_mapped` and `py_gc_tracked_count` directly (`probes/`, built on
the pattern of `benchmarks/lifetime.py`).

`gc.collect()` freed **nothing** in every leaking case and returned 0, so the
retention was live refcounted objects — a missing release — not uncollected
cycles. `py_gc_tracked_count` stayed flat while live bytes grew, which said the
leaked objects were refcount-only and invisible to the tracing set. That is why
the existing live-object probe had reported "no leak".

A layer bisect then ran the same handler shape up to a cut point. Virtual
thread spawn, `TaskScope` fork/join/close and dict/list results leaked **zero**
bytes over 20,000 iterations each. All of it appeared at one line:
`json.dumps(data, sort_keys=True).encode()`.

## Three defects fixed

Both in core, applied to the worktree. Exact diffs in `frontend-json.patch`
and `frontend-clocks.patch`.

**1. json returns new references nobody released.** `json.dumps` leaked its
whole result string on every call — exactly `len + 41` bytes, confirmed by
length scaling: an 86-character result leaked 127 bytes and a 971-character
result leaked 1012, i.e. 885 more characters cost 885 more bytes.
`json.loads` leaked the whole parsed document, 907 bytes and two tracked
containers per call.

The cause is documented in the codebase already. `py_json_dumps/_ex/loads` all
return a NEW reference, but the ownership shape classifier sees only a DynType
Call on a module-level function and answers "not owned", so no release is
emitted. `_native_re_call_returns_owned_object` describes the identical defect
for the `re` lowerings, where it leaked 1.76 GB in a 300k-iteration match loop.
The fix uses the mechanism the same file already applies to `re.compile` and
`re.sub`: record the owner at emission. `json.load` additionally releases the
intermediate string `py_file_read_all` returns, pinned across the release so a
moving backend cannot relocate the parsed result underneath it.

**2. Clock reads leaked their float.** `native_modules.py` contained no
`_note_owned_object_value` call at all, so every module-level native function
it lowers that builds a new object leaked it. `time.perf_counter` is called
twice per request in the handler. `time.monotonic`, `time.time`,
`time.strftime` and `os.urandom` are the same shape and are fixed with it.

**3. Float literals were boxed on every evaluation.** `y = x - 0.5` leaked 24
bytes per iteration and `(x - 0.5) * 1000.0` leaked 48; the emitted IR showed
`py_float_from_f64` for the literal *inside* the loop body and never released.

The cause is a shape, not a typo: `marshal_to_object` returns either the
incoming pointer unchanged (borrowed) or a fresh box (owned) and the caller
cannot tell which — across **262 call sites**.

Rather than teach 262 sites to tell the difference, the literal stops needing
an object of its own. Each distinct float literal is now emitted as a
statically initialized immortal `PyFloatObject` in the data segment, pooled by
value and registered once by the same static-literal initializer that already
handles string literals — the pattern `_emit_str_literal` established. That
makes the ambiguity **harmless** instead of merely fixed at one caller:
refcount operations on an immortal are no-ops, so no call site had to change.
The emitted IR confirms it — the loop body has no `py_float_from_f64` call and
takes the address of
`@.pyfloat.obj.N = internal global {i64 1, i32 3, i32 1, double K}`.

Measured effect: `json.dumps` 127 → **0** B/call, `json.loads` 907 → **0** and
2 → **0** tracked objects, `time.perf_counter` 24 → **0**, `x - 0.5` 24 → **0**,
`(x - 0.5) * 1000.0` 48 → **0**, and the full gateway request path 127 → **0**.
Real-workload retention went 203 → 73.6 → 49.1 → **24.65** bytes per request
across the three fixes.

## Throughput did not pay for it

200,000 requests x 7 repeats, C100/0ms, same run
(`../2026-09-10-leakfix-confirm.json`):

| | retained | with all three fixes | asyncio |
|---|---:|---:|---:|
| Median QPS | 80,175 | **85,665** | 82,716 |
| Paired QPS vs retained | — | **+6.24%, 6/7** | — |
| Paired QPS vs asyncio | — | **+2.62%, 6/7** | — |
| Median QPS vs asyncio | — | **+3.57%** | — |
| Instructions | 3.877e10 | 3.827e10 (−1.29%, 7/7) | 3.205e10 |
| Median peak RSS | 102.8 MiB | **37.1 MiB** | 35.0 MiB |

Adding releases did not cost throughput. The first two fixes improved it —
fewer live objects means less allocator pressure and better locality, which
more than paid for the extra release calls. The float literal change is
throughput-**neutral** against that state (−0.17% paired, 3/7) while
consistently lowering instructions (−0.33%, all seven), because what it removes
is an allocation rather than instructions; its value is the 52.9 → 37.1 MiB.

## Correctness

`benchmarks/combined_runtime.py --extra-module freestanding_allocator` on the
final state — both frontend fixes plus the promoted runtime. Three programs
across four compilation arms and `PCC_GC_BACKEND=0..4`, **60 runs, all passed**
(`gates-leakfix.json`), and again after the float literal change because it
touches the shared marshal helper (`gates-litfix.json`). The ownership program is core's own
`test_known_object_refcounts.py` with `VERIFY_CHECKS=1`, which is the gate that
would catch an over-release introduced by adding a release.

## What remains: one family, two symptoms

Both have an exact reproduction in `probes/leak_app.py`; neither is guesswork.

The residual after the literal fix names the family. `(time.perf_counter() -
started) * 1000.0` went 48 → 24 bytes: the literal box is gone and what is left
is the **computed** intermediate — an owned call result consumed directly in
operand position and never released. `json.dumps({"a": 1})` is the same shape
in argument position. So what remains is one defect: **an owned temporary
consumed in operand or argument position is not released.** It is worth roughly
24 bytes per request on the gateway path.

`marshal_to_object`'s borrowed-or-owned ambiguity across 262 call sites is
still there in principle, but it no longer leaks for literals, which were its
only measured victim. Int literals that fit are tagged immediates and bools
resolve to singletons, so neither allocates.

**The collect loop.** `for kid in scope.children: samples.append(scope.result(kid))`
leaks about 1226 bytes and 6 GC-tracked objects per loop execution.
`benchmark_native.batch()` uses exactly this shape once per batch. Isolate it
with phase `list_collect` against phase `child_float`, which separates the loop
from the float it collects. Six tracked objects per loop is the outlier here and
it is not yet bisected to a single owner — it may or may not be the same family.

**Container literal in argument position.** `json.dumps({"a": 1})` leaks about
430 bytes and one tracked object per call *beyond* the json defect, while
binding the same dict to a name first leaks nothing. Compare phase `dumps_small`
against phase `dict_results`. Not on the gateway path, which binds its dict.

## Reproducing

The probes compile their own app against a chosen compiler source and runtime
archive, so a before/after is one command each. They are diagnostics kept with
this receipt rather than promoted into `benchmarks/`; `benchmarks/lifetime.py`
remains the tracked-object counterpart.

```bash
# real workload, retention after each 10k-request repeat
env -u LC_ALL uv run python probes/memory_probe.py \
  --compiler-source ../pcc --runtime-archive <archive> \
  --rounds 100 --repeats 4 --output /tmp/mem.json

# layer bisect, 20k iterations per phase
env -u LC_ALL uv run python probes/leak_bisect.py \
  --compiler-source ../pcc --runtime-archive <archive> \
  --iterations 20000 --output /tmp/bisect.json
```

Run both under core's process-tree watchdog; they take the performance lock
themselves, so pass `--no-performance-lock` to the watchdog.

## Traced afterwards: why `pcc_gateway.dns` needs libpython — 2026-09-10

The gateway's `pytest -m integration` stops on
`NotImplementedError: no-libpython function unavailable: pcc_gateway.dns.encode_name`.
Nothing is missing from the gateway: `pcc_gateway/dns.py` is tracked and
`encode_name` is at line 60. The message is the compiler's own fail-closed
stub. Under `--python-libpython off`, if a function body still needs a
`py_cpy_*` call, `user_function_lowering.py` replaces the **whole body** with a
stub that raises at runtime and names the function. The owner is therefore
core, not the gateway, even though a gateway test is what surfaces it.

`PCC_DEBUG_STRICT_NOLIB_STUB=1` (with `PCC_PY_FRONTEND_JOBS=1`, or the worker's
diagnostic never reaches stderr) names the exact call. Compiling
`tests/fixtures/gateway/current_pcc1_async_dns.py` reports two:

    pcc_gateway.dns.encode_name: py_cpy_from_pccstr(ptr %label...)
    pcc_gateway.dns.step:        py_cpy_from_pcc_obj(ptr %self.server...)

The first is `label.encode("ascii")`. A three-way probe isolates it exactly:

| expression | result |
|---|---|
| `text.encode()` | native |
| `text.encode("utf-8")` | native |
| **`text.encode("ascii")`** | **falls back, function stubbed** |

`string_method_lowering.py` recognises only `utf-8/utf8/UTF-8/UTF8` (to
`py_str_utf8_encode`) and `latin-1/latin1` (to `py_str_latin1_encode`).
`ascii` is simply absent from both encode gates. It cannot be aliased to
utf-8: it has to reject code points above 127.

**Landed** in core as `py_str_ascii_encode`, the reviewed latin-1 encoder with
the bound at 127, plus its ABI entry and both lowering gates. `encode_name`'s
stub is gone; the app's remaining stub is `pcc_gateway.dns.step` alone.

Behaviour is verified against CPython on both paths, and verifying it turned up
a second, worse bug in the encoder it was mirroring. **Out of range, both
encoders returned NULL and raised nothing**, so `"日本".encode("latin-1")`
produced EMPTY BYTES rather than an error — silently malformed output, and
exactly what `dns.encode_name`'s `try/except UnicodeError` was written to
prevent. Both now raise and both gates emit the post-call error check.
ValueError is the closest correct supertype: CPython raises
UnicodeEncodeError, and the builtin exception table has no UnicodeError to
raise, so adding one is its own change against a shared header.

| expression | before | after | CPython |
|---|---|---|---|
| `"abc".encode("ascii")` | libpython stub | `b"abc"` | `b"abc"` |
| `"café".encode("ascii")` | libpython stub | raises | raises |
| `"日本".encode("latin-1")` | **empty bytes** | raises | raises |

## `pcc_gateway.dns.step` — one root cause, shared with asyncio

The second stub has the same shape as five in `pcc/py_stdlib/asyncio.py`
(`self._loop`, `self._waiter`, `self._on_completed_fut`, `self._parent_task`):
**a method call on an instance attribute initialised to `None` falls back to
libpython**, even when another method assigns that attribute an annotated
non-None type. The IR names it — `py_cpy_from_pcc_none(%self.server)`.

Reproduces in 30 lines: a class whose `__init__` sets `self._x = None`, a
setter that assigns a real object, and a guarded `self._x.method()`. Copying
the attribute to a local first and calling a *builtin* on it compiles
natively; calling a method on the attribute does not.

Class field types come from `_class_fields_from_def` and `_append_field` in
`pcc/py_frontend/type_infer.py`, whose merge is last-write-wins with no
widening. But annotating the setter's parameter does not change the outcome,
so the setter's assignment is evidently not reaching that merge at all, and
which of the two it is has not been established. Widening a core inference
rule wants its own gate run rather than a tail-end edit.
