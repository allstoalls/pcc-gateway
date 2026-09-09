# Per-request memory: compiler ownership leaks — 2026-09-10

Companion to `../2026-09-10-object-start-inline/`, which won throughput but
left peak RSS untouched at 2.96x asyncio. This receipt is the memory front.

## The gap was never baseline memory

| Requests | leaky | json fix | both fixes | asyncio |
|---:|---:|---:|---:|---:|
| 10,000 | 9.4 MiB | 7.7 | **6.9** | 27.9 |
| 50,000 | 29.1 | 20.7 | **16.6** | 29.0 |
| 100,000 | 53.7 | 36.3 | **28.7** | 31.0 |
| 200,000 | 102.9 | 68.2 | **52.9** | 35.0 |

Native baseline memory was always the better one — 6.9 MiB against asyncio's
27.9 at 10k requests, a quarter of it. The entire loss was **per-request
growth**: 516 bytes per request against asyncio's 38. So the question was never
"why is the runtime fat", it was "what does each request retain".

With both fixes that slope is 242 bytes and native now also wins at 100k
requests. The crossover moved from about 50k to about 120k.

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

## Two defects fixed

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

Measured effect: `json.dumps` 127 → **0** B/call, `json.loads` 907 → **0** and
2 → **0** tracked objects, `time.perf_counter` 24 → **0**, and the full gateway
request path 127 → **0**. Real-workload retention went 203 → 73.6 → **49.1**
bytes per request across the two fixes.

## Throughput did not pay for it

200,000 requests x 7 repeats, C100/0ms, same run
(`../2026-09-10-leakfix-confirm.json`):

| | retained | with fixes | asyncio |
|---|---:|---:|---:|
| Median QPS | 80,634 | **85,821** | 80,948 |
| Paired QPS vs retained | — | **+6.54%, 6/7** | — |
| Paired QPS vs asyncio | — | **+3.84%, 6/7** | — |
| Median QPS vs asyncio | — | **+6.02%** | — |
| Instructions | 3.876e10 | 3.839e10 | 3.204e10 |
| Median peak RSS | 102.8 MiB | **52.9 MiB** | 34.8 MiB |

Adding releases did not cost throughput; this is the best arm measured. Fewer
live objects means less allocator pressure and better locality, which more than
paid for the extra release calls.

## Correctness

`benchmarks/combined_runtime.py --extra-module freestanding_allocator` on the
final state — both frontend fixes plus the promoted runtime. Three programs
across four compilation arms and `PCC_GC_BACKEND=0..4`, **60 runs, all passed**
(`gates-leakfix.json`). The ownership program is core's own
`test_known_object_refcounts.py` with `VERIFY_CHECKS=1`, which is the gate that
would catch an over-release introduced by adding a release.

## Three defects located and left unfixed

All three have an exact reproduction in `probes/leak_app.py`; none is guesswork.

**Float literal boxing — the largest remaining lever.** Every evaluation of a
float literal as an operand of a DynType operation leaks 24 bytes. `y = x - 0.5`
leaks one float per iteration; `(x - 0.5) * 1000.0` leaks two. The emitted IR
shows it directly: `py_float_from_f64` for the literal is emitted *inside* the
loop body (block `while.body.8`, value `%m.flt_box`) and never released.

The cause is a shape, not a typo: `marshal_to_object` returns either the
incoming pointer unchanged (borrowed, must not be released) or a fresh
`py_int_from_i64` / `py_float_from_f64` / `py_bool_from_bit` box (owned, must be
released), and the caller cannot tell which. It has **262 call sites**. The
`BinOp` rule in `_expr_returns_owned_object` covers the operation's *result*,
not its operand boxes.

Two directions, in preference order. Emit each distinct float literal as a
module-level immortal box created once — that kills the leak *and* removes an
allocation from every dynamic float operation, so it should be a throughput win
too. Otherwise return an owned flag from `marshal_to_object` and release at the
sites that created a box, starting with `binary_op_lowering`.

This was not attempted here because a shared-codegen ownership change across
262 call sites needs its own design pass and gate run, and core's AGENTS.md
forbids stacking speculative shared-codegen edits.

**The collect loop.** `for kid in scope.children: samples.append(scope.result(kid))`
leaks about 1226 bytes and 6 GC-tracked objects per loop execution.
`benchmark_native.batch()` uses exactly this shape once per batch. Isolate it
with phase `list_collect` against phase `child_float`, which separates the loop
from the float it collects. Not yet bisected to a single owner.

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
