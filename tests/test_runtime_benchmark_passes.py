"""The runtime-emission diagnostic must include owned memory promotion."""

from pathlib import Path
import runpy

from pcc.native_ir.driver import optimize_ir


def test_runtime_pass_manifest_promotes_cross_block_memory():
    script = Path(__file__).resolve().parents[1] / "benchmarks/build_runtime_variants.py"
    passes = runpy.run_path(str(script))["PASSES"]
    source = '''define i64 @choose(i1 %condition) {
entry:
  %slot = alloca i64
  br i1 %condition, label %yes, label %no
yes:
  store i64 7, ptr %slot
  br label %done
no:
  store i64 9, ptr %slot
  br label %done
done:
  %value = load i64, ptr %slot
  ret i64 %value
}
'''
    result = optimize_ir(source, passes)
    assert "alloca" not in result
    assert "load i64" not in result
    assert "store i64" not in result
    assert "select i1 %condition, i64 7, i64 9" in result
