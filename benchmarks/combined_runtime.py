"""Controlled combined-runtime experiment, including GC/failure gates.

Host pcc emits application objects with its self backend. External LLVM merges
the selected runtime IR and emits O0 objects in every merged arm; pcc's owned
passes are the only optimization difference. This is an explicit reference
experiment, not owned runtime construction or an installation qualification.
Run under core's process-tree watchdog and performance lock.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from processes import run_command


ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "py_obj", "py_gen", "py_coroutine", "py_virtual_thread_runtime",
    "py_gc_backend", "py_list", "py_dict", "py_class", "py_obj_dealloc",
    "freestanding_gc_index_table", "freestanding_runtime_high_substrate",
    "freestanding_thread_kernel",
)
PASSES = ("inline-defined", "instcombine", "simplifycfg", "dce")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcc-source", type=Path, required=True)
    parser.add_argument("--runtime-archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--extra-module", action="append", default=[],
                        help="additional measured runtime owner to include in the same pipeline")
    args = parser.parse_args()
    source = args.pcc_source.resolve(strict=True)
    archive = args.runtime_archive.resolve(strict=True)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(source))
    from llvmlite import binding as llvm
    from pcc.py_frontend import pipeline
    from pcc.py_frontend.compiled_owned_passes import run_owned_passes
    from pcc.backend.macho_assemble_worker import assemble_asm_path_to_encoded
    from pcc.backend.native_object import decode_packed_native_object
    from pcc.backend.macho_exec import link_executable
    from pcc.tools.ir_to_obj import _emit_object_with_triple

    env = dict(os.environ)
    for key in list(env):
        if key.startswith("PCC_DIRECT_INDEXED_"):
            env.pop(key)
    env.pop("LC_ALL", None)
    env.update(PCC_SOURCE_ROOT=str(source), PCC_REPO_ROOT=str(source),
               PYTHONPATH=str(source), PCC_RUNTIME_ARCHIVE=str(archive),
               PCC_RUNTIME_CC="/usr/bin/false", PCC_GC_BACKEND="0",
               PCC_KNOWN_OBJECT_REFS="1", PCC_GENERATOR_FIRST_ENTRY_INIT="1",
               PCC_FAST_COMPLETED_CONTINUATIONS="1", PCC_DIRECT_GENERATOR_TASKS="1",
               PCC_DISABLE_BULK_GENERATOR_FRAME_INIT="1",
               PCC_PY_FRONTEND_JOBS="4", PCC_SELF_BACKEND_JOBS="4")
    os.environ.clear()
    os.environ.update(env)
    source_hashes = {str(p.relative_to(source)): digest(p)
                     for p in sorted((source / "pcc").rglob("*.py"))}
    report = {
        "schema": "pcc-gateway.combined-runtime.v1", "complete": False,
        "scope": "host-owned passes; external LLVM merge and O0 runtime emission; self application emission/linking",
        "pcc_source": str(source), "source_hashes": source_hashes,
        "runtime_archive": {"path": str(archive), "sha256": digest(archive)},
        "llvm_version": llvm.llvm_version_info, "script_sha256": digest(__file__),
        "environment": {k: v for k, v in env.items() if k.startswith("PCC_")},
        "runtime_ir": {}, "passes": [], "programs": {}, "artifacts": {}, "gates": [],
    }

    def save():
        (out / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")

    save()
    records = json.loads(Path(str(archive) + ".provenance.json").read_text())["members"]
    merged = None
    selected = list(MODULES)
    for name in args.extra_module:
        if not name.replace("_", "").isalnum() or name in selected:
            parser.error("extra runtime modules must be unique module names")
        selected.append(name)
    report["selected_modules"] = selected
    for name in selected:
        path = archive.parent / "build_py" / (name + ".ll")
        checksum = digest(path)
        record = next(item for item in records if item["member"] == name + ".o")
        if record["ir_sha256"] != checksum:
            raise RuntimeError("runtime IR differs from archive receipt: " + name)
        report["runtime_ir"][name] = {"path": str(path), "sha256": checksum}
        module = llvm.parse_assembly(path.read_text())
        module.verify()
        if merged is None:
            merged = module
        else:
            merged.link_in(module)
    text = str(merged)
    (out / "merged-input.ll").write_text(text)
    overlays = {}
    for round_number in range(3):
        label = "merged_o0" if round_number == 0 else "owned_round" + str(round_number)
        if round_number:
            for name in PASSES:
                before = text
                started = time.monotonic()
                text = run_owned_passes(text, [name], False)
                path = out / (label + "-" + name + ".ll")
                path.write_text(text)
                llvm.parse_assembly(text).verify()
                report["passes"].append({
                    "round": round_number, "name": name, "changed": text != before,
                    "seconds": time.monotonic() - started,
                    "input_bytes": len(before.encode()), "output_bytes": len(text.encode()),
                    "sha256": digest(path),
                })
                save()
        print("emit " + label, flush=True)
        blob, triple = _emit_object_with_triple(text, optimization_level=0)
        path = out / (label + ".o")
        path.write_bytes(blob)
        overlays[label] = blob
        report["artifacts"][label] = {"path": str(path), "sha256": digest(path), "triple": triple}
        save()

    # Consume the existing core regression program instead of copying a GC or
    # ownership implementation into the gateway benchmark.
    regression = ROOT.parent / "pcc/tests/python/test_known_object_refcounts.py"
    candidates = [node.value for node in ast.walk(ast.parse(regression.read_text()))
                  if isinstance(node, ast.Constant) and isinstance(node.value, str)
                  and "class Resurrect:" in node.value and "VERIFY_CHECKS" in node.value]
    if len(candidates) != 1:
        raise RuntimeError("core ownership regression template is ambiguous")
    probe = out / "ownership_probe.py"
    probe.write_text(candidates[0].replace("VERIFY_CHECKS", "1"))
    programs = {
        "benchmark": ROOT / "benchmark_native.py",
        "cleanup": ROOT / "tests/fixtures/gateway/structured_scope_app.py",
        "ownership": probe,
    }
    report["ownership_test_source"] = {"path": str(regression), "sha256": digest(regression)}

    class CapturedLink(Exception):
        pass

    for name, path in programs.items():
        print("compile " + name, flush=True)
        captured = []
        original = subprocess.run

        def capture(command, *call_args, **kwargs):
            if isinstance(command, (list, tuple)) and any(
                str(item).endswith("/scripts/pcc_link_macho.py") for item in command
            ):
                for index, item in enumerate(command[:-1]):
                    if item == "--asm":
                        assembly = out / (name + "-app-" + str(len(captured)) + ".s")
                        shutil.copyfile(command[index + 1], assembly)
                        captured.append(assembly)
                raise CapturedLink()
            return original(command, *call_args, **kwargs)

        subprocess.run = capture
        try:
            pipeline.compile_python(str(path), str(out / (name + "-unlinked")),
                                    backend="self", libpython_mode="off", ir_scaffold_mode="on",
                                    runtime_archive=str(archive))
        except CapturedLink:
            pass
        finally:
            subprocess.run = original
        if not captured:
            raise RuntimeError("self application object capture failed: " + name)
        objects = []
        for assembly in captured:
            packed = assemble_asm_path_to_encoded(str(assembly))
            assembly.with_suffix(".pco").write_bytes(packed)
            objects.append(decode_packed_native_object(packed))
        report["programs"][name] = {"source": str(path), "sha256": digest(path), "binaries": {}}
        for label in ("baseline", *overlays):
            native = list(objects)
            if label != "baseline":
                native.append(overlays[label])
            image = link_executable(native, archives=[archive.read_bytes()])
            binary = out / (name + "-" + label)
            binary.write_bytes(image)
            binary.chmod(0o755)
            report["programs"][name]["binaries"][label] = {"path": str(binary), "sha256": digest(binary)}
            save()
            for backend in range(5):
                command = [str(binary)]
                if name == "benchmark":
                    command += ["100", "0", "2", "--summary"]
                result = run_command(command, env=dict(env, PCC_GC_BACKEND=str(backend)),
                                     cwd=ROOT, capture_output=True, text=True, timeout=25)
                gate = {"program": name, "arm": label, "gc": backend,
                        "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
                report["gates"].append(gate)
                save()
                if result.returncode:
                    raise RuntimeError(str(gate))
                if name == "benchmark":
                    sample = json.loads(result.stdout)
                    if sample["requests"] != 200 or sample["warmup_requests"] != 200:
                        raise RuntimeError("benchmark workload mismatch")
                else:
                    expected = "PCC1_STRUCTURED_FAILURE_CLEANUP_OK" if name == "cleanup" else "[1, 2, 3, 4, 5]"
                    if result.stdout.strip() != expected:
                        raise RuntimeError(str(gate))
            print("validated " + name + " " + label + " GC0-4", flush=True)
    if digest(archive) != report["runtime_archive"]["sha256"]:
        raise RuntimeError("runtime changed during experiment")
    for relative, checksum in source_hashes.items():
        if digest(source / relative) != checksum:
            raise RuntimeError("compiler source changed: " + relative)
    report["complete"] = True
    save()


if __name__ == "__main__":
    main()
