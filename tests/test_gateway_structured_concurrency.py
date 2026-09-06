"""Structured-concurrency scope contracts and the dashboard example.

These tests script virtual-thread edges rather than borrowing a host
scheduler, the same way ``test_gateway_local_streaming.py`` does.  The fake
runs each child at the moment it is joined, which is deliberately the least
concurrent legal schedule: a scope whose ordering, cancellation and failure
propagation hold under it cannot depend on children racing ahead.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import pcc.virtual_thread as virtual_thread
import pcc_gateway.structured as structured
from pcc_gateway.structured import TaskScope, TaskScopeError, run_until_complete


REPO = Path(__file__).resolve().parents[1]


class FakeThread:
    def __init__(self, fn, args) -> None:
        self.fn = fn
        self.args = args
        self.state = "pending"
        self.value = None
        self.error = None


class FakeScheduler:
    """A deterministic stand-in for the pcc virtual-thread runtime."""

    def __init__(self) -> None:
        self.pending = []
        self.events = []
        self.slept_ms = []

    def install(self, monkeypatch) -> None:
        monkeypatch.setattr(virtual_thread, "spawn", self.spawn)
        monkeypatch.setattr(virtual_thread, "join", self.join)
        monkeypatch.setattr(virtual_thread, "result", self.result)
        monkeypatch.setattr(virtual_thread, "exception", self.exception)
        monkeypatch.setattr(virtual_thread, "cancel", self.cancel)
        monkeypatch.setattr(virtual_thread, "outcome", self.outcome)
        monkeypatch.setattr(virtual_thread, "run", self.run)
        monkeypatch.setattr(virtual_thread, "current", lambda: None)
        monkeypatch.setattr(virtual_thread, "sleep_current", self.sleep_current)

    def spawn(self, fn, *args):
        thread = FakeThread(fn, args)
        self.pending.append(thread)
        self.events.append("spawn:" + fn.__name__)
        return thread

    def sleep_current(self, delay_ms: int) -> None:
        self.slept_ms.append(delay_ms)

    def _run(self, thread: FakeThread) -> None:
        if thread.state != "pending":
            return
        if thread in self.pending:
            self.pending.remove(thread)
        self.events.append("start:" + thread.fn.__name__)
        try:
            thread.value = thread.fn(*thread.args)
            thread.state = "returned"
        except Exception as error:  # noqa: BLE001 - mirrors runtime capture
            thread.error = error
            thread.state = "raised"
        self.events.append(thread.state + ":" + thread.fn.__name__)

    def join(self, thread: FakeThread):
        self._run(thread)
        if thread.state == "raised":
            raise thread.error
        if thread.state == "cancelled":
            raise RuntimeError("virtual thread cancelled")
        return thread.value

    def result(self, thread: FakeThread):
        return thread.value

    def exception(self, thread: FakeThread):
        return thread.error

    def cancel(self, thread: FakeThread) -> bool:
        if thread.state != "pending":
            return False
        thread.state = "cancelled"
        if thread in self.pending:
            self.pending.remove(thread)
        self.events.append("cancel:" + thread.fn.__name__)
        return True

    def outcome(self, thread: FakeThread) -> int:
        if thread.state == "returned":
            return virtual_thread.OUTCOME_RETURNED
        if thread.state == "raised":
            return virtual_thread.OUTCOME_RAISED
        if thread.state == "cancelled":
            return virtual_thread.OUTCOME_CANCELLED
        return virtual_thread.OUTCOME_PENDING

    def run(self, carrier_count: int, max_steps: int) -> int:
        steps = 0
        while self.pending and steps < max_steps:
            self._run(self.pending[0])
            steps += 1
        return steps


@pytest.fixture()
def scheduler(monkeypatch) -> FakeScheduler:
    fake = FakeScheduler()
    fake.install(monkeypatch)
    return fake


def alpha():
    return "alpha"


def beta():
    return "beta"


def boom():
    raise ValueError("child failed")


def test_root_driver_waits_when_a_scheduler_step_is_idle(scheduler, monkeypatch):
    thread = virtual_thread.spawn(alpha)
    runs = []
    waits = []
    original = scheduler.run

    def step(carriers, budget):
        runs.append((carriers, budget))
        return 0 if len(runs) == 1 else original(carriers, budget)

    monkeypatch.setattr(virtual_thread, "run", step)
    def idle_wait(ns):
        waits.append(ns)
        return 0

    monkeypatch.setattr(structured, "_idle_sleep_ns", idle_wait)
    assert run_until_complete(thread) == "alpha"
    assert len(runs) == 2
    assert waits == [1000000]


def test_root_driver_propagates_child_failure(scheduler):
    thread = virtual_thread.spawn(boom)
    with pytest.raises(ValueError, match="child failed"):
        run_until_complete(thread)


def test_root_driver_rejects_cancelled_tasks(scheduler):
    thread = virtual_thread.spawn(alpha)
    virtual_thread.cancel(thread)
    with pytest.raises(TaskScopeError, match="root task was cancelled"):
        run_until_complete(thread)


def test_root_driver_rejects_recursive_scheduler_entry(scheduler, monkeypatch):
    thread = virtual_thread.spawn(alpha)
    monkeypatch.setattr(virtual_thread, "current", lambda: thread)
    with pytest.raises(TaskScopeError, match="requires an outer driver"):
        run_until_complete(thread)


def test_scope_forks_every_child_before_the_barrier_joins_any(scheduler) -> None:
    scope = TaskScope("fanout")
    first = scope.fork(virtual_thread.spawn(alpha))
    second = scope.fork(virtual_thread.spawn(beta))
    scope.join()

    # Both forks precede both starts: this is fan-out then join, not two
    # sequential calls wearing a scope.
    assert scheduler.events == [
        "spawn:alpha",
        "spawn:beta",
        "start:alpha",
        "returned:alpha",
        "start:beta",
        "returned:beta",
    ]
    assert scope.result(first) == "alpha"
    assert scope.result(second) == "beta"
    scope.close("done")


def test_result_before_join_is_rejected(scheduler) -> None:
    scope = TaskScope("early")
    thread = scope.fork(virtual_thread.spawn(alpha))
    with pytest.raises(TaskScopeError, match="result read before join"):
        scope.result(thread)
    scope.close("abandoned")


def test_fork_after_join_is_rejected(scheduler) -> None:
    scope = TaskScope("late")
    scope.fork(virtual_thread.spawn(alpha))
    scope.join()
    with pytest.raises(TaskScopeError, match="already joined"):
        scope.fork(virtual_thread.spawn(beta))
    assert scheduler.pending == []


def test_fork_after_close_is_rejected(scheduler) -> None:
    scope = TaskScope("closed")
    scope.close("shut")
    with pytest.raises(TaskScopeError, match="is closed"):
        scope.fork(virtual_thread.spawn(alpha))
    assert scheduler.pending == []


def test_first_failure_cancels_later_siblings_and_propagates(scheduler) -> None:
    scope = TaskScope("failing")
    scope.fork(virtual_thread.spawn(boom))
    survivor = scope.fork(virtual_thread.spawn(beta))

    with pytest.raises(ValueError, match="child failed"):
        scope.join()

    # The sibling never ran, and the scope is a real barrier: nothing is
    # still pending when the parent resumes.
    assert scheduler.events == [
        "spawn:boom",
        "spawn:beta",
        "start:boom",
        "raised:boom",
        "cancel:beta",
    ]
    assert scheduler.pending == []
    assert scope.outcome(survivor) == virtual_thread.OUTCOME_CANCELLED
    assert isinstance(scope.failure, ValueError)


def test_failure_is_reported_in_fork_order_not_completion_order(scheduler) -> None:
    scope = TaskScope("order")
    scope.fork(virtual_thread.spawn(alpha))
    scope.fork(virtual_thread.spawn(boom))
    with pytest.raises(ValueError, match="child failed"):
        scope.join()
    assert scope.result(scope.children[0]) == "alpha"


def test_rejoining_a_failed_scope_reraises_the_same_failure(scheduler) -> None:
    scope = TaskScope("sticky")
    scope.fork(virtual_thread.spawn(boom))
    with pytest.raises(ValueError):
        scope.join()
    first = scope.failure
    with pytest.raises(ValueError):
        scope.join()
    assert scope.failure is first


def test_close_drains_children_when_the_scope_body_never_joined(scheduler) -> None:
    scope = TaskScope("aborted")
    left = scope.fork(virtual_thread.spawn(alpha))
    right = scope.fork(virtual_thread.spawn(beta))
    try:
        raise RuntimeError("scope body failed before the barrier")
    except RuntimeError:
        pass
    finally:
        scope.close("body failed")

    assert scheduler.events == [
        "spawn:alpha",
        "spawn:beta",
        "cancel:alpha",
        "cancel:beta",
    ]
    assert scheduler.pending == []
    assert scope.outcome(left) == virtual_thread.OUTCOME_CANCELLED
    assert scope.outcome(right) == virtual_thread.OUTCOME_CANCELLED


def test_close_is_idempotent_and_a_noop_after_a_successful_join(scheduler) -> None:
    scope = TaskScope("tidy")
    scope.fork(virtual_thread.spawn(alpha))
    scope.join()
    before = list(scheduler.events)
    scope.close("first")
    scope.close("second")
    assert scheduler.events == before
    assert scope.close_reason == "first"


def _load_dashboard_app():
    """Import the example fresh; its module body runs the whole probe."""
    spec = importlib.util.spec_from_file_location(
        "dashboard_app_under_test", REPO / "dashboard_app.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dashboard_handler_answers_with_sorted_json_from_two_children(
    scheduler,
) -> None:
    module = _load_dashboard_app()
    # Import executes the probe; measure only the handler call below.
    scheduler.slept_ms.clear()
    request_cls = module.Request
    response = module.dashboard(request_cls("GET", "/dashboard"))

    assert response.status == 200
    assert ("content-type", "application/json") in response.headers
    assert json.loads(response.body.decode()) == {
        "profile": {"name": "Ada", "plan": "pro"},
        "notifications": ["Your report is ready"],
    }
    # sort_keys is what makes the body byte-stable across runs.
    assert response.body.index(b'"notifications"') < response.body.index(b'"profile"')
    # Each child requested the expected park duration. The fake scheduler
    # does not establish elapsed time or prove overlapping execution.
    assert scheduler.slept_ms == [module.FETCH_DELAY_MS, module.FETCH_DELAY_MS]


def test_dashboard_probe_runs_the_whole_request_path(scheduler, capsys) -> None:
    module = _load_dashboard_app()
    # The module body already ran main() during import.
    assert module.main() == 0
    assert "PCC1_DASHBOARD_STRUCTURED_OK" in capsys.readouterr().out


def test_unrouted_path_is_a_framework_404(scheduler) -> None:
    module = _load_dashboard_app()
    app = module.build_app()
    response = app.dispatch(module.Request("GET", "/nope"))
    assert response.status == 404
