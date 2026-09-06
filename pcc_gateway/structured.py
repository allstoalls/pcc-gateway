"""Structured concurrency scopes over pcc virtual threads.

This is the ``StructuredTaskScope`` shape — a scope owns every child it
forked, no child outlives it, and the first failure observed by a fork-ordered
join cancels later siblings and propagates to the parent.

``virtual_thread.spawn`` requires a **literal, closed-world function name**
at the call site.  The compiler proves a resumable parking boundary for the
named target before it will emit the spawn at all
(``pcc/py_frontend/codegen/native_virtual_thread.py::_emit_virtual_thread_spawn``
rejects anything else with "requires a closed-world function name; dynamic
callable targets cannot prove may_park").  A scope therefore cannot fork a
callable handed to it as a value, the way ``scope.fork(supplier)`` does in
Java.  The fork stays at the call site and the scope adopts the handle::

    scope = TaskScope("dashboard")
    try:
        profile = scope.fork(virtual_thread.spawn(fetch_profile))
        notifications = scope.fork(virtual_thread.spawn(fetch_notifications))
        scope.join()
        data = {"profile": scope.result(profile)}
    finally:
        scope.close("handler complete")

That split costs one line of syntax and keeps every guarantee that matters:
the scope, not the caller, is still the single owner of child cancellation,
draining and failure order.

The scope deliberately has no ``__enter__``/``__exit__``.  A context manager
would be the faithful rendering of a ``with``-shaped scope block, but its
``__exit__`` would have to join — and joining parks.  Implicit parking dunder
calls are fail-closed in the current park-effect lowering, so a ``with``
form would compile only until a child actually parked.  ``try/finally``
around an explicit ``close()`` expresses the same lifetime through explicit
parking boundaries. Host-model tests cover the lifetime contracts; native
canaries exercise the dashboard and failure/cancellation paths.
"""

import pcc.virtual_thread as virtual_thread
from pcc.extern import c_int64, extern


_idle_sleep_ns = extern("pcc_platform_sleep_ns", (c_int64,), c_int64)


class TaskScopeError(RuntimeError):
    """A scope was used outside its own lifetime contract."""


class TaskScope:
    """One structured-concurrency scope owning a set of forked children.

    Use the scope from one parent virtual thread. It moves through three
    states: open (children may be forked),
    joined (every child reached a terminal outcome, results readable) and
    closed (the scope released its ownership).  ``close()`` is idempotent and
    safe from a ``finally`` block whether or not ``join()`` ran.
    """

    def __init__(self, name: str = "scope") -> None:
        self.name = name
        self.children = []
        self.joined = False
        self.closed = False
        self.failure = None
        # Declared here, not first assigned in close(): the compiled class
        # layout is closed-world, so every slot must exist on construction.
        self.close_reason = ""

    @virtual_thread.continuation_factory
    def fork(self, thread):
        """Adopt one already-spawned child and return its handle.

        The caller performs the ``virtual_thread.spawn(...)`` so the spawn
        target stays a compiler-visible name; from here on the scope owns the
        child's cancellation and draining.
        """
        if self.closed or self.joined:
            # spawn() ran before fork() could validate the scope. Retire the
            # rejected handle as well so this API cannot orphan a child.
            return virtual_thread.continuation(_reject_scope_fork, self, thread)
        self.children.append(thread)
        return virtual_thread.completed(thread)

    def join(self) -> None:
        """Wait for every child, then re-raise the first failure.

        Children are joined in fork order, so the failure reported is the
        first in program order rather than the first to be scheduled.  Once
        one child fails the remaining siblings are cancelled and drained
        before the failure propagates, which is what keeps the scope's exit
        a real barrier: no child is still running when the parent resumes.
        """
        if self.joined:
            failure = self.failure
            if failure is not None:
                raise failure
            return
        self.joined = True
        failed_at = -1
        index = 0
        while index < len(self.children):
            try:
                virtual_thread.join(self.children[index])
            except Exception as error:
                self.failure = error
                failed_at = index
                break
            index += 1
        if failed_at >= 0:
            self._retire(failed_at + 1)
            failure = self.failure
            raise failure

    def result(self, thread):
        """Return one child's value; only legal after ``join()``.

        Reading a result before the barrier is the classic structured
        concurrency error — the value may not exist yet — so it is rejected
        rather than returning ``None``.
        """
        if not self.joined:
            raise TaskScopeError(
                "scope " + self.name + ": result read before join"
            )
        return virtual_thread.result(thread)

    def outcome(self, thread) -> int:
        """Return one child's terminal outcome code."""
        return virtual_thread.outcome(thread)

    @virtual_thread.continuation_factory
    def close(self, reason: str = "scope closed"):
        """Release scope ownership, cancelling and draining any stragglers.

        Safe to call from ``finally`` after a successful ``join()`` (where it
        is a no-op), after a failed one, or instead of one when the scope
        body raised before reaching the barrier.
        """
        if self.closed:
            return virtual_thread.completed(None)
        if self.joined:
            self.closed = True
            self.close_reason = reason
            return virtual_thread.completed(None)
        return virtual_thread.continuation(_close_scope_children, self, reason)

    def _close_unjoined(self, reason: str) -> None:
        """The deferred cleanup path; keep cancellation behind its barrier."""
        if self.closed:
            return
        self.closed = True
        self.close_reason = reason
        if not self.joined:
            self.joined = True
            self._retire(0)

    def _retire(self, start: int) -> None:
        """Cancel and drain children from ``start`` to the end of the scope."""
        index = start
        while index < len(self.children):
            self._retire_child(self.children[index])
            index += 1

    def _retire_child(self, child) -> None:
        virtual_thread.cancel(child)
        try:
            virtual_thread.join(child)
        except Exception:
            # A cancelled sibling raises on join by design. Cleanup must
            # preserve the scope's primary failure or lifetime error.
            pass


def _reject_scope_fork(scope: "TaskScope", thread):
    scope._retire_child(thread)
    if scope.closed:
        raise TaskScopeError("scope " + scope.name + " is closed")
    if scope.joined:
        raise TaskScopeError("scope " + scope.name + " already joined")
    scope.children.append(thread)
    return thread


def _close_scope_children(scope: "TaskScope", reason: str):
    scope._close_unjoined(reason)


def run_until_complete(thread):
    """Drive a root task from outside the virtual-thread scheduler.

    run() steps runnable work and may return with timers pending. The outer
    driver waits briefly when idle, letting timer-bound children finish while
    preserving run() as a stepping API for cancellation/control callers.
    """
    if virtual_thread.current() is not None:
        raise TaskScopeError("run_until_complete requires an outer driver")
    while virtual_thread.outcome(thread) == virtual_thread.OUTCOME_PENDING:
        steps = virtual_thread.run(1, 4096)
        if steps < 0:
            raise TaskScopeError("virtual-thread scheduler failed")
        if steps == 0 and virtual_thread.outcome(thread) == virtual_thread.OUTCOME_PENDING:
            # The pcc platform ABI waits only the outer driver, after
            # runnable virtual threads drained. Child waits remain virtual.
            if _idle_sleep_ns(1000000) < 0:
                raise TaskScopeError("outer scheduler wait failed")
    failure = virtual_thread.exception(thread)
    if failure is not None:
        raise failure
    if virtual_thread.outcome(thread) != virtual_thread.OUTCOME_RETURNED:
        raise TaskScopeError("root task was cancelled")
    return virtual_thread.result(thread)


__all__ = ["TaskScope", "TaskScopeError", "run_until_complete"]
