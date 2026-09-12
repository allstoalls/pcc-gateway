from pathlib import Path
import os,sys,json,hashlib,time
r=Path(__file__).resolve().parent;prior=r.parent/'2026-09-09-runtime-cfg-current';out=r/'early-cse-ab';out.mkdir(exist_ok=False)
source=prior/'address-source';sys.path.insert(0,str(source));sys.path.insert(0,str(r.parents[1]))
from pcc.py_frontend.compiled_owned_passes import run_owned_passes
from pcc.backend.native_object import decode_packed_native_object
from pcc.backend.macho_exec import link_executable
from pcc.tools.ir_to_obj import _emit_object_with_triple
from llvmlite import binding as llvm
archive=prior/'py_runtime_exact_start/libpy_runtime_pcc_py.a';base=json.loads((prior/'exact-cache-experiment/build-report.json').read_text());members=json.loads(Path(str(archive)+'.provenance.json').read_text())['members']
report={'complete':False,'scope':'performance-only experiment requested by user; no new GC/correctness suite; same application objects, owned passes and external LLVM O0 emission','runtime_sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),'inputs':{},'passes':[]}
def save():(out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
import re
text=(prior/'exact-cache-experiment/owned_round2-dce.ll').read_text()
report['input_sha256']=hashlib.sha256(text.encode()).hexdigest()
report['scope']='performance-only conservative owned local CSE on retained optimized runtime; external LLVM O0 emission; no correctness suite'
(out/'input.ll').write_text(text)
def counts(value):
 return {op:len(re.findall(r"\b"+op+r"\b",value)) for op in ['alloca','load','store','phi','call','br']}
report['counts_before']=counts(text)
import importlib.util
spec=importlib.util.spec_from_file_location('pcc.native_ir.early_cse_candidate',r/'early_cse.py')
cse=importlib.util.module_from_spec(spec);spec.loader.exec_module(cse)
report['candidate_source_sha256']=hashlib.sha256((r/'early_cse.py').read_bytes()).hexdigest()
for name in ['early-cse','simplifycfg','dce']:
 started=time.monotonic();before=text;text=cse.early_cse_text(text)[0] if name=='early-cse' else run_owned_passes(text,[name],False)
 report['passes'].append({'name':name,'changed':before!=text,'seconds':time.monotonic()-started,'counts':counts(text)});save()
report['counts_after']=counts(text)
(out/'optimized.ll').write_text(text);blob,triple=_emit_object_with_triple(text,optimization_level=0);(out/'runtime.o').write_bytes(blob)
objects=[decode_packed_native_object(p.read_bytes()) for p in sorted((prior/'exact-cache-experiment').glob('benchmark-app-*.pco'))];assert objects
image=link_executable([*objects,blob],archives=[archive.read_bytes()]);binary=out/'candidate';binary.write_bytes(image);binary.chmod(0o755)
report.update(complete=True,binary=str(binary),binary_sha256=hashlib.sha256(image).hexdigest(),triple=triple,correctness_qualification='NOT RUN');save();print('performance candidate built',flush=True)
