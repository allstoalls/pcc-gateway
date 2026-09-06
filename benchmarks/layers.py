"""Diagnose handler costs; these ablations do not replace the full benchmark."""

import argparse
import ast
import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

from compare import ROOT, digest, process_metrics, save, source_tree_digest


def variant_source(source, mode):
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    request = functions["request"]
    # Preserve the original timer, JSON encoder, byte validation and result.
    assert isinstance(request.body[2], ast.Try)
    original_data = copy.deepcopy(request.body[2].body[-1])
    assert isinstance(original_data, ast.Assign) and original_data.targets[0].id == "data"
    prefix = [request.body[0]]
    tail = request.body[3:]
    if mode == "scope":
        return source
    if mode == "direct":
        setup = ast.parse('''profile = vt.spawn(fetch_profile, delay_ms)
notifications = None
joined = False
try:
    notifications = vt.spawn(fetch_notifications, delay_ms)
    vt.join(profile)
    vt.join(notifications)
    joined = True
finally:
    if not joined:
        vt.cancel(profile)
        try:
            vt.join(profile)
        except Exception:
            pass
        if notifications is not None:
            vt.cancel(notifications)
            try:
                vt.join(notifications)
            except Exception:
                pass
''').body
        for value in original_data.value.values:
            assert isinstance(value, ast.Call) and value.func.attr == "result"
            value.func.value = ast.Name(id="vt", ctx=ast.Load())
        setup[-1].body.append(original_data)
        request.body = prefix + setup + tail
    elif mode == "json-only":
        # This mode deliberately removes child tasks/waits to establish a floor.
        original_data.value.values = [
            copy.deepcopy(functions[name].body[-1].value)
            for name in ("fetch_profile", "fetch_notifications")
        ]
        request.body = prefix + [original_data] + tail
    else:
        raise ValueError(mode)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcc", default=shutil.which("pcc"))
    parser.add_argument("--runtime-archive", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=20000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.pcc or args.requests < 1 or args.repeats < 1 or args.output.exists():
        parser.error("select a compiler, positive requests/repeats and a new output")
    import pcc
    core = Path(pcc.__file__).resolve().parents[1]
    sys.path.insert(0, str(core / "scripts"))
    from run_pcc_compile_ab import _performance_lock

    environment = dict(os.environ, PCC_RUNTIME_ARCHIVE=str(args.runtime_archive.resolve()),
        PCC_RUNTIME_CC="/usr/bin/false", PCC_GC_BACKEND="0", PCC_WITH_THREADS="0",
        PCC_RUNTIME_HIGH="py", PCC_GENERATOR_FIRST_ENTRY_INIT="1")
    environment.pop("LC_ALL", None)
    environment.pop("PCC_PACKAGE_SITE", None)
    with _performance_lock():
        build = ROOT / "benchmarks/build" / args.output.stem
        build.mkdir(parents=True, exist_ok=False)
        report = {"schema": "pcc-gateway.handler-layers.v1", "complete": False,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "claim": "Diagnostic ablations with different task/cleanup shapes, not replacement application QPS",
            "compiler_source_sha256": source_tree_digest(core),
            "runtime_archive_sha256": digest(args.runtime_archive),
            "base_source_sha256": digest(ROOT / "benchmark_native.py"),
            "asyncio_source_sha256": digest(ROOT / "benchmark_asyncio.py"),
            "python_version": sys.version, "compilers": {}, "runs": [], "summary": []}
        save(args.output, report)
        commands = {}
        for mode in ("scope", "direct", "json-only"):
            source = build / ("diagnostic_" + mode.replace("-", "_") + ".py")
            source.write_text(variant_source((ROOT / "benchmark_native.py").read_text(), mode))
            binary = source.with_suffix("")
            command = [args.pcc, "--backend", "self", "--python-libpython", "off",
                       "--ir-scaffold", "on", str(source), "-o", str(binary)]
            print("Compiling " + mode, flush=True)
            with (build / (mode + "-compile.log")).open("w") as log:
                compiled = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
                    stderr=subprocess.STDOUT, timeout=120)
            if compiled.returncode:
                raise RuntimeError(mode + " compilation failed: " + str(build))
            report["compilers"][mode] = {"source": str(source), "source_sha256": digest(source),
                "artifact_sha256": digest(binary), "command": command}
            commands[mode] = [str(binary)]
            save(args.output, report)
        commands["asyncio"] = [sys.executable, str(ROOT / "benchmark_asyncio.py")]
        rounds = max(1, math.ceil(args.requests / 100))
        labels = list(commands)
        for repeat in range(args.repeats):
            shift = repeat % len(labels)
            for mode in labels[shift:] + labels[:shift]:
                command = commands[mode] + ["100", "0", str(rounds), "--summary"]
                if sys.platform == "darwin":
                    command = ["/usr/bin/time", "-lp", *command]
                result = subprocess.run(command, cwd=ROOT, env=environment,
                    capture_output=True, text=True, timeout=30)
                if result.returncode:
                    raise RuntimeError(mode + ": " + result.stdout + result.stderr)
                row = json.loads(result.stdout)
                if (row["requests"] != 100 * rounds or row["warmup_requests"] != 200
                        or row["delay_ms"] != 0 or row["concurrency"] != 100
                        or not math.isfinite(row["elapsed_ms"]) or row["elapsed_ms"] <= 0
                        or not (0 <= row["latency_min_ms"] <= row["latency_max_ms"])
                        or not math.isfinite(row["latency_max_ms"])):
                    raise RuntimeError("invalid " + mode + ": " + repr(row))
                row.update(implementation=mode, repetition=repeat, **process_metrics(result.stderr))
                report["runs"].append(row)
                save(args.output, report)
                print(f"{mode}: {row['requests'] * 1000 / row['elapsed_ms']:.1f} QPS", flush=True)
        for mode in labels:
            rows = [x for x in report["runs"] if x["implementation"] == mode]
            rates = [x["requests"] * 1000 / x["elapsed_ms"] for x in rows]
            report["summary"].append({"implementation": mode,
                "qps_median": statistics.median(rates), "qps_min": min(rates), "qps_max": max(rates),
                "instructions_per_request": statistics.median(x.get("process_instructions", 0) / x["requests"] for x in rows),
                "user_cpu_per_request": statistics.median(x.get("process_user_seconds", 0) / x["requests"] for x in rows)})
        if source_tree_digest(core) != report["compiler_source_sha256"]:
            raise RuntimeError("compiler source changed during diagnostic")
        if digest(args.runtime_archive) != report["runtime_archive_sha256"]:
            raise RuntimeError("runtime changed during diagnostic")
        report["complete"] = True
        save(args.output, report)
    print(json.dumps(report["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
