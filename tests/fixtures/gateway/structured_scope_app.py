"""Native failure propagation and rejected-fork lifetime canary."""

import pcc.virtual_thread as vt
from pcc_gateway.structured import TaskScope, TaskScopeError, run_until_complete


def failing():
    vt.yield_now()
    raise ValueError("child failed")


def sleeping():
    vt.sleep_current(10000)
    return 42


def probe():
    scope = TaskScope("failure")
    first = scope.fork(vt.spawn(failing))
    sibling = scope.fork(vt.spawn(sleeping))
    observed = ""
    try:
        scope.join()
    except ValueError as error:
        observed = str(error)
    finally:
        scope.close()
    if observed != "child failed":
        raise RuntimeError("child failure was lost")
    if vt.outcome(first) != vt.OUTCOME_RAISED:
        raise RuntimeError("failing child did not terminate")
    if vt.outcome(sibling) != vt.OUTCOME_CANCELLED:
        raise RuntimeError("sibling survived the scope")
    closed = TaskScope("closed")
    closed.close()
    rejected = vt.spawn(sleeping)
    refused = False
    try:
        closed.fork(rejected)
    except TaskScopeError:
        refused = True
    if not refused or vt.outcome(rejected) != vt.OUTCOME_CANCELLED:
        raise RuntimeError("rejected fork left an orphan")
    return "PCC1_STRUCTURED_FAILURE_CLEANUP_OK"


def main():
    print(run_until_complete(vt.spawn(probe)))


main()
