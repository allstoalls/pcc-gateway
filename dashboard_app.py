"""A structured-concurrency dashboard endpoint on pcc virtual threads.

This is the Java-flavoured "virtual threads + structured concurrency" example
rewritten using pcc's explicit virtual-thread API. The original sketch used two
block forms Python does not have and pcc's parser rejects — a bare ``await:``
scope containing bare ``async:`` children::

    data = {}
    await:
        async:
            data["profile"] = fetch({"name": "Ada", "plan": "pro"})
        async:
            data["notifications"] = fetch(["Your report is ready"])

``pcc/parse/py_parse.py`` only accepts ``async def`` / ``async for`` /
``async with``, and ``await`` is a unary expression prefix, so neither block
parses.  What the sketch *means*, though, maps onto pcc directly:

    ``async:``  ->  ``virtual_thread.spawn(fetch_x)`` adopted by the scope
    ``await:``  ->  ``TaskScope`` ... ``scope.join()``

The rest of the sketch — one virtual thread per connection, with
try/except/finally cleanup around each request — is not application code
here at all: it is what ``pcc_gateway.server.GatewayServer`` already does
(``spawn_accept`` / ``spawn_connection``), so this file only supplies the
handler and lets the gateway own the connection lifetime.

``dashboard_probe`` drives the whole request path — HTTP/1 codec, router,
framework dispatch, response encoder — without a socket, which is the same
sans-I/O shape ``local_http_app.py`` uses. Host-model tests and compiled
host-pcc/pcc1 execution gates exercise this path (see README.md).
"""

import json

import pcc.virtual_thread as virtual_thread
from pcc_gateway.lifecycle import GatewayLifecycle
from pcc_gateway.server import GatewayConfig, GatewayConnection
from pcc_gateway.structured import TaskScope, run_until_complete
from pcc_gateway.web import App, Request, Response, get


# Park the virtual thread for the sketch's 100 ms fetch delay, allowing the
# other child to run on the same carrier.
FETCH_DELAY_MS = 100


def fetch_profile():
    """One of the two concurrent children — the sketch's first ``async:``."""
    virtual_thread.sleep_current(FETCH_DELAY_MS)
    return {"name": "Ada", "plan": "pro"}


def fetch_notifications():
    """The second concurrent child — the sketch's second ``async:``."""
    virtual_thread.sleep_current(FETCH_DELAY_MS)
    return ["Your report is ready"]


def dashboard(request: Request):
    """GET /dashboard — fan out two fetches, join them, answer with JSON.

    Both children are spawned before the barrier and request FETCH_DELAY_MS
    parks. Native execution overlaps those waits; the comparison script
    measures this fan-out shape against asyncio.TaskGroup.
    """
    data = {}
    scope = TaskScope("dashboard")
    try:
        # The spawn stays at the call site: the compiler must see a literal
        # function name to prove a resumable parking boundary.  The scope
        # owns the children from the moment it adopts them.
        profile = scope.fork(virtual_thread.spawn(fetch_profile))
        notifications = scope.fork(virtual_thread.spawn(fetch_notifications))
        scope.join()
        data["profile"] = scope.result(profile)
        data["notifications"] = scope.result(notifications)
    finally:
        scope.close("dashboard handler complete")
    body = json.dumps(data, sort_keys=True).encode()
    return Response.bytes(body, 200, [("content-type", "application/json")])


def build_app() -> App:
    """The routing table.  Anything but /dashboard is a framework 404."""
    return App(routes=(get("/dashboard", dashboard),))


def dashboard_probe() -> int:
    """Run one 200 and one 404 through the real codec/router/encoder path."""
    app = build_app()
    config = GatewayConfig()
    lifecycle = GatewayLifecycle(config, config.admission)
    lifecycle.start()
    lifecycle.started()
    if not lifecycle.admit_connection():
        return 1
    generation = lifecycle.acquire_generation()
    connection = GatewayConnection(app, -1, None, lifecycle, generation, config)

    # RequestHead + RequestEnd for each of the two pipelined requests.  The
    # handler parks inside this call; feed_data is reached through the
    # explicit resumable call boundary.
    events = virtual_thread.call(
        connection.feed_data,
        b"GET /dashboard HTTP/1.1\r\nHost: local\r\n\r\n"
        b"GET /missing HTTP/1.1\r\nHost: local\r\n\r\n",
    )
    if events != 4:
        return 2

    output = connection.take_output()
    if b"HTTP/1.1 200 OK" not in output:
        return 3
    if b"application/json" not in output:
        return 4
    # Check the returned values independently of JSON whitespace.
    if b'"Ada"' not in output or b'"pro"' not in output:
        return 5
    if b'"Your report is ready"' not in output:
        return 6
    # sort_keys=True: "notifications" precedes "profile" in the body.
    # find(), not index(): only find/rfind are lowered for bytes.
    if output.find(b'"notifications"') > output.find(b'"profile"'):
        return 7
    if b"HTTP/1.1 404 Not Found" not in output:
        return 8
    if lifecycle.metrics.get("requests_started") != 2:
        return 9
    if lifecycle.metrics.get("requests_active") != 0:
        return 10

    connection.close("dashboard-probe-complete")
    generation.release()
    lifecycle.release_connection()
    print("PCC1_DASHBOARD_STRUCTURED_OK")
    return 0


def main() -> int:
    thread = virtual_thread.spawn(dashboard_probe)
    result = run_until_complete(thread)
    if result != 0:
        raise RuntimeError("dashboard probe failed: " + str(result))
    return result


main()
