"""Re-emit fixed runtime IR using explicit native pcc emitters and link variants.

Manifest: pcc_root, runtime_archive, app_objects, variants. Each variant has
an emitter and runtime_ir mapping, or reference_objects (externally emitted
objects retained with an explicit reference_provenance). Relative paths use
the manifest directory. Host CPython runs pcc's parser/codec/linker; native
emitters run with host Python and external compilers disabled. Remaining
archive members and application PCOs stay fixed. This is a diagnostic builder,
not a complete source-to-native toolchain qualification.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from build_runtime_variants import GUARD, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = args.manifest.resolve(strict=True)
    spec = json.loads(manifest.read_text())

    def resolve(path):
        return (manifest.parent / path).resolve(strict=True)

    root = resolve(spec["pcc_root"])
    archive = resolve(spec["runtime_archive"])
    apps = [resolve(path) for path in spec["app_objects"]]
    variants = spec["variants"]
    if not apps or not variants:
        parser.error("application objects and variants are required")
    for name, variant in variants.items():
        if not name.replace("-", "").replace("_", "").isalnum():
            parser.error("invalid variant name")
        if "reference_objects" in variant:
            if not variant.get("reference_provenance") or "emitter" in variant:
                parser.error("reference objects require provenance and cannot select an emitter")
            variant["reference_objects"] = [resolve(path) for path in variant["reference_objects"]]
        else:
            variant["emitter"] = resolve(variant["emitter"])
            with variant["emitter"].open("rb") as stream:
                if stream.read(4) != b"\xcf\xfa\xed\xfe":
                    parser.error("emitter must be a native Darwin executable")
            variant["runtime_ir"] = {name: resolve(path) for name, path in variant["runtime_ir"].items()}
            if not variant["runtime_ir"] or any(not name.replace("_", "").isalnum() for name in variant["runtime_ir"]):
                parser.error("nonempty named runtime IR modules required")
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "sitecustomize.py").write_text(GUARD)
    exec(GUARD, {})
    sys.path.insert(0, str(root))
    from pcc.backend.self_backend_parse import parse_self_backend_module
    from pcc.backend.self_backend_kernel import get_indexed_function_kernel
    from pcc.backend.self_backend_indexed_codec import encode_indexed_module_file
    from pcc.backend.native_object import decode_native_object

    paths = [manifest, Path(__file__).resolve(), Path(sys.executable), archive, *apps]
    paths.extend(sorted((root / "pcc").rglob("*.py")))
    paths.append(root / "scripts/pcc_link_macho.py")
    for variant in variants.values():
        if "reference_objects" in variant:
            paths.extend(variant["reference_objects"])
        else:
            paths.extend([variant["emitter"], *variant["runtime_ir"].values()])
    hashes = {str(path): digest(path) for path in paths}
    report = {"schema": "pcc-gateway.codegen-matrix-build.v1", "complete": False,
              "host_owned_steps": ["IR parsing", "indexed encoding", "Mach-O linking"],
              "native_steps": ["self PCO emission with target passes enabled"],
              "claim": "fixed application PCOs and remaining archive; selected runtime members re-emitted",
              "input_sha256": hashes, "steps": [], "artifacts": {},
              "reference_provenance": {name: variant.get("reference_provenance") for name, variant in variants.items()}}

    def save():
        temporary = out / "build-report.json.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(out / "build-report.json")

    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PCC_") and key not in ("LC_ALL", "PYTHONPATH", "PYTHONHOME")}
    env.update(PATH="/nonexistent", PCC_HOST_PYTHON="/usr/bin/false",
               PCC_RUNTIME_CC="/usr/bin/false", CC="/usr/bin/false", PCC_GC_BACKEND="0")
    link_env = dict(env, PYTHONPATH=str(out) + os.pathsep + str(root))
    report["native_environment"] = {key: env[key] for key in ("PATH", "PCC_HOST_PYTHON", "PCC_RUNTIME_CC", "CC", "PCC_GC_BACKEND")}
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

    for label, variant in variants.items():
        objects = []
        if "reference_objects" not in variant:
            for name, path in variant["runtime_ir"].items():
                module = parse_self_backend_module(path.read_text())
                for function in module.functions:
                    get_indexed_function_kernel(function)
                sidecar, pco = out / (label + "-" + name + ".pidx"), out / (label + "-" + name + ".pco")
                encode_indexed_module_file(str(sidecar), module)
                run(label + "-" + name, [variant["emitter"], sidecar, pco, "PCO", "1"])
                if not decode_native_object(pco.read_bytes()).sections:
                    raise RuntimeError("empty PCO: " + name)
                objects.append(pco)
                report["artifacts"][label + "-" + name] = {"path": str(pco), "sha256": digest(pco)}
        binary = out / label
        command = [sys.executable, root / "scripts/pcc_link_macho.py", "--out", binary, "--archive", archive]
        for path in apps + objects:
            command.extend(["--native-object", path])
        for path in variant.get("reference_objects", []):
            command.extend(["--object", path])
        run(label + "-link", command, link_env)
        run(label + "-smoke", [binary, "100", "0", "2", "--summary"])
        sample = json.loads((out / (label + "-smoke.log")).read_text())
        if any(sample[key] != value for key, value in (("requests", 200), ("warmup_requests", 200), ("concurrency", 100), ("delay_ms", 0))):
            raise RuntimeError("workload mismatch: " + label)
        report["artifacts"][label] = {"path": str(binary), "sha256": digest(binary)}
        save()
    for path, original in hashes.items():
        if digest(path) != original:
            raise RuntimeError("input changed during build: " + path)
    report["complete"] = True
    save()


if __name__ == "__main__":
    main()
