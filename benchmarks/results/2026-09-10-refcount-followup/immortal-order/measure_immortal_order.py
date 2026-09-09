from pathlib import Path
import os,sys,json,hashlib,time
r=Path(__file__).resolve().parent;prior=r.parent/'2026-09-09-runtime-cfg-current';out=r/'immortal-ab';out.mkdir(exist_ok=False)
source=prior/'address-source';sys.path.insert(0,str(source));sys.path.insert(0,str(r.parents[1]))
from pcc.py_frontend.compiled_owned_passes import run_owned_passes
from pcc.backend.native_object import decode_packed_native_object
from pcc.backend.macho_exec import link_executable
from pcc.tools.ir_to_obj import _emit_object_with_triple
from llvmlite import binding as llvm
archive=r/'py_runtime_immortal_order/libpy_runtime_pcc_py.a';base=json.loads((prior/'exact-cache-experiment/build-report.json').read_text());members=json.loads(Path(str(archive)+'.provenance.json').read_text())['members']
report={'complete':False,'scope':'performance-only experiment requested by user; no new GC/correctness suite; same application objects, owned passes and external LLVM O0 emission','runtime_sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),'inputs':{},'passes':[]}
def save():(out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
merged=None
for name in base['runtime_ir']:
 path=archive.parent/'build_py'/(name+'.ll');data=path.read_bytes();checksum=hashlib.sha256(data).hexdigest();record=next(m for m in members if m['member']==name+'.o');assert record['ir_sha256']==checksum
 report['inputs'][name]=checksum;module=llvm.parse_assembly(data.decode());module.verify()
 if merged is None:merged=module
 else:merged.link_in(module)
text=str(merged);(out/'input.ll').write_text(text)
for iteration in range(2):
 for name in ['inline-defined','instcombine','simplifycfg','dce']:
  started=time.monotonic();before=text;text=run_owned_passes(text,[name],False)
  report['passes'].append({'round':iteration+1,'name':name,'changed':before!=text,'seconds':time.monotonic()-started});save()
(out/'optimized.ll').write_text(text);blob,triple=_emit_object_with_triple(text,optimization_level=0);(out/'runtime.o').write_bytes(blob)
objects=[decode_packed_native_object(p.read_bytes()) for p in sorted((prior/'exact-cache-experiment').glob('benchmark-app-*.pco'))];assert objects
image=link_executable([*objects,blob],archives=[archive.read_bytes()]);binary=out/'candidate';binary.write_bytes(image);binary.chmod(0o755)
report.update(complete=True,binary=str(binary),binary_sha256=hashlib.sha256(image).hexdigest(),triple=triple,correctness_qualification='NOT RUN');save();print('performance candidate built',flush=True)
