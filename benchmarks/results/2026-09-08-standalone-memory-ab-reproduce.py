"""One-run two-module attribution; inputs are frozen next to this file."""
import hashlib
import importlib.abc
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / 'candidate-source'))

class RejectLLVM(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'llvmlite' or fullname.startswith('llvmlite.') or fullname == 'pcc.llvm_capi.binding':
            raise RuntimeError('External LLVM import: ' + fullname)
sys.meta_path.insert(0, RejectLLVM())

from pcc.native_ir.driver import optimize_ir
from pcc.backend.self_backend_aarch64_darwin import emit_aarch64_darwin_asm

inputs = ROOT / 'runtime-valid-raw-input'
output = Path(sys.argv[2]).resolve()
output.mkdir(exist_ok=False)
manifest = json.loads((inputs / 'inputs.json').read_text())
old = 'instsimplify,simplifycfg,inline-defined,instsimplify,simplifycfg,instcombine,dce'
passes = {'control': old, 'candidate': 'mem2reg,sroa,' + old}
report = {'complete': False, 'claim': manifest['claim'], 'input_manifest': manifest,
          'passes': passes, 'modules': [], 'artifacts': {}}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save():
    (output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')

def counts(text):
    return {'alloca': text.count(' = alloca '), 'load': text.count(' = load '),
            'store': text.count('  store '), 'phi': text.count(' = phi ')}

save()
for arm, selected in passes.items():
    assemblies = []
    for name in ('py_obj', 'py_list'):
        path = inputs / (name + '.ll')
        before = path.read_text()
        print(arm, name, 'optimize', flush=True)
        started = time.perf_counter()
        after = optimize_ir(before, selected)
        ir = output / (arm + '-' + name + '.ll')
        ir.write_text(after)
        print(arm, name, counts(before), '->', counts(after), 'emit', flush=True)
        assembly = output / (arm + '-' + name + '.s')
        assembly.write_text(emit_aarch64_darwin_asm(after))
        assemblies.append(assembly)
        report['modules'].append({'arm': arm, 'module': name, 'before': counts(before),
            'after': counts(after), 'input_sha256': digest(path), 'ir_sha256': digest(ir),
            'assembly_sha256': digest(assembly), 'seconds': time.perf_counter() - started})
        save()
    binary = output / arm
    command = [sys.executable, str(ROOT / 'candidate-source/scripts/pcc_link_macho.py'),
        '--out', str(binary), '--archive', str(inputs / 'libpy_runtime_pcc_py.a')]
    for p in (inputs / 'app-0.pco', inputs / 'app-1.pco'):
        command.extend(['--native-object', str(p)])
    for p in assemblies:
        command.extend(['--asm', str(p)])
    print(arm, 'link', flush=True)
    ran = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (output / (arm + '-link.log')).write_text(ran.stdout + ran.stderr)
    if ran.returncode:
        raise RuntimeError(arm + ' link failed')
    ran = subprocess.run([str(binary), '100', '0', '2', '--summary'],
        capture_output=True, text=True, timeout=15)
    (output / (arm + '-smoke.log')).write_text(ran.stdout + ran.stderr)
    if ran.returncode:
        raise RuntimeError(arm + ' execution failed')
    row = json.loads(ran.stdout)
    assert row['requests'] == 200 and row['warmup_requests'] == 200
    report['artifacts'][arm] = {'path': str(binary), 'sha256': digest(binary),
        'link_command': command, 'smoke': row}
    save()
for name, expected in manifest['files'].items():
    assert digest(inputs / name) == expected
report['complete'] = True
save()
