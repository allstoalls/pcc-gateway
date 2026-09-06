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

## Status: does not compile out of tree yet

The same sources compiled inside the core as `pcc.gateway` / `pcc.web`; as an
external package the current frontend stops with three gaps, recorded here so
they are fixed in the compiler rather than worked around in this repository:

1. `codegen[pcc_gateway.server]: pcc.virtual_thread.spawn cannot prove a
   resumable parking boundary for _gateway_connection_entry: calls unresolved
   may_park wrapper: _run_gateway_connection`
2. `codegen[pcc_gateway.web.app]: may_park method boundary is not statically
   resumable: App.dispatch: unresolved user-method may park: .join`
3. `codegen[pcc_gateway]: cross-module global representation mismatch for
   pcc_gateway.tls.PCC_TLS_REQUIRED_CAPABILITIES` (the importing module does
   not use the raw-int scaffold that `tls.py` uses, so the same module-level
   int is an object on one side and an `i64` on the other)

Two related gaps were already fixed in the core while extracting this package:
`stack_alloc(SIZE)` now folds a module-scope integer constant and constant
arithmetic over such constants, and runtime-port modules imported as closure
siblings keep their pointer-lane lowering. The remaining three are tracked as a
GitHub issue on the core ("out-of-tree package parity with pcc-owned modules").
Until it is closed, this repository is the authoritative home of the sources
but cannot be built.

## Tests

The tests use the core's pytest fixtures; run them from a core checkout with
this repository as the package site once the parity issue is closed:

```bash
cd /path/to/pcc && PCC_PACKAGE_SITE=/path/to/pcc-gateway gtimeout 900s env -u LC_ALL \
    uv run pytest -q -x /path/to/pcc-gateway/tests/test_gateway_http1_codec.py
```
