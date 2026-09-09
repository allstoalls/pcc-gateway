from pathlib import Path
import sys,os,json,hashlib
r=Path(__file__).resolve().parent;source=r/'post2-source';sys.path.insert(0,str(source));sys.path.insert(0,str(r.parents[1]))
from pcc.py_frontend.compiled_owned_passes import run_owned_passes
from processes import run_command
compiler=Path('/Users/jiamo/my/pcc/.venv/bin/pcc')
env=dict(os.environ,PCC_SOURCE_ROOT=str(source),PCC_REPO_ROOT=str(source),PYTHONPATH=str(source),PCC_RUNTIME_ARCHIVE=str(r/'py_runtime_leaf_fixed/libpy_runtime_pcc_py.a'),PCC_RUNTIME_CC='/usr/bin/false',PCC_HOST_PYTHON='/Users/jiamo/my/pcc/.venv/bin/python',PCC_PY_FRONTEND_JOBS='4',PCC_SELF_BACKEND_JOBS='4')
binary=r/'native-post2-driver';report={'complete':False,'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),'compiler_kind':'host pcc builds native optimizer; runtime execution is native','runs':[]}
with (r/'native-post2-compile.log').open('w') as log:
    built=run_command([str(compiler),str(source/'pcc/native_ir/driver.py'),'-o',str(binary)],env=env,cwd=r.parents[2],stdout=log,stderr=-2,timeout=180)
report['build_returncode']=built.returncode;(r/'native-post2-gate.json').write_text(json.dumps(report,indent=2)+'\n');assert built.returncode==0
input_path=r/'inline-loop-input.ll';expected=run_owned_passes(input_path.read_text(),['inline-defined','instcombine','simplifycfg','dce'],False)
for backend in range(5):
    output=r/('native-post2-loop-gc'+str(backend)+'.ll')
    ran=run_command([str(binary),'inline-defined,instcombine,simplifycfg,dce',str(input_path),str(output)],env=dict(env,PCC_GC_BACKEND=str(backend)),capture_output=True,text=True,timeout=30)
    same=output.exists() and output.read_text()==expected
    report['runs'].append({'backend':backend,'returncode':ran.returncode,'matches_host':same,'stdout':ran.stdout,'stderr':ran.stderr})
    (r/'native-post2-gate.json').write_text(json.dumps(report,indent=2)+'\n');assert ran.returncode==0 and same,(backend,ran.stderr)
report['small_gc_complete']=True;
input_path=r/'lto-combined-input.ll'; output=r/'native-post2-runtime.ll';expected=run_owned_passes(input_path.read_text(),['inline-defined','instcombine','simplifycfg','dce'],False)
with (r/'native-post2-runtime.stdout').open('w') as out_log, (r/'native-post2-runtime.stderr').open('w') as err_log:
    ran=run_command([str(binary),'inline-defined,instcombine,simplifycfg,dce',str(input_path),str(output)],env=dict(env,PCC_GC_BACKEND='0',PCC_OPT_PROFILE_MEMORY='1'),stdout=out_log,stderr=err_log,text=True,timeout=120)
same=output.exists() and output.read_text()==expected
report['real_runtime']={'returncode':ran.returncode,'matches_host':same,'stdout':(r/'native-post2-runtime.stdout').read_text(),'stderr':(r/'native-post2-runtime.stderr').read_text()}
(r/'native-post2-gate.json').write_text(json.dumps(report,indent=2)+'\n');assert ran.returncode==0 and same,ran.stderr
report['complete']=True;report['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest();(r/'native-post2-gate.json').write_text(json.dumps(report,indent=2)+'\n');print('5 native optimizer GC cases passed')
