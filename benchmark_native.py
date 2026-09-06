"""Matched two-fetch/JSON workload for pcc and pcc1 native artifacts."""

import json
import sys
import time

import pcc.virtual_thread as vt
from pcc_gateway.structured import TaskScope, run_until_complete


def fetch_profile(delay_ms: int):
    vt.sleep_current(delay_ms)
    return {"name": "Ada", "plan": "pro"}


def fetch_notifications(delay_ms: int):
    vt.sleep_current(delay_ms)
    return ["Your report is ready"]


def request(delay_ms: int):
    started = time.perf_counter()
    scope = TaskScope("request")
    try:
        profile = scope.fork(vt.spawn(fetch_profile, delay_ms))
        notifications = scope.fork(vt.spawn(fetch_notifications, delay_ms))
        scope.join()
        data = {"profile": scope.result(profile),
                "notifications": scope.result(notifications)}
    finally:
        scope.close()
    body = json.dumps(data, sort_keys=True).encode()
    expected = b'{"notifications": ["Your report is ready"], "profile": {"name": "Ada", "plan": "pro"}}'
    if body != expected:
        raise RuntimeError("benchmark response mismatch: " + body.decode())
    return (time.perf_counter() - started) * 1000.0


def batch(concurrency: int, delay_ms: int):
    scope = TaskScope("batch")
    try:
        index = 0
        while index < concurrency:
            scope.fork(vt.spawn(request, delay_ms))
            index += 1
        scope.join()
        samples = []
        for child in scope.children:
            samples.append(scope.result(child))
        return samples
    finally:
        scope.close()


def benchmark():
    concurrency = int(sys.argv[1])
    delay_ms = int(sys.argv[2])
    rounds = int(sys.argv[3])
    warmup = batch(concurrency, delay_ms)
    second_warmup = batch(concurrency, delay_ms)
    warmup_requests = len(warmup) + len(second_warmup)
    samples = []
    started = time.perf_counter()
    index = 0
    while index < rounds:
        completed = batch(concurrency, delay_ms)
        samples.extend(completed)
        index += 1
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {"concurrency": concurrency, "delay_ms": delay_ms,
            "rounds": rounds, "requests": len(samples),
            "warmup_requests": warmup_requests,
            "elapsed_ms": elapsed_ms, "latencies_ms": samples}


def main():
    thread = vt.spawn(benchmark)
    result = run_until_complete(thread)
    # Profilers need the request phase, without spending their samples on
    # formatting the final latency array. Normal comparison runs retain it.
    if len(sys.argv) > 4 and sys.argv[4] == "--summary":
        samples = result.pop("latencies_ms")
        result["latency_min_ms"] = min(samples)
        result["latency_max_ms"] = max(samples)
    print(json.dumps(result, sort_keys=True))


main()
