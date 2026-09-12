# `time.sleep` has no native lowering, so the event loop's idle wait routed
# `_Loop._run_once` through CPython: under --python-libpython=off the whole
# method was replaced by a fail-closed stub and any loop that ever went idle
# died with
#
#   NotImplementedError: no-libpython function unavailable: asyncio._run_once
#
# The fix uses `pcc_platform_sleep_ns`, the runtime's own portable primitive,
# which the freestanding platform module already exports -- nothing new in the
# runtime archive. `time.sleep` itself is still a gap for user programs; this
# file is that gap's reproduction. CPython prints "slept".
import time


def main() -> None:
    time.sleep(0.001)
    print("slept")


main()
