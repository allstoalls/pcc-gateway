"""Standalone gateway test setup; native archives remain compiler-owned."""

import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def package_site(monkeypatch):
    sites = [str(ROOT)]
    existing = os.environ.get("PCC_PACKAGE_SITE")
    if existing:
        sites.append(existing)
    monkeypatch.setenv("PCC_PACKAGE_SITE", os.pathsep.join(sites))


@pytest.fixture(scope="session")
def pcc_py_runtime_archive():
    from tests.runtime_build_cache import cached_pcc_python_runtime
    return cached_pcc_python_runtime() / "libpy_runtime_pcc_py.a"


@pytest.fixture(scope="session")
def threaded_pcc_py_runtime_archive():
    from tests.runtime_build_cache import cached_threaded_pcc_python_runtime
    return cached_threaded_pcc_python_runtime() / "libpy_runtime_pcc_py.a"
