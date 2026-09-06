"""Keep diagnostic ablations faithful to payload and child-cleanup behavior."""

import ast
import importlib.util
from pathlib import Path

import pytest

from test_gateway_structured_concurrency import FakeScheduler


ROOT = Path(__file__).resolve().parents[1]


def load_variant(monkeypatch, mode):
    monkeypatch.syspath_prepend(str(ROOT / "benchmarks"))
    spec = importlib.util.spec_from_file_location("gateway_layers", ROOT / "benchmarks/layers.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tree = ast.parse(module.variant_source((ROOT / "benchmark_native.py").read_text(), mode))
    assert isinstance(tree.body[-1], ast.Expr) and tree.body[-1].value.func.id == "main"
    tree.body.pop()  # Exercise one request, without running the command-line driver.
    namespace = {"__name__": "gateway_layer_test"}
    exec(compile(tree, "gateway_layer_test", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("mode", ["scope", "direct", "json-only"])
def test_layer_payload_and_declared_wait_shape(monkeypatch, mode):
    scheduler = FakeScheduler()
    scheduler.install(monkeypatch)
    namespace = load_variant(monkeypatch, mode)
    assert namespace["request"](0) >= 0
    assert scheduler.pending == []
    assert scheduler.slept_ms == ([] if mode == "json-only" else [0, 0])


@pytest.mark.parametrize("mode", ["scope", "direct"])
def test_layer_failure_cancels_and_drains_the_sibling(monkeypatch, mode):
    scheduler = FakeScheduler()
    scheduler.install(monkeypatch)
    namespace = load_variant(monkeypatch, mode)

    def failing_profile(delay_ms):
        raise ValueError("profile failed")

    namespace["fetch_profile"] = failing_profile
    with pytest.raises(ValueError, match="profile failed"):
        namespace["request"](0)
    assert scheduler.pending == []
    assert "cancel:fetch_notifications" in scheduler.events
