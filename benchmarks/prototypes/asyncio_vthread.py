"""Prototype: the asyncio surface, backed by pcc's virtual threads.

`pcc/py_stdlib/asyncio.py` is a reference implementation written in Python: a
ready queue, `_Handle` objects, `Future` callback chains and a Python-level
`Task._step`. Measured against CPython -- whose `Task` and `Future` are C
types in `_asyncio` -- it loses by roughly 25x. Rebuilding CPython's design in
pcc's runtime would at best reach parity, because the algorithm and the object
model would be the same.

pcc already has machinery that is *faster* than CPython's asyncio: the virtual
threads `benchmark_native.py` uses reach 86,862 req/s against asyncio's 84,456
on the published gateway comparison. This file asks whether the asyncio API can
be served by that machinery instead of by a second scheduler written in Python.

The whole design rests on one property: **the coroutine never parks; the
virtual thread does.** `await` unwinds out of the coroutine and back into
`_drive`, an ordinary function whose parking calls are literal -- which is what
`virtual_thread.spawn` requires of a target, and what lets a coroutine-shaped
API sit on a thread-shaped scheduler at all. Nothing here allocates a Task, a
Future, a Handle or a context copy.

Scope: exactly what `benchmark_asyncio_gather.py` uses -- `run`, `gather` and
`sleep`. This is a measurement instrument, not a replacement for the stdlib
module. What a real replacement additionally owes: `call_soon` FIFO ordering,
`Task.cancel()` delivering `CancelledError` at the next await point,
per-virtual-thread `contextvars`, `get_running_loop()` identity, and a
conformance suite for the "no interleaving between awaits" contract that real
asyncio code depends on.
"""

import pcc.virtual_thread as vt
from pcc.extern import extern, c_obj, c_ptr
from pcc.unsafe import null

from pcc_gateway.structured import run_until_complete


_await_iterator = extern("py_await_iterator", (c_ptr,), c_obj)
_await_step = extern("py_await_step", (c_ptr, c_ptr, c_ptr), c_obj)


class _Sleep:
    """A suspension request the driver turns into a virtual-thread park.

    `asyncio.sleep` is a coroutine in the stdlib; here it is a plain object, so
    a sleep costs no coroutine of its own.
    """

    def __init__(self, delay_ms: int, result=None) -> None:
        self.delay_ms = delay_ms
        self.result = result

    def __await__(self):
        yield self
        return self.result


class _Gather:
    """A fan-out request the driver turns into forked virtual threads.

    `gather` cannot be an `async def` that joins: its body would run inside a
    coroutine frame, and parking from there is exactly what the compiler cannot
    prove. Yielding the request back to `_drive` puts the join in a frame that
    owns a parking boundary.
    """

    def __init__(self, awaitables) -> None:
        self.awaitables = awaitables
        self.results = None

    def __await__(self):
        yield self
        return self.results


def _fork_and_join(awaitables):
    """Run every awaitable on its own virtual thread, in fork order."""
    threads = []
    for awaitable in awaitables:
        threads.append(vt.spawn(_drive, awaitable))
    results = []
    for thread in threads:
        vt.join(thread)
        failure = vt.exception(thread)
        if failure is not None:
            raise failure
        results.append(vt.result(thread))
    return results


def _drive(awaitable):
    """Run one coroutine to completion inside the current virtual thread."""
    iterator = _await_iterator(awaitable)
    while True:
        try:
            yielded = _await_step(iterator, null(), null())
        except StopIteration as stopped:
            return stopped.value
        if yielded is None:
            vt.yield_now()
        elif isinstance(yielded, _Sleep):
            if yielded.delay_ms > 0:
                vt.sleep_current(yielded.delay_ms)
            else:
                vt.yield_now()
        elif isinstance(yielded, _Gather):
            yielded.results = _fork_and_join(yielded.awaitables)
        else:
            vt.yield_now()


def sleep(delay, result=None):
    return _Sleep(int(delay * 1000.0), result)


def gather(*awaitables):
    return _Gather(awaitables)


def run(awaitable):
    thread = vt.spawn(_drive, awaitable)
    return run_until_complete(thread)
