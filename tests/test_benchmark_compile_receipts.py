import json
import subprocess

import pytest

from benchmarks import compare


@pytest.mark.parametrize("outcome", ["timeout", "failure", "success"])
def test_compile_receipt_survives_each_command_outcome(tmp_path, monkeypatch, outcome):
    compiler = tmp_path / "compiler"
    compiler.write_bytes(b"test compiler")
    output = tmp_path / "program"
    report_path = tmp_path / "report.json"
    report = {"started_utc": "test", "platform": "test", "cpu_model": "test",
              "complete": False, "status": "RUNNING", "compilers": {}, "summary": []}

    def run(command, **kwargs):
        pending = json.loads(report_path.read_text())
        assert pending["compilers"]["pcc1"]["status"] == "RUNNING"
        assert kwargs["timeout"] == 300
        kwargs["stdout"].write("compiler diagnostic\n")
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 300)
        if outcome == "success":
            output.write_bytes(b"program bytes")
        return subprocess.CompletedProcess(command, 1 if outcome == "failure" else 0)

    monkeypatch.setattr(compare, "run_command", run)
    monkeypatch.setattr(compare.subprocess, "check_output", lambda *a, **k: "program:\nlibSystem\n")
    kwargs = dict(env={}, report=report, report_path=report_path)
    args = ("pcc1", str(compiler), tmp_path / "source.py", output, tmp_path / "compile.log")
    if outcome == "success":
        assert compare.compile_arm(*args, **kwargs) == [str(output)]
    else:
        with pytest.raises(subprocess.TimeoutExpired if outcome == "timeout" else RuntimeError):
            compare.compile_arm(*args, **kwargs)
    saved = json.loads(report_path.read_text())
    row = saved["compilers"]["pcc1"]
    assert row["status"] == {"success": "COMPILED", "timeout": "TIMEOUT", "failure": "FAILED"}[outcome]
    assert row["compile_seconds"] >= 0
    assert "artifact_sha256" in row if outcome == "success" else "artifact_sha256" not in row
    assert saved["complete"] is False
    if outcome != "success":
        assert saved["failure"]["implementation"] == "pcc1"
        assert "Status: FAILED" in report_path.with_suffix(".md").read_text()
