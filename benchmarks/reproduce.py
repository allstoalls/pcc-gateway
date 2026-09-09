"""Rebuild and measure the optimized runtime under bounded process watchdogs."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcc-source", type=Path, default=ROOT.parent / "pcc")
    parser.add_argument("--runtime-archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.pcc_source.resolve(strict=True)
    archive = args.runtime_archive.resolve(strict=True)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    watchdog = ROOT.parent / "pcc/scripts/run_process_tree_sample.py"

    def run(name, command, timeout, internal_lock=False):
        wrapped = [sys.executable, str(watchdog), "--result", str(out / (name + ".json")),
                   "--samples", str(out / (name + ".samples")),
                   "--stdout", str(out / (name + ".stdout")),
                   "--stderr", str(out / (name + ".stderr")),
                   "--timeout", str(timeout), "--max-tree-rss-bytes", "3221225472"]
        if internal_lock:
            wrapped.append("--no-performance-lock")
        print(name, flush=True)
        subprocess.run([*wrapped, "--", *map(str, command)], cwd=ROOT, check=True)

    build = out / "runtime"
    run("build", [sys.executable, ROOT / "benchmarks/combined_runtime.py",
                  "--pcc-source", source, "--runtime-archive", archive,
                  "--output-dir", build, "--extra-module", "freestanding_allocator"], 240)
    run("measure", [sys.executable, ROOT / "benchmarks/artifact_compare.py",
                    "--native", "pcc=" + str(build / "benchmark-owned_round2"),
                    "--build-report", build / "build-report.json",
                    "--requests", "200000", "--repeats", "7",
                    "--output", out / "comparison.json"], 180, internal_lock=True)
    print("Results: " + str(out / "comparison.json"))


if __name__ == "__main__":
    main()
