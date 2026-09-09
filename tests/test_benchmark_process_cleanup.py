"""Timing wrappers must not leave their benchmark child running."""

import contextlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from benchmarks.processes import run_command


def _running(pid):
    result = subprocess.run(["ps", "-p", str(pid), "-o", "stat="],
                            capture_output=True, text=True, timeout=2)
    return bool(result.stdout.strip()) and not result.stdout.lstrip().startswith("Z")


@pytest.mark.parametrize("leader_waits", [True, False])
def test_timeout_and_parent_exit_clean_the_benchmark_group(tmp_path: Path, leader_waits):
    pid_file = tmp_path / "child.pid"
    code = (
        "import subprocess,sys,time; from pathlib import Path; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], "
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "Path(sys.argv[1]).write_text(str(child.pid)); "
        + ("time.sleep(30)" if leader_waits else "sys.exit(0)")
    )
    try:
        if leader_waits:
            with pytest.raises(subprocess.TimeoutExpired):
                run_command([sys.executable, "-c", code, str(pid_file)],
                            timeout=0.3, capture_output=True, text=True)
        else:
            result = run_command([sys.executable, "-c", code, str(pid_file)],
                                 timeout=3, capture_output=True, text=True)
            assert result.returncode == 0
        pid = int(pid_file.read_text())
        deadline = time.monotonic() + 2
        while _running(pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not _running(pid)
    finally:
        if pid_file.exists() and _running(int(pid_file.read_text())):
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(pid_file.read_text()), signal.SIGKILL)


def test_sigterm_to_runner_cleans_its_command(tmp_path: Path):
    pid_file = tmp_path / "command.pid"
    child_code = "import os,sys,time; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
    code = "import sys; from benchmarks.processes import run_command; run_command([sys.executable, '-c', sys.argv[1], sys.argv[2]], timeout=30)"
    runner = subprocess.Popen([sys.executable, "-c", code, child_code, str(pid_file)],
                              cwd=Path(__file__).resolve().parents[1])
    try:
        deadline = time.monotonic() + 3
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pid_file.exists()
        runner.terminate()
        assert runner.wait(timeout=3) == 128 + signal.SIGTERM
        assert not _running(int(pid_file.read_text()))
    finally:
        if runner.poll() is None:
            runner.kill()
            runner.wait(timeout=2)
        if pid_file.exists() and _running(int(pid_file.read_text())):
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
