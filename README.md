# pcc-gateway

A virtual-thread HTTP/1.1 gateway kernel and a typed declarative web framework
written in pcc-Python for the [pcc](https://github.com/allstoalls/pcc)
compiler: channel buffers with backpressure, an HTTP/1 codec, routing, reverse
proxy policy, lifecycle/process control, a native DNS transport and a TLS
provider ABI backed by OpenSSL, all on pcc's own virtual threads with no
libpython at run time.

It is an ordinary pcc package: an application does `from pcc_gateway.web import
App, ...` and `pcc1` compiles the framework into the program together with the
application code. Nothing is prebuilt and nothing is linked from outside the
compiler.

Extracted from `allstoalls/pcc` at commit `2574f585` (2026-09-06); the core no
longer contains `pcc/gateway` or `pcc/web`.

## Layout

- `pcc_gateway/` – the gateway kernel (`buffer`, `channel`, `http1`, `routing`,
  `proxy`, `proxy_http1`, `lifecycle`, `control`, `dns`, `dns_native`, `tls`,
  `server`, `config`, `models`).
- `pcc_gateway/web/` – the declarative application framework (`App`,
  `Request`, `Response`, `BodyStream`, route decorators, proxy dispatch).
- `pcc_gateway/include/pcc_tls_provider_v1.h`, `pcc_gateway/native/` – the
  `pcc-native-tls-v1` provider ABI and its OpenSSL implementation (`make` in
  `pcc_gateway/native`, OpenSSL >= 3).
- `local_http_app.py` – a product-shaped local HTTP/1 application (request
  codec, router, framework dispatch, response encoder) that pcc1 compiles.
- `tests/` – unit tests and pcc1 canaries; `tests/fixtures/gateway/` the pcc1
  gate programs.
- `docs/pcc-vthread-gateway.md` – design note; `docs/gateway-research/` –
  references.

The process-control primitives the gateway uses (`pcc_gateway_control_*`) are a
generic runtime substrate and stay in the core runtime
(`pcc/py_runtime/py/freestanding_gateway_control.py`).

## Use it

```bash
PCC_PACKAGE_SITE=/path/to/pcc-gateway \
  pcc1 --backend self --python-libpython off --ir-scaffold on local_http_app.py -o local_http_app
./local_http_app
```

`PCC_PACKAGE_SITE` is pcc's package-site list (colon separated); the package
can also be copied into pcc's default site
(`~/.local/share/pcc/environments/<tag>/site-packages`).

## Status

`local_http_app.py` **compiles, links and runs** as an ordinary external pcc
package (verified 2026-09-06 with a host `pcc` built from the core working
tree; no libpython, self backend, nothing linked from outside the compiler).

Getting there fixed nine compiler defects in the core, all of which were
already latent inside it:

- `stack_alloc(SIZE)` now folds a module-scope int constant and constant
  arithmetic over such constants.
- Builtin-typed receivers (`", ".join(...)`) are no longer treated as
  open-world methods that might park.
- The delegation-slot planner visits `except` handler bodies.
- The `finally` exception root and a named handler's release re-derive their
  frame pointer per block (may_park state machines split at every park).
- Cross-module integer globals bridge the raw-`i64` and boxed representations.
- A signed integer literal (`FLOOR = -7`) exports as a constant like `7` did;
  previously a raw-int provider stored `i64` into a slot the importer read as
  a tagged object pointer and `-7` arrived as `-4`.
- A sibling module's ABI slot type wins over the caller's int policy, so a
  boxed `-1` reaches an `i64` parameter correctly.
- Values loaded from module-level globals are re-derived at pin/unpin and call
  sites a park boundary made unreachable from their definition.
- Module resolution is case-exact, so on macOS `from pkg import App` no longer
  resolves the class `App` to `pkg/app.py` and compiles it twice.

Remaining defect, pre-existing and shared with the core's asyncio/threading
paths: a virtual thread spawned from a plain `def` never runs its body
(`virtual_thread.result(...)` returns `None`), so the probe exits 0 without
printing `PCC1_GATEWAY_HTTP1_LOCAL_OK`. Tracked as a core issue
(`RT-P1-MAY-PARK-CALLER-SILENT-DEF-RED`).

The package also no longer reaches into pcc internals: the byte payload
offsets come from the public `pcc.unsafe.abi_constant` intrinsic instead of
`pcc.py_runtime.py.py_abi_constants`.

## Tests

The tests use the core's pytest fixtures; run them from a core checkout with
this repository as the package site once the parity issue is closed:

```bash
cd /path/to/pcc && PCC_PACKAGE_SITE=/path/to/pcc-gateway gtimeout 900s env -u LC_ALL \
    uv run pytest -q -x /path/to/pcc-gateway/tests/test_gateway_http1_codec.py
```
