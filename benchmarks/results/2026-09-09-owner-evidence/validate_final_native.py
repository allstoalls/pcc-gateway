from pathlib import Path
import hashlib,json,os,sys
r=Path(__file__).resolve().parent
sys.path.insert(0,str(r.parents[1]))
from processes import run_command
b=Path('/Users/jiamo/my/pcc/build/gateway-direct-owner-stage1-20260909')
source=b/'source-snapshot';compiler=b/'pcc1'
env=dict(os.environ,PYTHONPATH=str(source),PCC_SOURCE_ROOT=str(source),PCC_REPO_ROOT=str(source),PCC_HOST_PYTHON='/Users/jiamo/my/pcc/.venv/bin/python',PCC_RUNTIME_ARCHIVE=str(r/'py_runtime_leaf_fixed/libpy_runtime_pcc_py.a'),PCC_RUNTIME_CC='/usr/bin/false')
report={'complete':False,'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),'build_scope':'normal-mode native execution of direct-built candidate; Stage1 harness failed native-direct smoke; not a qualified full build or fixed point','runs':[]}
for name,path,expected in [('tuple',r/'tuple_iterator.py','TUPLE_ITERATOR_OK'),('bool',Path('/Users/jiamo/my/pcc-gateway/benchmarks/build/2026-09-09-quota30-runtime/exact_bool_conversion.py'),'input True\noutput True'),('records',Path('/Users/jiamo/my/pcc-gateway/benchmarks/build/2026-09-09-quota30-runtime/internal-record-source/pcc/record_relocation_probe.py'),'NATIVE_RECORD_RELOCATION_OK'),('cleanup',r.parents[2]/'tests/fixtures/gateway/structured_scope_app.py','PCC1_STRUCTURED_FAILURE_CLEANUP_OK')]:
    binary=r/('final-'+name)
    with (r/('final-'+name+'-compile.log')).open('w') as log:
        result=run_command([str(compiler),str(path),'-o',str(binary)],env=env,cwd=r.parents[2],stdout=log,stderr=-2,timeout=150)
    assert result.returncode==0,name
    for backend in range(5):
        result=run_command([str(binary)],env=dict(env,PCC_GC_BACKEND=str(backend)),capture_output=True,text=True,timeout=15)
        report['runs'].append(dict(name=name,backend=backend,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr));(r/'final-native-validation.json').write_text(json.dumps(report,indent=2)+'\n')
        assert result.returncode==0,(name,backend,result.stderr)
        assert result.stdout.strip()==expected,(name,backend,result.stdout)
report['complete']=True;(r/'final-native-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('20 native GC cases passed',flush=True)
