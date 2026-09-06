# pcc-gateway

pcc virtual-thread gateway (HTTP/1.1 server, reverse proxy, DNS, TLS provider) extracted from the pcc compiler core

Seeded from `allstoalls/pcc` at commit `2574f585` (2026-09-06) with the same
relative layout as the core repository, so the core can drop these paths in a
follow-up extraction task without renaming anything. The code still depends on
the pcc compiler and runtime (`pcc/py_runtime`, `pcc.unsafe`, `pcc.extern`);
build and test it against an installed pcc from the core repository.

Files copied (see `SEED_FILES.txt`): 48 tracked paths.

Status: seed copy only. The core repository keeps the originals until the
extraction task on its task board (docs/goal/task-board.yaml) removes them
behind the bootstrap and runtime-archive gates.
