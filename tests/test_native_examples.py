"""Compile and execute the documented examples with both compiler entries."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.integration


@pytest.mark.parametrize("compiler_name", ["pcc", "pcc1"])
@pytest.mark.parametrize("source, marker", [
    ("local_http_app.py", "PCC1_GATEWAY_HTTP1_LOCAL_OK"),
    ("dashboard_app.py", "PCC1_DASHBOARD_STRUCTURED_OK"),
    ("tests/fixtures/gateway/structured_scope_app.py", "PCC1_STRUCTURED_FAILURE_CLEANUP_OK"),
])
def test_documented_native_example(tmp_path, compiler_name, source, marker):
    compiler = os.environ.get("PCC_TEST_" + compiler_name.upper()) or shutil.which(compiler_name)
    assert compiler, f"{compiler_name} must be installed on PATH"
    executable = tmp_path / Path(source).stem
    environment = dict(os.environ)
    environment.pop("LC_ALL", None)
    environment.pop("PCC_PACKAGE_SITE", None)
    command = [compiler]
    if compiler_name == "pcc":
        command += ["--backend", "self", "--python-libpython", "off", "--ir-scaffold", "on"]
    command += [source, "-o", str(executable)]
    compiled = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                              capture_output=True, timeout=300)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    ran = subprocess.run([str(executable)], cwd=ROOT, env=environment, text=True,
                         capture_output=True, timeout=15)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.strip() == marker
    if sys.platform == "darwin":
        linkage = subprocess.check_output(["otool", "-L", str(executable)], text=True, timeout=10)
        assert "libpython" not in linkage.lower(), linkage
