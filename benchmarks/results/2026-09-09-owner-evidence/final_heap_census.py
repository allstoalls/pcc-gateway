from pathlib import Path
import json,os,sys,shutil,hashlib
r=Path(__file__).resolve().parent
source=r/'census-final-source'
shutil.copytree(r/'post2-source',source,copy_function=shutil.copyfile)
p=source/'pcc/native_ir/driver.py';p.chmod(0o644)
s=p.read_text().replace('from pcc.extern import c_int64, extern','from pcc.extern import c_int64, c_void, extern')
s=s.replace('_heap_live_bytes = extern(', '_heap_census = extern("pcc_heap_census", (c_int64,), c_void)\n\n_heap_live_bytes = extern(')
s=s.replace('    index = 0\n', '    index = 0\n    _heap_census(0)\n')
s=s.replace('        changed = text != previous','        _heap_census(index + 1)\n        changed = text != previous')
p.write_text(s);p.chmod(0o444)
sys.path.insert(0,str(source));sys.path.insert(0,str(r.parents[1]))
from processes import run_command
archive=r/'py_runtime_leaf_fixed/libpy_runtime_pcc_py.a'
os.environ.update(PCC_SOURCE_ROOT=str(source),PCC_REPO_ROOT=str(source),PYTHONPATH=str(source),PCC_RUNTIME_ARCHIVE=str(archive),PCC_RUNTIME_CC='/usr/bin/false',PCC_HOST_PYTHON='/Users/jiamo/my/pcc/.venv/bin/python',PCC_PY_FRONTEND_JOBS='4',PCC_SELF_BACKEND_JOBS='4',PCC_GC_BACKEND='0')
helper=r.parents[0]/'2026-09-08-asyncio-challenge/heap_census_v4.c'
obj=r/'final-heap-census.o'
cmd=['/usr/bin/clang','-O2','-c',str(helper),'-I'+str(archive.parent/'src'),'-I'+str(archive.parent/'include'),'-o',str(obj)]
ran=run_command(cmd,timeout=20,capture_output=True,text=True);assert ran.returncode==0,ran.stderr
import pcc.py_frontend.pipeline as pipeline
original=pipeline._pipeline_self_link.build_pcc_link_command
def with_census(**kwargs):
 kwargs['extra_link_inputs']=tuple(kwargs.get('extra_link_inputs',()))+(str(obj),)
 return original(**kwargs)
pipeline._pipeline_self_link.build_pcc_link_command=with_census
binary=r/'final-heap-census-native'
pipeline.compile_python(str(p),str(binary),backend='self',libpython_mode='off',ir_scaffold_mode='on',runtime_archive=str(archive))
output=r/'final-heap-census-output.ll';tsv=r/'final-heap-census.tsv'
ran=run_command([str(binary),'inline-defined,instcombine,simplifycfg,dce',str(r/'lto-combined-input.ll'),str(output)],env=dict(os.environ,PCC_HEAP_CENSUS_FILE=str(tsv),PCC_OPT_PROFILE_MEMORY='1'),timeout=120,capture_output=True,text=True)
report={'scope':'GC0 quiescent census, same post2 optimizer/runtime; external clang diagnostic observer, not performance or ownership qualification','complete':False,'returncode':ran.returncode,'stderr':ran.stderr,'helper_command':cmd,'helper_source_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'runtime_sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),'binary_sha256':hashlib.file_digest(binary.open('rb'),'sha256').hexdigest(),'output_matches_uninstrumented':output.exists() and output.read_bytes()==(r/'native-post2-runtime.ll').read_bytes(),'phases':[]}
(r/'final-heap-census.json').write_text(json.dumps(report,indent=2)+'\n')
assert ran.returncode==0,ran.stderr
for line in tsv.read_text().splitlines():
 fields=line.split('\t')
 if fields[0]=='BEGIN': phase={'phase':int(fields[1]),'metrics':{},'types':[],'strings':[]};report['phases'].append(phase)
 elif fields[0]=='METRIC': phase['metrics'][fields[1]]=int(fields[2])
 elif fields[0]=='TYPE': phase['types'].append(dict(zip(['tag','count','requested','usable','backing_requested','refcount_one'],map(int,fields[1:7])),class_name=bytes.fromhex(fields[7]).decode(errors='replace')))
 elif fields[0]=='STRING': phase['strings'].append({'length':int(fields[1]),'count':int(fields[2]),'requested':int(fields[3]),'prefix':bytes.fromhex(fields[4]).decode(errors='replace')})
for phase in report['phases']:
 phase['strings'].sort(key=lambda x:x['requested'],reverse=True)
 phase['types'].sort(key=lambda x:x['requested']+x['backing_requested'],reverse=True)
 assert phase['metrics']['bad_headers']==0
 assert phase['metrics']['live_requested']==phase['metrics']['live_requested_after_walk']
assert report['output_matches_uninstrumented']
report['complete']=True;(r/'final-heap-census.json').write_text(json.dumps(report,indent=2)+'\n')
print('census complete',flush=True)
