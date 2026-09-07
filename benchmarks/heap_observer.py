"""Native diagnostic only; keep unsafe imports outside the measured module.

Importing pcc.unsafe into the workload changes its lowering mode, which can
change ownership behavior. This module only reads the GC's live-object count.
"""

from pcc.unsafe import global_addr, load_i32


def tracked() -> int:
    return load_i32(global_addr("py_gc_tracked_count"), 0)
