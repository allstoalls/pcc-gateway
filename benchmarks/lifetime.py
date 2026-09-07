"""Repeat the unchanged handler workload in one process and count live objects."""

import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from compare import ROOT, digest, save
from runtime_ab import source_identity


def probe_source(source):
    tree = ast.parse(source)
    assert isinstance(tree.body[-1], ast.Expr)
    assert ast.unparse(tree.body[-1]) == "main()"
    tree.body = [node for node in tree.body[:-1]
                 if not (isinstance(node, ast.FunctionDef) and node.name == "main")]
    tree.body.extend(ast.parse('''import gc
from heap_observer import tracked
def run_probe():
    task = vt.spawn(benchmark)
    result = run_until_complete(task)
    print("requests", result["requests"])
def main():
    print("before", tracked())
    index = 0
    while index < int(sys.argv[4]):
        run_probe()
        print("after", tracked())
        print("collected", gc.collect())
        print("remaining", tracked())
        index += 1
main()
''').body)
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcc", default=shutil.which("pcc"))
    parser.add_argument("--compiler-source", type=Path, required=True)
    parser.add_argument("--runtime-archive", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.pcc or min(args.repeats, args.rounds) < 1 or args.output.exists():
        parser.error("select a compiler, positive counts and a new output")
    import pcc
    core = Path(pcc.__file__).resolve().parents[1]
    sys.path.insert(0, str(core / "scripts"))
    from run_pcc_compile_ab import _performance_lock

    compiler_source = args.compiler_source.resolve()
    archive = args.runtime_archive.resolve()
    environment = dict(os.environ, PYTHONPATH=str(compiler_source),
        PCC_SOURCE_ROOT=str(compiler_source), PCC_REPO_ROOT=str(compiler_source),
        PCC_RUNTIME_ARCHIVE=str(archive), PCC_RUNTIME_CC="/usr/bin/false",
        PCC_GC_BACKEND="0", PCC_WITH_THREADS="0", PCC_RUNTIME_HIGH="py")
    environment.pop("LC_ALL", None)
    environment.pop("PCC_PACKAGE_SITE", None)
    with _performance_lock():
        build = ROOT / "benchmarks/build" / args.output.stem
        build.mkdir(parents=True, exist_ok=False)
        source = build / "lifetime_probe.py"
        source.write_text(probe_source((ROOT / "benchmark_native.py").read_text()))
        observer = build / "heap_observer.py"
        shutil.copyfile(Path(__file__).with_name("heap_observer.py"), observer)
        executable = source.with_suffix("")
        identity = source_identity(compiler_source)
        report = {"schema": "pcc-gateway.lifetime.v1", "complete": False,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "compiler_source": str(compiler_source), "source_identity": identity,
            "archive_sha256": digest(archive), "probe_sha256": digest(source),
            "observer_sha256": digest(observer), "gc_backend": 0,
            "optimization_environment": {key: environment.get(key, "0") for key in
                ("PCC_GENERATOR_FIRST_ENTRY_INIT", "PCC_FAST_COMPLETED_CONTINUATIONS",
                 "PCC_DIRECT_GENERATOR_TASKS")}}
        save(args.output, report)
        command = [args.pcc, "--backend", "self", "--python-libpython", "off",
                   "--ir-scaffold", "on", str(source), "-o", str(executable)]
        with (build / "compile.log").open("w") as log:
            compiled = subprocess.run(command, cwd=ROOT, env=environment,
                stdout=log, stderr=subprocess.STDOUT, timeout=120)
        if compiled.returncode:
            raise RuntimeError("lifetime compilation failed: " + str(build))
        ran = subprocess.run([str(executable), "100", "0", str(args.rounds), str(args.repeats)],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60)
        report.update(command=command, artifact_sha256=digest(executable),
                      stdout=ran.stdout, stderr=ran.stderr, returncode=ran.returncode)
        save(args.output, report)
        pairs = [line.split() for line in ran.stdout.splitlines()]
        expected_labels = ["before"] + ["requests", "after", "collected", "remaining"] * args.repeats
        assert ran.returncode == 0, ran.stderr
        assert [pair[0] for pair in pairs] == expected_labels, ran.stdout
        assert all(int(pair[1]) == 100 * args.rounds for pair in pairs if pair[0] == "requests")
        report["live_counts"] = [int(pair[1]) for pair in pairs if pair[0] in ("before", "remaining")]
        assert source_identity(compiler_source) == identity
        assert digest(archive) == report["archive_sha256"]
        report["complete"] = True
        save(args.output, report)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
