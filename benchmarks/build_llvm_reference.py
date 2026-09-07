"""Build explicit external LLVM references for an already optimized IR snapshot.

This diagnostic is never imported by a compiler product path. The manifest
contains runtime_ir (module name -> path); paths resolve beside the manifest.
It saves the exact codegen input for reuse by self, explicit target-machine
options, tool identities, assembly and object hashes. No IR optimization pass
is rerun: this isolates machine-code generation on the supplied IR.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--return-address-policy", choices=("existing", "all"), default="existing")
    parser.add_argument("--cpu", default="")
    parser.add_argument("--features", default="")
    args = parser.parse_args()
    manifest = args.manifest.resolve(strict=True)
    spec = json.loads(manifest.read_text())
    sources = {name: (manifest.parent / path).resolve(strict=True)
               for name, path in spec["runtime_ir"].items()}
    if not sources or any(not name.replace("_", "").isalnum() for name in sources):
        parser.error("nonempty named runtime IR modules required")
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    import llvmlite
    from llvmlite import binding as llvm

    llvm.initialize_all_targets()
    llvm.initialize_all_asmprinters()
    llvm.initialize_native_asmparser()
    inputs = [manifest, Path(__file__).resolve(), Path(sys.executable), *sources.values()]
    inputs.extend(Path(llvm.__file__).parent.glob("libllvmlite*"))
    hashes = {str(path): digest(path) for path in inputs if path.is_file()}
    report = {"schema": "pcc-gateway.llvm-reference-build.v1", "complete": False,
              "claim": "external reference only; target-machine O2 on saved IR; no IR passes rerun",
              "llvmlite_version": llvmlite.__version__, "llvm_version": llvm.llvm_version_info,
              "input_sha256": hashes, "return_address_policy": args.return_address_policy,
              "target_machine": {"cpu": args.cpu, "features": args.features, "opt": 2,
                                 "reloc": "default", "codemodel": "jitdefault"}, "modules": []}

    def save():
        temporary = out / "build-report.json.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(out / "build-report.json")

    save()
    for name, path in sources.items():
        text = path.read_text()
        if args.return_address_policy == "all":
            if '"sign-return-address"' in text or '"branch-target-enforcement"' in text:
                raise ValueError("input already declares a return-address policy: " + name)
            lines = text.splitlines()
            definitions = 0
            for index, line in enumerate(lines):
                if line.startswith("define "):
                    if not line.rstrip().endswith("{"):
                        raise ValueError("expected a normalized one-line function header")
                    lines[index] = line.rstrip()[:-1] + '"branch-target-enforcement" "sign-return-address"="all" "sign-return-address-key"="a_key" {'
                    definitions += 1
            if not definitions:
                raise ValueError("no function definitions: " + name)
            text = "\n".join(lines) + "\n"
        module = llvm.parse_assembly(text)
        module.verify()
        if args.return_address_policy == "all" and llvm.get_triple_parts(module.triple).Arch != "aarch64":
            raise ValueError("all-function return-address policy is an AArch64 diagnostic")
        target = llvm.Target.from_triple(module.triple)
        machine = target.create_target_machine(cpu=args.cpu, features=args.features, opt=2,
                                               reloc="default", codemodel="jitdefault")
        if str(module.data_layout) and str(module.data_layout) != str(machine.target_data):
            raise ValueError("module and target data layout differ")
        codegen_input = out / (name + ".ll")
        codegen_input.write_text(text)
        assembly, obj = out / (name + ".s"), out / (name + ".o")
        obj.write_bytes(machine.emit_object(module))
        assembly_module = llvm.parse_assembly(text)
        assembly_module.verify()
        assembly.write_text(machine.emit_assembly(assembly_module))
        report["modules"].append({"name": name, "triple": module.triple,
                                  "codegen_ir_sha256": digest(codegen_input),
                                  "assembly_sha256": digest(assembly), "object_sha256": digest(obj)})
        save()
        print(name, flush=True)
    for path, expected in hashes.items():
        if digest(path) != expected:
            raise RuntimeError("input changed during build: " + path)
    report["complete"] = True
    save()


if __name__ == "__main__":
    main()
