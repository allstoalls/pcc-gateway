"""Compile both native arms and retain a reproducible asyncio comparison.

Run with ``uv run python benchmarks/compare.py --pcc1 /path/to/pcc1``.
Compilation, process startup and two warmup batches are outside measured
request time. Every request validates the same JSON bytes. No sockets are used.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_tree_digest(root):
    state = hashlib.sha256()
    for path in sorted((root / "pcc").rglob("*.py")):
        state.update(str(path.relative_to(root)).encode())
        state.update(bytes.fromhex(digest(path)))
    return state.hexdigest()


def git(*args, cwd=ROOT):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                            text=True, timeout=15)
    return result.stdout.strip() if result.returncode == 0 else None


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def process_metrics(stderr):
    """Darwin process totals include startup/warmups; request timings do not."""
    metrics = {}
    for label in ("real", "user", "sys"):
        match = re.search(rf"^{label}\s+([0-9.]+)$", stderr, re.MULTILINE)
        if match:
            metrics[f"process_{label}_seconds"] = float(match.group(1))
    match = re.search(r"^\s*(\d+)\s+maximum resident set size$", stderr, re.MULTILINE)
    if match:
        metrics["process_peak_rss_bytes"] = int(match.group(1))
    for label, key in (("instructions retired", "process_instructions"),
                       ("cycles elapsed", "process_cycles"),
                       ("involuntary context switches", "process_involuntary_context_switches")):
        match = re.search(rf"^\s*(\d+)\s+{label}$", stderr, re.MULTILINE)
        if match:
            metrics[key] = int(match.group(1))
    return metrics


def write_markdown(path, report):
    lines = [
        "# Structured-concurrency comparison",
        "",
        f"Run: {report['started_utc']}; {report['platform']}; {report['cpu_model']}.",
        "",
        "Two concurrent child waits and validated JSON per request; one carrier/event loop.",
        "These are handler requests/s, excluding HTTP and network transport.",
        "QPS is the median of repeated runs; percentiles pool measured requests.",
        "Process peak RSS includes startup and warmups.",
        "",
        "| Wait (ms) | Concurrency | Implementation | Median QPS | Min–max QPS | p50 (ms) | p95 (ms) | Peak RSS (MiB) |",
        "|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["summary"]:
        rss = row.get("process_peak_rss_bytes_median")
        memory = f"{rss / 1024**2:.2f}" if rss is not None else "n/a"
        lines.append(
            f"| {row['delay_ms']} | {row['concurrency']} | {row['implementation']} "
            f"| {row['requests_per_second_median']:.1f} "
            f"| {row['requests_per_second_min']:.1f}–{row['requests_per_second_max']:.1f} "
            f"| {row['p50_ms']:.3f} | {row['p95_ms']:.3f} | {memory} |"
        )
    lines.extend(["", f"Raw samples and provenance: [{path.name}]({path.name}).", ""])
    path.with_suffix(".md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcc", default=shutil.which("pcc"))
    parser.add_argument("--pcc1", default=shutil.which("pcc1"))
    parser.add_argument("--compiler-source", type=Path,
                        help="fixed compiler source tree shared by host pcc and pcc1")
    parser.add_argument("--runtime-archive", type=Path,
                        help="application runtime archive shared by both native arms")
    parser.add_argument("--pcc1-binary", type=Path,
                        help="native executable behind a pcc1 environment wrapper")
    parser.add_argument("--pcc1-receipt", type=Path,
                        help="optional core Stage1 build receipt for this native executable")
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--zero-delay-requests", type=int, default=5000,
                        help="minimum requests per run when delay=0")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--concurrency", default="1,10,100")
    parser.add_argument("--delays", default="0,100")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "benchmarks/results/latest.json")
    args = parser.parse_args()
    if not args.pcc or not args.pcc1:
        parser.error("both pcc and pcc1 are required; specify their paths")
    if args.output.exists():
        parser.error("refusing to overwrite an existing comparison")
    concurrencies = [int(item) for item in args.concurrency.split(",")]
    delays = [int(item) for item in args.delays.split(",")]
    if (args.rounds <= 0 or args.repeats <= 0 or args.zero_delay_requests <= 0
            or min(concurrencies) <= 0 or min(delays) < 0):
        parser.error("rounds/repeats/concurrency must be positive and delays nonnegative")

    import pcc
    core = Path(pcc.__file__).resolve().parents[1]
    sys.path.insert(0, str(core / "scripts"))
    from run_pcc_compile_ab import _performance_lock

    with _performance_lock():
        compare(args, core, concurrencies, delays, parser)


def compare(args, core, concurrencies, delays, parser):
    build = ROOT / "benchmarks/build" / args.output.stem
    build.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env.pop("LC_ALL", None)
    env.pop("PCC_PACKAGE_SITE", None)
    compiler_source = args.compiler_source.resolve() if args.compiler_source else core
    if args.compiler_source:
        env.update(PYTHONPATH=str(compiler_source), PCC_SOURCE_ROOT=str(compiler_source),
                   PCC_REPO_ROOT=str(compiler_source))
    env.update(PCC_GC_BACKEND="0", PCC_WITH_THREADS="0", PCC_RUNTIME_HIGH="py",
               PCC_DISABLE_BULK_GENERATOR_FRAME_INIT="1")
    if args.runtime_archive:
        env.update(PCC_RUNTIME_ARCHIVE=str(args.runtime_archive.resolve()),
                   PCC_RUNTIME_CC="/usr/bin/false")
    cpu_model = platform.processor()
    if sys.platform == "darwin":
        cpu_model = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=10
        ).strip()
    report = {
        "schema": "pcc-gateway.asyncio-comparison.v1",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "complete": False,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": cpu_model,
        "cpu_count": os.cpu_count(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "compiler_source": str(compiler_source),
        "compiler_source_sha256": source_tree_digest(compiler_source),
        "load_average_start": os.getloadavg() if hasattr(os, "getloadavg") else None,
        "gateway_commit": git("rev-parse", "HEAD"),
        "gateway_dirty": bool(git("status", "--porcelain")),
        "core_commit": git("rev-parse", "HEAD", cwd=core),
        "core_dirty": bool(git("status", "--porcelain", cwd=core)),
        "core_diff_sha256": hashlib.sha256(
            (git("diff", "HEAD", "--", "pcc", cwd=core) or "").encode()
        ).hexdigest(),
        "sources": {str(path.relative_to(ROOT)): digest(path)
                    for path in sorted([
                        ROOT / "benchmark_native.py", ROOT / "benchmark_asyncio.py", Path(__file__).resolve(),
                        *ROOT.glob("pcc_gateway/**/*.py")])},
        "workload": "Two child waits, TaskScope/TaskGroup barrier, identical sorted JSON bytes; no HTTP/socket I/O",
        "warmup_batches": 2,
        "memory_scope": "Darwin /usr/bin/time per-process peak RSS, including startup and warmups",
        "rounds": args.rounds,
        "zero_delay_requests": args.zero_delay_requests,
        "repeats": args.repeats,
        "compilers": {}, "runs": [], "summary": [],
    }
    if args.runtime_archive:
        report["application_runtime"] = {
            "path": str(args.runtime_archive.resolve()), "sha256": digest(args.runtime_archive)
        }
    if args.pcc1_binary:
        report["pcc1_binary"] = {
            "path": str(args.pcc1_binary.resolve()), "sha256": digest(args.pcc1_binary)
        }
    if args.pcc1_receipt:
        receipt = json.loads(args.pcc1_receipt.read_text())
        if not args.pcc1_binary or receipt.get("compiler_sha256") != digest(args.pcc1_binary):
            parser.error("--pcc1-receipt must match --pcc1-binary")
        report["pcc1_receipt"] = {
            key: receipt[key] for key in (
                "schema", "status", "compiler_sha256", "runtime_bundle_sha256",
                "source_manifest_sha256",
            )
        }
    save(args.output, report)
    args.output.with_suffix(".md").write_text("Comparison in progress; no complete results yet.\n")
    commands = {"asyncio": [sys.executable, str(ROOT / "benchmark_asyncio.py")]}
    for label, compiler in (("host-pcc", args.pcc), ("pcc1", args.pcc1)):
        compiler = str(Path(compiler).resolve())
        output = build / label
        command = [compiler, "--backend", "self", "--python-libpython", "off",
                   "--ir-scaffold", "on", str(ROOT / "benchmark_native.py"),
                   "-o", str(output)]
        print(f"Compiling {label}", flush=True)
        started = time.perf_counter()
        log = build / f"{label}-compile.log"
        with log.open("w") as stream:
            compiled = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=300)
        report["compilers"][label] = {
            "path": compiler, "sha256": digest(compiler), "command": command,
            "compile_seconds": time.perf_counter() - started,
            "returncode": compiled.returncode,
        }
        save(args.output, report)
        if compiled.returncode:
            raise RuntimeError(f"{label} compilation failed: {log}")
        report["compilers"][label]["artifact_sha256"] = digest(output)
        if sys.platform == "darwin":
            linkage = subprocess.check_output(["otool", "-L", str(output)], text=True, timeout=10)
            if "libpython" in linkage.lower():
                raise RuntimeError(label + " unexpectedly links libpython")
            report["compilers"][label]["dynamic_dependencies"] = linkage.splitlines()[1:]
        commands[label] = [str(output)]

    labels = list(commands)
    for delay in delays:
        for concurrency in concurrencies:
            rounds = (max(args.rounds, math.ceil(args.zero_delay_requests / concurrency))
                      if delay == 0 else args.rounds)
            for repetition in range(args.repeats):
                # Rotate arms to avoid always giving one implementation the
                # first (or last) position. All runs use a single carrier/loop.
                order = labels[repetition % 3:] + labels[:repetition % 3]
                for label in order:
                    command = commands[label] + [str(concurrency), str(delay), str(rounds)]
                    timed_command = (["/usr/bin/time", "-lp", *command]
                                     if sys.platform == "darwin" else command)
                    ran = subprocess.run(timed_command, cwd=ROOT, env=env, text=True,
                                         capture_output=True, timeout=60)
                    if ran.returncode:
                        raise RuntimeError(f"{label} failed ({ran.returncode}): {ran.stdout}\n{ran.stderr}")
                    measured = json.loads(ran.stdout)
                    expected_count = concurrency * rounds
                    samples = measured["latencies_ms"]
                    if (measured["requests"] != expected_count or len(samples) != expected_count
                            or measured["warmup_requests"] != concurrency * 2
                            or measured["concurrency"] != concurrency or measured["delay_ms"] != delay
                            or measured["rounds"] != rounds
                            or not math.isfinite(measured["elapsed_ms"]) or measured["elapsed_ms"] <= 0
                            or not all(math.isfinite(value) and value >= max(0, delay - 2)
                                       for value in samples)
                            or measured["elapsed_ms"] < rounds * max(0, delay - 2)):
                        raise RuntimeError(f"invalid/incomplete {label} measurements: {measured}")
                    measured.update(implementation=label, repetition=repetition)
                    measured["load_average"] = os.getloadavg() if hasattr(os, "getloadavg") else None
                    measured.update(process_metrics(ran.stderr))
                    report["runs"].append(measured)
                    save(args.output, report)
                    rate = measured["requests"] * 1000 / measured["elapsed_ms"]
                    print(f"{label}: wait={delay}ms concurrency={concurrency} repeat={repetition + 1} {rate:.1f} requests/s", flush=True)
            for label in labels:
                rows = [row for row in report["runs"] if row["implementation"] == label
                        and row["delay_ms"] == delay and row["concurrency"] == concurrency]
                rates = [row["requests"] * 1000 / row["elapsed_ms"] for row in rows]
                samples = [value for row in rows for value in row["latencies_ms"]]
                summary = {
                    "implementation": label, "delay_ms": delay, "concurrency": concurrency,
                    "requests_per_second_median": statistics.median(rates),
                    "requests_per_second_min": min(rates), "requests_per_second_max": max(rates),
                    "p50_ms": percentile(samples, .5), "p95_ms": percentile(samples, .95),
                }
                rss = [row["process_peak_rss_bytes"] for row in rows
                       if "process_peak_rss_bytes" in row]
                if rss:
                    summary["process_peak_rss_bytes_median"] = statistics.median(rss)
                report["summary"].append(summary)
    if source_tree_digest(compiler_source) != report["compiler_source_sha256"]:
        raise RuntimeError("compiler source changed during comparison")
    for path, identity in report["sources"].items():
        if digest(ROOT / path) != identity:
            raise RuntimeError("workload or runner source changed during comparison: " + path)
    if args.runtime_archive and digest(args.runtime_archive) != report["application_runtime"]["sha256"]:
        raise RuntimeError("application runtime changed during comparison")
    report["load_average_end"] = os.getloadavg() if hasattr(os, "getloadavg") else None
    report["complete"] = True
    save(args.output, report)
    write_markdown(args.output, report)
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
