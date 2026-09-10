"""Rotate existing native benchmark artifacts against CPython asyncio.

Compilation is separate. --build-report binds the artifact construction
evidence; process counters include startup/warmups, handler QPS does not.
"""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

try:
    from .processes import run_command
except ImportError:
    from processes import run_command

from compare import ROOT, digest, process_metrics, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--build-report", type=Path)
    parser.add_argument("--asyncio-script", type=Path, default=ROOT / "benchmark_asyncio.py",
                        help="CPython workload; use the same source as a native asyncio arm")
    parser.add_argument("--concurrency", default="100")
    parser.add_argument("--delays", default="0")
    parser.add_argument("--requests", type=int, default=20000)
    parser.add_argument("--wait-rounds", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite existing results")
    commands = {}
    for value in args.native:
        label, separator, path = value.partition("=")
        if not separator or not label or label in commands or label == "asyncio":
            parser.error("native artifacts need unique LABEL=PATH entries")
        binary = Path(path).resolve(strict=True)
        commands[label] = [str(binary)]
    commands["asyncio"] = [sys.executable, str(args.asyncio_script.resolve(strict=True))]
    concurrencies = [int(value) for value in args.concurrency.split(",")]
    delays = [int(value) for value in args.delays.split(",")]
    if min(concurrencies) < 1 or min(delays) < 0 or min(args.requests, args.wait_rounds, args.repeats) < 1:
        parser.error("invalid request/repeat/concurrency/delay values")
    core = ROOT.parent / "pcc"
    sys.path.insert(0, str(core / "scripts"))
    from run_pcc_compile_ab import _performance_lock

    with _performance_lock():
        report = {"schema": "pcc-gateway.artifact-comparison.v1", "complete": False,
                  "started_utc": datetime.now(timezone.utc).isoformat(),
                  "python_version": sys.version, "platform": platform.platform(),
                  "scope": "validated handler batches, no HTTP; process metrics include startup and warmups",
                  "script_sha256": digest(__file__), "artifacts": {}, "runs": [], "summary": []}
        for label, command in commands.items():
            report["artifacts"][label] = {"command": command,
                "sha256": {part: digest(part) for part in command}}
        if args.build_report:
            report["build_report"] = {"path": str(args.build_report.resolve()),
                                      "sha256": digest(args.build_report)}
        env = dict(os.environ)
        env.pop("LC_ALL", None)
        env["PCC_GC_BACKEND"] = "0"
        report["runtime_environment"] = {"PCC_GC_BACKEND": "0"}
        save(args.output, report)
        labels = list(commands)
        for delay in delays:
            for concurrency in concurrencies:
                rounds = max(1, math.ceil(args.requests / concurrency)) if delay == 0 else args.wait_rounds
                for repetition in range(args.repeats):
                    shift = repetition % len(labels)
                    for label in labels[shift:] + labels[:shift]:
                        command = ["/usr/bin/time", "-lp", *commands[label],
                                   str(concurrency), str(delay), str(rounds), "--summary"]
                        before_load = os.getloadavg()
                        result = run_command(command, cwd=ROOT, env=env, text=True,
                                                capture_output=True, timeout=90)
                        if result.returncode:
                            raise RuntimeError(label + ": " + result.stdout + result.stderr)
                        sample = json.loads(result.stdout)
                        if sample["requests"] != concurrency * rounds or sample["warmup_requests"] != 2 * concurrency:
                            raise RuntimeError(label + " request/warmup count mismatch")
                        if sample["concurrency"] != concurrency or sample["delay_ms"] != delay:
                            raise RuntimeError(label + " workload mismatch")
                        elapsed = float(sample["elapsed_ms"])
                        if not math.isfinite(elapsed) or elapsed <= 0:
                            raise RuntimeError(label + " invalid elapsed time")
                        row = dict(sample, implementation=label, repetition=repetition,
                                   qps=sample["requests"] * 1000.0 / elapsed,
                                   load_before=before_load, load_after=os.getloadavg(),
                                   **process_metrics(result.stderr))
                        report["runs"].append(row)
                        save(args.output, report)
                        print(label, concurrency, delay, repetition, round(row["qps"], 1), flush=True)
        for label in labels:
            for delay in delays:
                for concurrency in concurrencies:
                    rows = [row for row in report["runs"] if row["implementation"] == label
                            and row["delay_ms"] == delay and row["concurrency"] == concurrency]
                    qps = [row["qps"] for row in rows]
                    summary = {"implementation": label, "concurrency": concurrency, "delay_ms": delay,
                               "qps_median": statistics.median(qps), "qps_min": min(qps), "qps_max": max(qps)}
                    for metric in ("process_instructions", "process_cycles", "process_peak_rss_bytes",
                                   "process_user_seconds", "process_sys_seconds"):
                        values = [row[metric] for row in rows if metric in row]
                        if values:
                            summary[metric + "_median"] = statistics.median(values)
                    report["summary"].append(summary)
        for artifact in report["artifacts"].values():
            for path, original in artifact["sha256"].items():
                if digest(path) != original:
                    raise RuntimeError("artifact changed during measurement: " + path)
        if args.build_report and digest(args.build_report) != report["build_report"]["sha256"]:
            raise RuntimeError("build evidence changed during measurement")
        report["complete"] = True
        save(args.output, report)


if __name__ == "__main__":
    main()
