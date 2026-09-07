# AGENTS.md

## Compiler dependency contract (maintainer directive, 2026-09-07)

Host pcc may depend only on CPython and the Python standard library. Native
pcc1 must require no external toolchain or language-runtime dependencies.
Apply the same contract when changing the compiler in `../pcc`; its
`AGENTS.md` contains the full compiler workflow and verification rules.

- Remove LLVM/libLLVM, llvmlite, cc/clang/gcc and equivalent dependencies from
  compiler product paths. Third-party Python packages are not acceptable
  host-pcc dependencies. pcc1 must not require host Python or libpython.
- This covers C as well as Python: preprocessing, parsing, optimization,
  code generation, runtime construction, assembly, linking and installation
  must use pcc-owned implementations. C/extension builds are not exceptions.
- pcc1 operations must execute as pcc-owned native code, built into pcc1 or
  supplied with the pcc toolchain. Delegating to a Python subprocess, external
  assembler/linker/archiver or bundled LLVM does not satisfy the contract.
- Existing dependencies are unfinished migration work. Fix the compiler or
  gateway at the actual boundary; do not make applications select a legacy
  fallback, install host tools or accept weaker semantics to pass a benchmark.
- Keep performance scripts reproducible and validate emitted programs. Label
  LLVM/cc comparisons as external reference experiments; their gains do not
  establish pcc1-owned optimization or a qualified default toolchain.

The target OS's kernel/platform ABI is the execution boundary. These are
required architectural principles, not a claim that migration is complete.

## Work and validation

Use the shared qualified `~/.local/bin/pcc1` through PATH for normal use.
Keep experimental compilers isolated until the core installation gates pass.
Both repositories use Python 3.15.0rc1 for host work and the asyncio baseline.
Retain exact benchmark inputs, compiler/runtime identities and raw results.
Keep the main README concise and put diagnostic details in benchmark notes.
