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

## Status: not compiling yet (was already red in the core)

The pcc1 path of the gateway was already failing inside the core at HEAD
(same errors as `pcc.gateway`), so this is not an extraction gap. Fixed on
2026-09-06 (gateway sources here + compiler fixes in the core working tree):
may_park resolution (`virtual_thread.call` around duck-typed transport reads,
typed `connection` helpers, a hoisted nested park), `stack_alloc` module
constants, builtin-typed receivers, except-handler delegation slots, finally
and handler dominance in may_park state machines, cross-module int globals.

Remaining compile error: a boxed negative literal passed into a sibling
class `__init__` whose ABI slot is `i64` (`GatewayConnection(app, -1, ...)`
→ `'%int.obj.neg' defined with type 'ptr' but expected 'i64'`). The fix
belongs in the core's `class_gen.emit_instantiate` (unbox with
`py_int_value_i64` when the caller module keeps ints as objects); see the
core's `docs/knowledge/2026-09-06-session-handoff.md`.

## Tests

The tests use the core's pytest fixtures; run them from a core checkout with
this repository as the package site once the parity issue is closed:

```bash
cd /path/to/pcc && PCC_PACKAGE_SITE=/path/to/pcc-gateway gtimeout 900s env -u LC_ALL \
    uv run pytest -q -x /path/to/pcc-gateway/tests/test_gateway_http1_codec.py
```
