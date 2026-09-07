"""Compare two runtime archives using one compiler and the same native workload.

Run from the uv environment. This reuses the core performance lock and keeps
compiler construction, program compilation, startup and warmups out of QPS.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys

from compare import ROOT, digest, percentile, process_metrics, save


def source_identity(core, programs=()):
    paths = [ROOT / "benchmark_native.py", ROOT / "benchmark_asyncio.py",
             ROOT / "pcc_gateway/structured.py",
             *sorted((core / "pcc").rglob("*.py"))]
    for program in programs:
        paths.append(program)
        paths.extend(sorted((program.parent / "pcc_gateway").rglob("*.py")))
    state = hashlib.sha256()
    for path in paths:
        state.update(str(path).encode())
        state.update(bytes.fromhex(digest(path)))
    return state.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-runtime", type=Path, required=True)
    parser.add_argument("--candidate-runtime", type=Path, required=True)
    parser.add_argument("--pcc", default=shutil.which("pcc"))
    parser.add_argument("--compiler-source", type=Path,
                        help="immutable pcc source tree used by the host compiler")
    parser.add_argument("--control-compiler-source", type=Path,
                        help="override the control arm's immutable compiler source")
    parser.add_argument("--candidate-compiler-source", type=Path,
                        help="override the candidate arm's immutable compiler source")
    parser.add_argument("--control-backend", choices=("self", "llvm"), default="self")
    parser.add_argument("--candidate-backend", choices=("self", "llvm"), default="self",
                        help="diagnose emitted-code costs with an explicit LLVM oracle arm")
    parser.add_argument("--control-program", type=Path, default=ROOT / "benchmark_native.py",
                        help="control workload; sibling pcc_gateway sources may be frozen with it")
    parser.add_argument("--candidate-program", type=Path, default=ROOT / "benchmark_native.py")
    parser.add_argument("--control-env", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--candidate-env", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--delays", default="0,100")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--requests", type=int, default=5000,
                        help="minimum zero-delay requests per run")
    parser.add_argument("--summary", action="store_true",
                        help="suppress final latency-array formatting; retain min/max checks")
    parser.add_argument("--asyncio", action="store_true", help="include a same-run asyncio control")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    arm_env = {}
    for label, values in (("control", args.control_env), ("candidate", args.candidate_env)):
        settings = {}
        for value in values:
            key, separator, content = value.partition("=")
            if not key or not separator or key == "PCC_RUNTIME_ARCHIVE":
                parser.error("arm environment entries must be KEY=VALUE; runtime paths use their dedicated arguments")
            settings[key] = content
        arm_env[label] = settings
    delays = [int(value) for value in args.delays.split(",")]
    if not args.pcc or args.repeats < 1 or args.concurrency < 1 or args.requests < 1 or min(delays) < 0:
        parser.error("compiler and positive repeats/concurrency are required")
    if args.output.exists():
        parser.error("refusing to overwrite an existing comparison")
    import pcc
    core = Path(pcc.__file__).resolve().parents[1]
    sys.path.insert(0, str(core / "scripts"))
    from run_pcc_compile_ab import _performance_lock

    build = ROOT / "benchmarks/build" / args.output.stem
    archives = {"control": args.control_runtime.resolve(),
                "candidate": args.candidate_runtime.resolve()}
    programs = {"control": args.control_program.resolve(),
                "candidate": args.candidate_program.resolve()}
    env = dict(os.environ)
    env.pop("LC_ALL", None)
    env.pop("PCC_PACKAGE_SITE", None)
    env["PCC_RUNTIME_CC"] = "/usr/bin/false"
    compiler_source = args.compiler_source.resolve() if args.compiler_source else core
    compiler_sources = {
        "control": (args.control_compiler_source or compiler_source).resolve(),
        "candidate": (args.candidate_compiler_source or compiler_source).resolve(),
    }
    backends = {"control": args.control_backend, "candidate": args.candidate_backend}
    if args.compiler_source:
        env.update(PYTHONPATH=str(compiler_source), PCC_SOURCE_ROOT=str(compiler_source),
                   PCC_REPO_ROOT=str(compiler_source))
    report = {"schema": "pcc-gateway.runtime-ab.v1", "complete": False,
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "compiler": str(Path(args.pcc).resolve()),
              "compiler_sha256": digest(args.pcc), "compiler_source": str(compiler_source),
              "compiler_sources": {key: str(path) for key, path in compiler_sources.items()},
              "backends": backends,
              "archives": {}, "arm_environment": arm_env,
              "summary_output": args.summary, "python_version": sys.version,
              "programs": {key: str(path) for key, path in programs.items()},
              "base_optimization_environment": {key: env.get(key) for key in (
                  "PCC_GC_BACKEND", "PCC_WITH_THREADS", "PCC_RUNTIME_HIGH",
                  "PCC_DISABLE_BULK_GENERATOR_FRAME_INIT", "PCC_GENERATOR_FIRST_ENTRY_INIT",
                  "PCC_FAST_COMPLETED_CONTINUATIONS", "PCC_DIRECT_GENERATOR_TASKS")},
              "runs": [], "summary": []}
    with _performance_lock():
        build.mkdir(parents=True, exist_ok=False)
        report["source_identity"] = source_identity(compiler_source, programs.values())
        report["arm_source_identities"] = {
            key: source_identity(path, programs.values())
            for key, path in compiler_sources.items()
        }
        report["tool_overrides"] = {}
        for label, settings in arm_env.items():
            if "CC" in settings:
                cc = Path(shutil.which(settings["CC"]) or settings["CC"]).resolve()
                report["tool_overrides"][label] = {
                    "CC": str(cc), "sha256": digest(cc),
                    "version": subprocess.check_output([str(cc), "--version"], text=True, timeout=15),
                }
        save(args.output, report)
        binaries = {}
        for label, archive in archives.items():
            binary = build / label
            command = [args.pcc, "--backend", backends[label], "--python-libpython", "off",
                       "--ir-scaffold", "on", str(programs[label]),
                       "-o", str(binary)]
            compile_env = dict(env, **arm_env[label])
            compile_env.update(PYTHONPATH=str(compiler_sources[label]),
                PCC_SOURCE_ROOT=str(compiler_sources[label]),
                PCC_REPO_ROOT=str(compiler_sources[label]))
            compile_env["PCC_RUNTIME_ARCHIVE"] = str(archive)
            print("Compiling " + label, flush=True)
            with (build / (label + "-compile.log")).open("w") as stream:
                ran = subprocess.run(command, env=compile_env, cwd=programs[label].parent, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=300)
            if ran.returncode:
                raise RuntimeError(label + " compile failed; see " + str(build))
            report["archives"][label] = {"path": str(archive), "sha256": digest(archive),
                                          "artifact_sha256": digest(binary), "command": command}
            binaries[label] = binary
            save(args.output, report)
        if args.asyncio:
            binaries["asyncio"] = ROOT / "benchmark_asyncio.py"
            arm_env["asyncio"] = {}
        for delay in delays:
            rounds = max(10, math.ceil(args.requests / args.concurrency)) if delay == 0 else 10
            for repeat in range(args.repeats):
                labels = list(binaries)
                shift = repeat % len(labels)
                order = labels[shift:] + labels[:shift]
                for label in order:
                    command = [str(binaries[label]), str(args.concurrency), str(delay), str(rounds)]
                    if label == "asyncio":
                        command.insert(0, sys.executable)
                    if args.summary:
                        command.append("--summary")
                    if sys.platform == "darwin":
                        command = ["/usr/bin/time", "-lp", *command]
                    run_env = dict(env, **arm_env[label])
                    ran = subprocess.run(command, env=run_env, cwd=ROOT, capture_output=True,
                                         text=True, timeout=60)
                    if ran.returncode:
                        raise RuntimeError(label + ": " + ran.stdout + ran.stderr)
                    row = json.loads(ran.stdout)
                    expected = args.concurrency * rounds
                    if args.summary:
                        valid_samples = (math.isfinite(row["latency_min_ms"])
                            and math.isfinite(row["latency_max_ms"])
                            and row["latency_max_ms"] >= row["latency_min_ms"] >= max(0, delay - 2))
                    else:
                        valid_samples = (len(row["latencies_ms"]) == expected
                            and all(math.isfinite(x) and x >= max(0, delay - 2) for x in row["latencies_ms"]))
                    if (row["requests"] != expected or not valid_samples
                            or row["warmup_requests"] != 2 * args.concurrency
                            or row["concurrency"] != args.concurrency or row["delay_ms"] != delay
                            or row["rounds"] != rounds or not math.isfinite(row["elapsed_ms"])
                            or row["elapsed_ms"] <= 0 or row["elapsed_ms"] < rounds * max(0, delay - 2)):
                        report["validation_failure"] = {"implementation": label,
                            "command": command, "measurement": row, "stderr": ran.stderr}
                        save(args.output, report)
                        raise RuntimeError("incomplete or invalid " + label + " measurements; retained in report")
                    row.update(implementation=label, repetition=repeat, **process_metrics(ran.stderr))
                    report["runs"].append(row)
                    save(args.output, report)
                    print(f"{label} delay={delay} repeat={repeat + 1}: "
                          f"{expected * 1000 / row['elapsed_ms']:.1f} QPS", flush=True)
            for label in binaries:
                rows = [row for row in report["runs"] if row["implementation"] == label and row["delay_ms"] == delay]
                rates = [row["requests"] * 1000 / row["elapsed_ms"] for row in rows]
                summary = {"implementation": label, "delay_ms": delay,
                    "qps_median": statistics.median(rates), "qps_min": min(rates), "qps_max": max(rates)}
                if not args.summary:
                    latencies = [value for row in rows for value in row["latencies_ms"]]
                    summary.update(p50_ms=percentile(latencies, .5), p95_ms=percentile(latencies, .95))
                for key in ("process_instructions", "process_cycles", "process_user_seconds", "process_sys_seconds"):
                    values = [row[key] / row["requests"] for row in rows if key in row]
                    if values:
                        summary[key + "_per_request_median"] = statistics.median(values)
                rss = [row["process_peak_rss_bytes"] for row in rows if "process_peak_rss_bytes" in row]
                if rss:
                    summary["process_peak_rss_bytes_median"] = statistics.median(rss)
                report["summary"].append(summary)
        if source_identity(compiler_source, programs.values()) != report["source_identity"]:
            raise RuntimeError("compiler/workload sources changed during comparison")
        for label, path in compiler_sources.items():
            if source_identity(path, programs.values()) != report["arm_source_identities"][label]:
                raise RuntimeError(label + " compiler sources changed during comparison")
        for label, archive in archives.items():
            if digest(archive) != report["archives"][label]["sha256"]:
                raise RuntimeError(label + " archive changed during comparison")
        for label, override in report["tool_overrides"].items():
            if digest(override["CC"]) != override["sha256"]:
                raise RuntimeError(label + " compiler wrapper changed during comparison")
        report["complete"] = True
        save(args.output, report)
    print(json.dumps(report["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
