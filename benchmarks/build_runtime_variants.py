"""Build an isolated runtime-emission comparison from recorded IR inputs.

The JSON manifest supplies pcc_root, pcc1, optimizer, runtime_archive,
app_ir (list of paths), and runtime_ir (module-name -> path). Relative paths
are resolved against the manifest directory. This diagnostic still uses host
CPython for pcc's parser/codec/linker and a partially prebuilt runtime.
Run under pcc/scripts/run_process_tree_sample.py for an RSS cap and watchdog.
"""

import argparse
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import subprocess
import sys


PASSES = "mem2reg,sroa,instsimplify,simplifycfg,inline-defined,instsimplify,simplifycfg,instcombine,dce"
GUARD = '''import importlib.abc
import sys
class RejectLLVM(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "llvmlite" or fullname.startswith("llvmlite.") or fullname == "pcc.llvm_capi.binding":
            raise ImportError("LLVM import blocked: " + fullname)
sys.meta_path.insert(0, RejectLLVM())
'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = args.manifest.resolve(strict=True)
    spec = json.loads(manifest.read_text())

    def resolve(value):
        return (manifest.parent / value).resolve(strict=True)

    root, pcc1, optimizer, archive = (resolve(spec[key]) for key in
                                     ("pcc_root", "pcc1", "optimizer", "runtime_archive"))
    apps = [resolve(path) for path in spec["app_ir"]]
    modules = {name: resolve(path) for name, path in spec["runtime_ir"].items()}
    if not apps or not modules or any(not name.replace("_", "").isalnum() for name in modules):
        parser.error("supply application IR and named runtime modules")
    for binary in (pcc1, optimizer):
        with binary.open("rb") as stream:
            if stream.read(4) != b"\xcf\xfa\xed\xfe":
                parser.error("Darwin native executables required, not wrappers")
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "sitecustomize.py").write_text(GUARD)
    exec(GUARD, {})
    sys.path.insert(0, str(root))
    from pcc.backend.self_backend_parse import parse_self_backend_module
    from pcc.backend.self_backend_kernel import get_indexed_function_kernel
    from pcc.backend.self_backend_indexed_codec import encode_indexed_module_file
    from pcc.backend.native_object import decode_native_object

    inputs = [manifest, Path(__file__).resolve(), pcc1, optimizer, archive, Path(sys.executable),
              root / "scripts/pcc_link_macho.py", *apps, *modules.values()]
    inputs.extend(sorted((root / "pcc").rglob("*.py")))
    hashes = {str(path): digest(path) for path in inputs}
    report = {"schema": "pcc-gateway.runtime-emission-build.v1", "complete": False,
              "claim": "same app objects; selected runtime members re-emitted; remaining members prebuilt",
              "reference_provenance": spec.get("reference_provenance", "unspecified prebuilt archive"),
              "host_owned_steps": ["IR parsing", "indexed encoding", "Mach-O linking"],
              "native_steps": ["owned IR passes", "PCO emission"],
              "input_sha256": hashes, "passes": PASSES, "steps": [], "artifacts": {}}

    def save():
        temporary = out / "build-report.json.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(out / "build-report.json")

    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PCC_") and key not in ("LC_ALL", "PYTHONPATH", "PYTHONHOME")}
    env.update(PCC_HOST_PYTHON="/usr/bin/false", PCC_RUNTIME_CC="/usr/bin/false",
               CC="/usr/bin/false", PATH="/nonexistent", PCC_GC_BACKEND="0")
    report["native_environment"] = {key: env[key] for key in
                                    ("PCC_HOST_PYTHON", "PCC_RUNTIME_CC", "CC", "PATH", "PCC_GC_BACKEND")}
    save()

    def run(name, command, execution_env=env):
        command = list(map(str, command))
        print(name, flush=True)
        with (out / (name + ".log")).open("w") as log:
            result = subprocess.run(command, cwd=root, env=execution_env,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=90)
        report["steps"].append({"name": name, "command": command, "returncode": result.returncode})
        save()
        if result.returncode:
            raise RuntimeError(name + " failed; see log")

    def emit(name, path):
        module = parse_self_backend_module(path.read_text())
        for function in module.functions:
            get_indexed_function_kernel(function)
        sidecar, pco = out / (name + ".pidx"), out / (name + ".pco")
        encode_indexed_module_file(str(sidecar), module)
        run(name + "-emit", [pcc1, "--pcc-self-backend-indexed-emit-worker", sidecar, pco, "PCO"])
        if not decode_native_object(pco.read_bytes()).sections:
            raise RuntimeError("empty native object: " + name)
        report["artifacts"][name] = {"path": str(pco), "sha256": digest(pco)}
        save()
        return pco

    app_objects = [emit("app-" + str(index), path) for index, path in enumerate(apps)]
    variants = {"reference": [], "self-control": [], "self-owned": []}
    for name, path in modules.items():
        variants["self-control"].append(emit(name + "-control", path))
        optimized = out / (name + "-owned.ll")
        run(name + "-optimize", [optimizer, PASSES, path, optimized])
        variants["self-owned"].append(emit(name + "-owned", optimized))
    link_env = dict(env, PYTHONPATH=str(out) + os.pathsep + str(root))
    for name, objects in variants.items():
        binary = out / (name + "-linked")
        command = [sys.executable, root / "scripts/pcc_link_macho.py", "--out", binary, "--archive", archive]
        for pco in app_objects + objects:
            command.extend(["--native-object", pco])
        run(name + "-link", command, link_env)
        run(name + "-smoke", [binary, "100", "0", "2", "--summary"])
        sample = json.loads((out / (name + "-smoke.log")).read_text())
        if any(sample[key] != value for key, value in
               (("requests", 200), ("warmup_requests", 200), ("concurrency", 100), ("delay_ms", 0))):
            raise RuntimeError(name + " workload count mismatch")
        report["artifacts"][name] = {"path": str(binary), "sha256": digest(binary)}
    for path, original in hashes.items():
        if digest(path) != original:
            raise RuntimeError("input changed during build: " + path)
    report["complete"] = True
    save()


if __name__ == "__main__":
    main()
