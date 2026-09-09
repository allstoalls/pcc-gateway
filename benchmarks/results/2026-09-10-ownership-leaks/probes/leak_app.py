"""Attribute the per-request live-byte growth by layer.

Each phase runs the same shape as benchmark_native.request() up to a point,
so the difference between two phases is the layer added between them.
"""
import json
import sys
import time

import pcc.virtual_thread as vt
from pcc_gateway.structured import TaskScope, run_until_complete

from memory_observer import live_requested, live_usable, mapped, tracked


def trivial(unused: int):
    return 1


def fetch_profile(delay_ms: int):
    vt.sleep_current(delay_ms)
    return {"name": "Ada", "plan": "pro"}


def fetch_notifications(delay_ms: int):
    vt.sleep_current(delay_ms)
    return ["Your report is ready"]


def phase_spawn_only(n: int):
    index = 0
    while index < n:
        thread = vt.spawn(trivial, 0)
        scope = TaskScope("p")
        try:
            child = scope.fork(thread)
            scope.join()
            scope.result(child)
        finally:
            scope.close()
        index += 1
    return 0


def phase_two_children(n: int):
    index = 0
    while index < n:
        scope = TaskScope("p")
        try:
            a = scope.fork(vt.spawn(trivial, 0))
            b = scope.fork(vt.spawn(trivial, 0))
            scope.join()
            scope.result(a)
            scope.result(b)
        finally:
            scope.close()
        index += 1
    return 0


def phase_dict_results(n: int):
    index = 0
    while index < n:
        scope = TaskScope("p")
        try:
            a = scope.fork(vt.spawn(fetch_profile, 0))
            b = scope.fork(vt.spawn(fetch_notifications, 0))
            scope.join()
            data = {"profile": scope.result(a), "notifications": scope.result(b)}
        finally:
            scope.close()
        index += 1
    return 0


def phase_full_request(n: int):
    index = 0
    while index < n:
        scope = TaskScope("request")
        try:
            a = scope.fork(vt.spawn(fetch_profile, 0))
            b = scope.fork(vt.spawn(fetch_notifications, 0))
            scope.join()
            data = {"profile": scope.result(a), "notifications": scope.result(b)}
        finally:
            scope.close()
        body = json.dumps(data, sort_keys=True).encode()
        if len(body) != 86:
            raise RuntimeError("unexpected body")
        index += 1
    return 0


FIXED = '{"notifications": ["Your report is ready"], "profile": {"name": "Ada", "plan": "pro"}}'


def phase_encode_only(n: int):
    index = 0
    while index < n:
        body = FIXED.encode()
        if len(body) != 86:
            raise RuntimeError("unexpected body")
        index += 1
    return 0


def phase_dumps_only(n: int):
    data = {"profile": {"name": "Ada", "plan": "pro"},
            "notifications": ["Your report is ready"]}
    index = 0
    while index < n:
        text = json.dumps(data, sort_keys=True)
        if len(text) != 86:
            raise RuntimeError("unexpected text")
        index += 1
    return 0


def phase_dumps_unsorted(n: int):
    data = {"profile": {"name": "Ada", "plan": "pro"},
            "notifications": ["Your report is ready"]}
    index = 0
    while index < n:
        text = json.dumps(data)
        if len(text) != 86:
            raise RuntimeError("unexpected text")
        index += 1
    return 0


def phase_dumps_small(n: int):
    index = 0
    while index < n:
        text = json.dumps({"a": 1})
        if len(text) != 8:
            raise RuntimeError("unexpected small text")
        index += 1
    return 0


LONG_DATA = {"items": ["Your report is ready" for _ in range(40)]}


def phase_dumps_long(n: int):
    data = LONG_DATA
    index = 0
    while index < n:
        text = json.dumps(data)
        if len(text) != 971:
            raise RuntimeError("unexpected long text " + str(len(text)))
        index += 1
    return 0


def phase_str_join(n: int):
    parts = ["Your report is ready", "and another one here"]
    index = 0
    while index < n:
        text = ",".join(parts)
        if len(text) != 41:
            raise RuntimeError("unexpected join " + str(len(text)))
        index += 1
    return 0


def phase_str_format(n: int):
    index = 0
    while index < n:
        text = str(12345678)
        if len(text) != 8:
            raise RuntimeError("unexpected str")
        index += 1
    return 0


SPLIT_ME = "alpha,beta,gamma,delta"
LOAD_ME = '{"a": [1, 2, 3], "b": "text"}'


def phase_str_split(n: int):
    index = 0
    while index < n:
        parts = SPLIT_ME.split(",")
        if len(parts) != 4:
            raise RuntimeError("unexpected split")
        index += 1
    return 0


def phase_json_loads(n: int):
    index = 0
    while index < n:
        value = json.loads(LOAD_ME)
        if len(value) != 2:
            raise RuntimeError("unexpected loads")
        index += 1
    return 0


def phase_str_upper(n: int):
    index = 0
    while index < n:
        text = SPLIT_ME.upper()
        if len(text) != 22:
            raise RuntimeError("unexpected upper")
        index += 1
    return 0


def timed_child(delay_ms: int):
    started = time.perf_counter()
    vt.sleep_current(delay_ms)
    return (time.perf_counter() - started) * 1000.0


def phase_perf_only(n: int):
    index = 0
    while index < n:
        moment = time.perf_counter()
        if moment < 0.0:
            raise RuntimeError("clock")
        index += 1
    return 0


def phase_perf_delta(n: int):
    index = 0
    while index < n:
        started = time.perf_counter()
        elapsed = (time.perf_counter() - started) * 1000.0
        if elapsed < 0.0:
            raise RuntimeError("elapsed")
        index += 1
    return 0


def phase_child_float(n: int):
    index = 0
    while index < n:
        scope = TaskScope("f")
        try:
            child = scope.fork(vt.spawn(timed_child, 0))
            scope.join()
            value = scope.result(child)
            if value < 0.0:
                raise RuntimeError("child value")
        finally:
            scope.close()
        index += 1
    return 0


def phase_list_collect(n: int):
    index = 0
    while index < n:
        scope = TaskScope("f")
        try:
            child = scope.fork(vt.spawn(timed_child, 0))
            scope.join()
            samples = []
            for kid in scope.children:
                samples.append(scope.result(kid))
            if len(samples) != 1:
                raise RuntimeError("samples")
        finally:
            scope.close()
        index += 1
    return 0


def float_sub_only(x, n: int):
    index = 0
    while index < n:
        y = x - 0.5
        if y < 0.0:
            raise RuntimeError("sub")
        index += 1
    return 0


def float_mul_chain(x, n: int):
    index = 0
    while index < n:
        y = (x - 0.5) * 1000.0
        if y < 0.0:
            raise RuntimeError("chain")
        index += 1
    return 0


def phase_float_sub(n: int):
    return float_sub_only(2.5, n)


def phase_float_chain(n: int):
    return float_mul_chain(2.5, n)


def report(label: str):
    print(label, tracked(), live_requested(), live_usable(), mapped())


def main():
    n = int(sys.argv[1])
    # warm every path once so first-touch allocation is not attributed
    run_until_complete(vt.spawn(phase_spawn_only, 1))
    run_until_complete(vt.spawn(phase_two_children, 1))
    run_until_complete(vt.spawn(phase_dict_results, 1))
    run_until_complete(vt.spawn(phase_full_request, 1))
    run_until_complete(vt.spawn(phase_encode_only, 1))
    run_until_complete(vt.spawn(phase_dumps_only, 1))
    run_until_complete(vt.spawn(phase_dumps_unsorted, 1))
    run_until_complete(vt.spawn(phase_dumps_small, 1))
    run_until_complete(vt.spawn(phase_dumps_long, 1))
    run_until_complete(vt.spawn(phase_str_join, 1))
    run_until_complete(vt.spawn(phase_str_format, 1))
    run_until_complete(vt.spawn(phase_str_split, 1))
    run_until_complete(vt.spawn(phase_json_loads, 1))
    run_until_complete(vt.spawn(phase_str_upper, 1))
    run_until_complete(vt.spawn(phase_perf_only, 1))
    run_until_complete(vt.spawn(phase_perf_delta, 1))
    run_until_complete(vt.spawn(phase_child_float, 1))
    run_until_complete(vt.spawn(phase_list_collect, 1))
    run_until_complete(vt.spawn(phase_float_sub, 1))
    run_until_complete(vt.spawn(phase_float_chain, 1))
    report("warm")
    run_until_complete(vt.spawn(phase_float_sub, n))
    report("float_sub")
    run_until_complete(vt.spawn(phase_float_chain, n))
    report("float_chain")
    run_until_complete(vt.spawn(phase_perf_only, n))
    report("perf_only")
    run_until_complete(vt.spawn(phase_perf_delta, n))
    report("perf_delta")
    run_until_complete(vt.spawn(phase_child_float, n))
    report("child_float")
    run_until_complete(vt.spawn(phase_list_collect, n))
    report("list_collect")
    run_until_complete(vt.spawn(phase_str_upper, n))
    report("str_upper")
    run_until_complete(vt.spawn(phase_str_split, n))
    report("str_split")
    run_until_complete(vt.spawn(phase_json_loads, n))
    report("json_loads")
    run_until_complete(vt.spawn(phase_str_format, n))
    report("str_int")
    run_until_complete(vt.spawn(phase_str_join, n))
    report("str_join")
    run_until_complete(vt.spawn(phase_dumps_long, n))
    report("dumps_891char")
    run_until_complete(vt.spawn(phase_encode_only, n))
    report("encode_only")
    run_until_complete(vt.spawn(phase_dumps_small, n))
    report("dumps_small")
    run_until_complete(vt.spawn(phase_dumps_unsorted, n))
    report("dumps_unsorted")
    run_until_complete(vt.spawn(phase_dumps_only, n))
    report("dumps_sorted")
    run_until_complete(vt.spawn(phase_spawn_only, n))
    report("spawn_only")
    run_until_complete(vt.spawn(phase_two_children, n))
    report("two_children")
    run_until_complete(vt.spawn(phase_dict_results, n))
    report("dict_results")
    run_until_complete(vt.spawn(phase_full_request, n))
    report("full_request")


main()
