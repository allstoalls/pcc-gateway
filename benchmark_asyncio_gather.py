"""Identical asyncio.gather workload for native pcc and CPython."""

import asyncio
import json
import sys
import time


async def fetch_profile(delay_ms: int):
    await asyncio.sleep(delay_ms / 1000)
    return {"name": "Ada", "plan": "pro"}


async def fetch_notifications(delay_ms: int):
    await asyncio.sleep(delay_ms / 1000)
    return ["Your report is ready"]


async def request(delay_ms: int):
    started = time.perf_counter()
    fetched = await asyncio.gather(
        fetch_profile(delay_ms), fetch_notifications(delay_ms))
    data = {"profile": fetched[0], "notifications": fetched[1]}
    body = json.dumps(data, sort_keys=True).encode()
    expected = b'{"notifications": ["Your report is ready"], "profile": {"name": "Ada", "plan": "pro"}}'
    if body != expected:
        raise RuntimeError("benchmark response mismatch")
    return (time.perf_counter() - started) * 1000.0


async def batch(concurrency: int, delay_ms: int):
    children = [request(delay_ms) for _ in range(concurrency)]
    return await asyncio.gather(*children)


async def benchmark():
    concurrency, delay_ms, rounds = map(int, sys.argv[1:4])
    warmup = await batch(concurrency, delay_ms)
    second_warmup = await batch(concurrency, delay_ms)
    warmup_requests = len(warmup) + len(second_warmup)
    samples = []
    started = time.perf_counter()
    for _ in range(rounds):
        # Bound first rather than `samples.extend(await batch(...))`. An await
        # in argument position suspends after the receiver has been evaluated
        # and the receiver is not spilled to the generator frame across the
        # suspension, so the self backend rejects the resume block. Both arms
        # run this same source, so the comparison is unaffected.
        completed = await batch(concurrency, delay_ms)
        samples.extend(completed)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {"concurrency": concurrency, "delay_ms": delay_ms,
            "rounds": rounds, "requests": len(samples),
            "warmup_requests": warmup_requests,
            "elapsed_ms": elapsed_ms, "latencies_ms": samples}


if __name__ == "__main__":
    result = asyncio.run(benchmark())
    if len(sys.argv) > 4 and sys.argv[4] == "--summary":
        samples = result.pop("latencies_ms")
        result["latency_min_ms"] = min(samples)
        result["latency_max_ms"] = max(samples)
    print(json.dumps(result, sort_keys=True))
