# AGENTS.md

## Project intent

Build a native HTTP gateway and declarative web framework whose ordinary
application code uses pcc virtual threads and structured concurrency. Own the
HTTP, routing, proxy, streaming and lifecycle behavior in `pcc_gateway`;
complete reusable compiler/runtime capabilities in pcc. Performance must retain
request semantics, child-task cleanup and all five GC contracts.

[Core Intent](../pcc/docs/project-intent.md) and
[compiler contracts](../pcc/docs/compiler-contract.md) define the shared target:
host pcc uses CPython plus its standard library; native pcc1 requires no external
LLVM/llvmlite, cc/toolchain, host Python or libpython, including runtime and C
processing. Existing external build routes are migration gaps, not exceptions.
Platform ABI and explicitly named application providers are separate boundaries.

## Work from source and fix the right owner

- Start with current code, effective options, tests and `git status --short`.
  Historical reports locate experiments; verify their revision and artifacts
  before adopting a conclusion. Do not preload the compiler's whole knowledge base.
- Fix HTTP/API/proxy/lifecycle behavior here. Fix Python semantics, lowering,
  optimizer, scheduling primitives, object ownership, GC or toolchain defects in
  `../pcc`, following its [AGENTS.md](../pcc/AGENTS.md). Add a small core regression
  and confirm the real gateway scenario; do not turn compiler bugs into app rules.
- Keep one implementation of each reusable mechanism. Applications and examples
  consume the public framework; do not copy schedulers or runtime helpers into
  handlers. Keep ordinary commands simple; do not require diagnostic pass switches.
- Track work in `allstoalls/pcc-gateway` or `allstoalls/pcc` according to ownership.
  Preserve other edits and unfinished scope. No destructive resets or unrequested
  commit/push; do not change packaging/release metadata as unrelated cleanup.

## Correctness boundaries

- Preserve TaskScope fork/join/failure ordering, cancellation, draining and
  exactly-once cleanup. A faster path must execute the same children and work.
- Exercise fragmented HTTP messages, framing/limits, partial writes, backpressure,
  disconnects, deadlines and shutdown. Keep nonblocking transport and explicit
  resource ownership through errors; a successful happy-path request is insufficient.
- Keep TLS at the declared provider ABI. Record the provider/artifact used and
  verify real HTTPS separately; never replace it silently with plaintext or
  Python ssl. Provider code must not take over scheduling or socket ownership.
- Shared runtime/ownership changes require the relevant GC0–4 and failure-cleanup
  gates in core as well as the gateway reproducer. Host models, native handlers,
  live HTTP and live HTTPS are distinct validation scopes.

## Development and validation

- At each user-approved quota checkpoint, record weekly quota remaining. Check
  it during work and before heavy runs. After a drop of 10 percentage points
  (or an earlier user-specified threshold), stop work, clean up owned processes,
  save evidence and a handoff, and wait for the user's review before continuing.
  Status questions and interruptions do not reset this checkpoint. Use observed
  quota data; never claim to monitor a reading that is unavailable.
- The adjacent `../pcc` checkout is selected by `pyproject.toml`. Use
  `env -u LC_ALL uv run ...`; keep `.python-version` aligned with core and the
  asyncio baseline (3.15.0rc1). uv/dev tools are not native compiler dependencies.
- Use the qualified `pcc1` on PATH (`~/.local/bin/pcc1` normally); keep experimental
  binaries isolated. Tests accept `PCC_TEST_PCC1` for a candidate and `PCC_TEST_PCC`
  for the host entry. A cached/installed name alone does not prove source identity.
- Start with focused tests using `-x -vv --tb=short` and a timeout. The default
  pytest selection excludes `integration`; inspect fixtures because native tests
  may rebuild the shared runtime. Example of focused protocol validation:

```bash
gtimeout 120s env -u LC_ALL uv run pytest tests/test_gateway_http1_codec.py -x -vv --tb=short
```

- `tests/test_native_examples.py` explicitly tests pcc and pcc1 compile/run;
  select it with `-m integration` after the relevant focused checks. Live network
  and TLS gates have their own fixtures. Save long-run logs, stop at the first
  failure and follow core's watchdog/performance-lock rules for heavy work.
- Prevent process leaks: run builds, tests and benchmarks under a process-tree
  watchdog; on timeout, error, interruption or parent exit, terminate and reap
  the owned process tree, not only its wrapper. Before finishing, verify that
  no task processes remain. Stop only processes whose task ownership is confirmed.
- New public behavior needs a regression and a runnable example. Validate package
  discovery through actual compile/run; `PCC_PACKAGE_SITE` is a search-location
  override, not a compiler capability or an assumed requirement for every app.

## Performance and source routing

Keep scripts and raw results reproducible; see [benchmark methods](benchmarks/README.md).
Record compiler/runtime/pass/cache identities, validated work, concurrency,
latency, QPS, CPU/instructions and memory. Compare same-run arms under the core
performance lock. Handler batch QPS, steady-load HTTP QPS and scheduler tasks/s
are different workloads. Profile before changing an owner; pair IR-effect
checks with emitted execution, and label external LLVM references explicitly.
Keep README results concise and tied to receipts; old numbers are not defaults.

| Work | Source and tests to inspect |
|---|---|
| Structured requests | `pcc_gateway/structured.py`, `web/`, `tests/test_gateway_structured_concurrency.py`, `dashboard_app.py` |
| HTTP/buffers/transport | `http1.py`, `buffer.py`, `channel.py`, `server.py` under `pcc_gateway/`; corresponding `tests/test_gateway_*` |
| Proxy/DNS/TLS | `pcc_gateway/proxy*.py`, `dns*.py`, `tls.py`, `native/`, `include/`; provider and product canaries |
| Reload/drain/control | `pcc_gateway/config.py`, `lifecycle.py`, `control.py`, `routing.py` |
| Throughput | `benchmark_native.py`, `benchmark_asyncio.py`, `benchmarks/`; inspect actual pass dispatch in core |

Keep this file to stable intent, ownership, validation and source locators.
Store experiment history beside its receipts, not as additional startup rules.
