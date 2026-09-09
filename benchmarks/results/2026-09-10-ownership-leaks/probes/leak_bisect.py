import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
ROOT = Path("/Users/jiamo/my/pcc-gateway")
sys.path.insert(0, str(ROOT / "benchmarks"))
from compare import digest
SP = Path(__file__).resolve().parent
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
'''
p = argparse.ArgumentParser()
p.add_argument("--compiler-source", type=Path, required=True)
p.add_argument("--runtime-archive", type=Path, required=True)
p.add_argument("--iterations", type=int, default=20000)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
import pcc
core = Path(pcc.__file__).resolve().parents[1]
sys.path.insert(0, str(core / "scripts"))
from run_pcc_compile_ab import _performance_lock
cs = a.compiler_source.resolve(); archive = a.runtime_archive.resolve()
env = dict(os.environ, PYTHONPATH=str(cs), PCC_SOURCE_ROOT=str(cs), PCC_REPO_ROOT=str(cs),
           PCC_RUNTIME_ARCHIVE=str(archive), PCC_RUNTIME_CC="/usr/bin/false",
           PCC_GC_BACKEND="0", PCC_WITH_THREADS="0", PCC_RUNTIME_HIGH="py")
env.pop("LC_ALL", None); env.pop("PCC_PACKAGE_SITE", None)
with _performance_lock():
    build = ROOT / "benchmarks/build" / a.output.stem
    build.mkdir(parents=True, exist_ok=True)
    src = build / "leak_app.py"
    shutil.copyfile(SP / "leak_app.py", src)
    (build / "memory_observer.py").write_text(OBSERVER)
    exe = src.with_suffix("")
    cmd = [shutil.which("pcc"), "--backend", "self", "--python-libpython", "off",
           "--ir-scaffold", "on", str(src), "-o", str(exe)]
    with (build / "compile.log").open("w") as log:
        c = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
    if c.returncode:
        print((build / "compile.log").read_text()[-2500:], file=sys.stderr)
        raise SystemExit("compile failed")
    r = subprocess.run([str(exe), str(a.iterations)], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=240)
    print(r.stdout)
    if r.returncode: print(r.stderr[-2000:], file=sys.stderr)
    rows = [ln.split() for ln in r.stdout.splitlines() if ln.split()]
    out = {"schema": "pcc-gateway.leak-bisect.v1", "iterations": a.iterations,
           "archive_sha256": digest(archive), "probe_sha256": digest(src),
           "columns": ["label", "tracked", "live_requested", "live_usable", "mapped"],
           "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
           "rows": [[x[0]] + [int(v) for v in x[1:]] for x in rows if len(x) == 5]}
    a.output.write_text(json.dumps(out, indent=2) + "\n")
