"""Repeat the unchanged handler workload in one process and read the
allocator's own accounting, to separate reachable retention from mapped
memory the allocator never reuses or returns."""
import argparse, ast, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/jiamo/my/pcc-gateway")
sys.path.insert(0, str(ROOT / "benchmarks"))
from compare import digest

OBSERVER = '''"""Native diagnostic only; keep unsafe imports outside the measured module."""
from pcc.unsafe import global_addr, load_i32, load_i64


def tracked() -> int:
    return load_i32(global_addr("py_gc_tracked_count"), 0)


def live_requested() -> int:
    return load_i64(global_addr("pcc_allocator_live_requested"), 0)


def live_usable() -> int:
    return load_i64(global_addr("pcc_allocator_live_usable"), 0)


def mapped() -> int:
    return load_i64(global_addr("pcc_allocator_mapped"), 0)


def metadata_mapped() -> int:
    return load_i64(global_addr("pcc_allocator_metadata_mapped"), 0)


def fully_free_slabs() -> int:
    return load_i64(global_addr("pcc_allocator_fully_free_slabs"), 0)


def granule_count() -> int:
    return load_i64(global_addr("pcc_allocator_granule_count"), 0)
'''

PROBE_TAIL = '''import gc
from memory_observer import (tracked, live_requested, live_usable, mapped,
                             metadata_mapped, fully_free_slabs, granule_count)
def report(label):
    print(label, tracked(), live_requested(), live_usable(), mapped(),
          metadata_mapped(), fully_free_slabs(), granule_count())
def run_probe():
    task = vt.spawn(benchmark)
    result = run_until_complete(task)
    print("requests", result["requests"])
def main():
    report("before")
    index = 0
    while index < int(sys.argv[4]):
        run_probe()
        report("after")
        gc.collect()
        report("collected")
        index += 1
main()
'''


def probe_source(source):
    tree = ast.parse(source)
    assert isinstance(tree.body[-1], ast.Expr)
    assert ast.unparse(tree.body[-1]) == "main()"
    tree.body = [n for n in tree.body[:-1]
                 if not (isinstance(n, ast.FunctionDef) and n.name == "main")]
    tree.body.extend(ast.parse(PROBE_TAIL).body)
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pcc", default=shutil.which("pcc"))
    p.add_argument("--compiler-source", type=Path, required=True)
    p.add_argument("--runtime-archive", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=4)
    p.add_argument("--rounds", type=int, default=100)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if not a.pcc or a.output.exists():
        p.error("select a compiler and a new output")
    import pcc
    core = Path(pcc.__file__).resolve().parents[1]
    sys.path.insert(0, str(core / "scripts"))
    from run_pcc_compile_ab import _performance_lock

    cs = a.compiler_source.resolve(); archive = a.runtime_archive.resolve()
    env = dict(os.environ, PYTHONPATH=str(cs), PCC_SOURCE_ROOT=str(cs),
               PCC_REPO_ROOT=str(cs), PCC_RUNTIME_ARCHIVE=str(archive),
               PCC_RUNTIME_CC="/usr/bin/false", PCC_GC_BACKEND="0",
               PCC_WITH_THREADS="0", PCC_RUNTIME_HIGH="py")
    env.pop("LC_ALL", None); env.pop("PCC_PACKAGE_SITE", None)
    with _performance_lock():
        build = ROOT / "benchmarks/build" / a.output.stem
        build.mkdir(parents=True, exist_ok=False)
        src = build / "memory_probe_app.py"
        src.write_text(probe_source((ROOT / "benchmark_native.py").read_text()))
        (build / "memory_observer.py").write_text(OBSERVER)
        exe = src.with_suffix("")
        report = {"schema": "pcc-gateway.memory-accounting.v1", "complete": False,
                  "started_utc": datetime.now(timezone.utc).isoformat(),
                  "compiler_source": str(cs), "archive_sha256": digest(archive),
                  "probe_sha256": digest(src), "gc_backend": 0,
                  "rounds": a.rounds, "repeats": a.repeats,
                  "columns": ["label", "tracked", "live_requested", "live_usable",
                              "mapped", "metadata_mapped", "fully_free_slabs",
                              "granule_count"]}
        cmd = [a.pcc, "--backend", "self", "--python-libpython", "off",
               "--ir-scaffold", "on", str(src), "-o", str(exe)]
        with (build / "compile.log").open("w") as log:
            c = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log,
                               stderr=subprocess.STDOUT, timeout=180)
        if c.returncode:
            report["compile_log"] = (build / "compile.log").read_text()[-3000:]
            a.output.write_text(json.dumps(report, indent=2) + "\n")
            raise RuntimeError("probe compilation failed: " + str(build))
        r = subprocess.run([str(exe), "100", "0", str(a.rounds), str(a.repeats)],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        report.update(command=cmd, artifact_sha256=digest(exe), returncode=r.returncode,
                      stdout=r.stdout, stderr=r.stderr)
        rows = [ln.split() for ln in r.stdout.splitlines() if not ln.startswith("requests")]
        report["rows"] = [[x[0]] + [int(v) for v in x[1:]] for x in rows]
        report["complete"] = r.returncode == 0
        a.output.write_text(json.dumps(report, indent=2) + "\n")
        print(r.stdout)
        if r.returncode:
            print(r.stderr[-2000:], file=sys.stderr)


main()
