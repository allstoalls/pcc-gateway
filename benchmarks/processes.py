"""Run one benchmark command with a lifetime bounded by its process group."""

import os
import signal
import subprocess
import threading
import time


def _group_has_live_members(pgid):
    rows = subprocess.check_output(["ps", "-axo", "pgid=,stat="], text=True, timeout=2)
    for line in rows.splitlines():
        group, state = line.split()
        if int(group) == pgid and not state.startswith("Z"):
            return True
    return False


def _stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        if _group_has_live_members(process.pid):
            raise
        return
    # The group can outlive its leader (notably /usr/bin/time). Reaping only
    # the leader leaves the native benchmark running under init.
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            # Darwin can report EPERM for an orphan group containing only
            # zombies; they are already dead and await the system reaper.
            if _group_has_live_members(process.pid):
                raise
            return
        time.sleep(0.01)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        if _group_has_live_members(process.pid):
            raise
    process.wait(timeout=2)


def run_command(command, *, timeout, capture_output=False, check=False, **kwargs):
    if capture_output:
        if "stdout" in kwargs or "stderr" in kwargs:
            raise ValueError("capture_output cannot be combined with stdout/stderr")
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # A distinct group permits per-arm cancellation while retaining the outer
    # watchdog's session, so it can also recover an orphaned group.
    process = subprocess.Popen(command, process_group=0, **kwargs)
    previous_term = None
    if threading.current_thread() is threading.main_thread():
        previous_term = signal.getsignal(signal.SIGTERM)

        def terminate(signum, _frame):
            raise SystemExit(128 + signum)

        signal.signal(signal.SIGTERM, terminate)
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _stop_group(process)
            process.communicate(timeout=2)
            raise
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
    finally:
        try:
            _stop_group(process)
        finally:
            if previous_term is not None:
                signal.signal(signal.SIGTERM, previous_term)
