"""Profile the request workload with the existing pcc/Tachyon tools.

Native mode is Darwin-only. Build benchmark_native.py before using --binary.
The summary option suppresses formatting the final latency array; every
request still performs its JSON check and records its latency normally.
Profiles are diagnostic; use compare.py/runtime_ab.py for performance verdicts.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from compare import ROOT, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arm", choices=("native", "asyncio"))
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--rounds", type=int, default=5000)
    parser.add_argument("--seconds", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rounds <= 0 or args.seconds <= 0:
        parser.error("rounds and seconds must be positive")
    if args.arm == "native" and (not args.binary or sys.platform != "darwin"):
        parser.error("native profiling requires Darwin and --binary")
    import pcc
    core = Path(pcc.__file__).resolve().parents[1]
    sys.path.insert(0, str(core / "scripts"))
    from run_pcc_compile_ab import _performance_lock
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ)
    environment.pop("LC_ALL", None)
    arguments = ["100", "0", str(args.rounds), "--summary"]
    report = {"arm": args.arm, "complete": False, "arguments": arguments}
    (output / "profile.json").write_text(json.dumps(report, indent=2) + "\n")
    with _performance_lock():
        with (output / "target.stdout").open("w") as stdout, (output / "target.stderr").open("w") as stderr:
            if args.arm == "native":
                binary = args.binary.resolve()
                report.update(binary=str(binary), binary_sha256=digest(binary))
                target = subprocess.Popen([str(binary), *arguments], cwd=ROOT,
                    # Keep the outer watchdog's session while owning a group
                    # that this profiler can terminate independently.
                    env=environment, stdout=stdout, stderr=stderr, process_group=0)
                try:
                    command = [sys.executable, str(core / "scripts/pcc_flamegraph.py"),
                        "cpu", str(target.pid), str(args.seconds), "--exact-pid",
                        "-o", str(output / "native.svg"), "--folded", str(output / "native.folded")]
                    sampled = subprocess.run(command, env=environment, capture_output=True,
                                             text=True, timeout=args.seconds + 20)
                    (output / "profiler.log").write_text(sampled.stdout + sampled.stderr)
                    if sampled.returncode:
                        raise RuntimeError("native profiler failed: " + str(output / "profiler.log"))
                    if target.wait(timeout=60):
                        raise RuntimeError("native target failed: " + str(output / "target.stderr"))
                finally:
                    if target.poll() is None:
                        os.killpg(target.pid, 15)
                        target.wait(timeout=10)
            else:
                python = args.python or core / ".venv/bin/python-tachyon"
                report.update(python=str(python.resolve()), python_sha256=digest(python))
                command = [str(python), "-m", "profiling.sampling", "run", "--mode=cpu",
                    "--opcodes", "--native", "--flamegraph", "-o", str(output / "asyncio.html"),
                    str(ROOT / "benchmark_asyncio.py"), *arguments]
                subprocess.run(command, cwd=ROOT, env=environment, stdout=stdout,
                               stderr=stderr, timeout=60, check=True)
                aggregated = subprocess.run([sys.executable, str(core / "scripts/pcc_tachyon_aggregate.py"),
                    str(output), "--json-out", str(output / "aggregate.json")],
                    env=environment, capture_output=True, text=True, timeout=15, check=True)
                (output / "aggregate.log").write_text(aggregated.stdout + aggregated.stderr)
        summaries = []
        for line in (output / "target.stdout").read_text().splitlines():
            if line.startswith("{"):
                value = json.loads(line)
                if "concurrency" in value:
                    summaries.append(value)
        if len(summaries) != 1:
            raise RuntimeError("profile target produced no unique completed workload summary")
        summary = summaries[0]
        if (summary["requests"] != 100 * args.rounds or summary["warmup_requests"] != 200
                or summary["concurrency"] != 100 or summary["delay_ms"] != 0
                or summary["rounds"] != args.rounds or "latencies_ms" in summary):
            raise RuntimeError("profile target did not execute the expected summary-mode workload")
        report.update(complete=True, profiler_command=command, workload_summary=summary)
        (output / "profile.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Saved " + str(output), flush=True)


if __name__ == "__main__":
    main()
