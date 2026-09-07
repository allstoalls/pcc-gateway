"""Explain batch-size scaling; fitted costs are not separately timed phases."""

import argparse
import asyncio
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import statistics
import sys

from compare import ROOT, digest, save


def fit_costs(report):
    results = []
    for arm in ("host-pcc", "pcc1", "asyncio"):
        rows = []
        for concurrency in (1, 10, 100):
            rates = [run["requests"] * 1000 / run["elapsed_ms"]
                     for run in report["runs"]
                     if run["implementation"] == arm and run["delay_ms"] == 0
                     and run["concurrency"] == concurrency]
            if not rates:
                raise ValueError(f"missing zero-wait {arm}/C{concurrency} measurements")
            rate = statistics.median(rates)
            rows.append({"concurrency": concurrency, "qps_median": rate,
                         "batch_us": concurrency * 1e6 / rate})
        incremental = (rows[2]["batch_us"] - rows[1]["batch_us"]) / 90
        fixed = rows[1]["batch_us"] - 10 * incremental
        results.append({"implementation": arm, "measurements": rows,
                        "fitted_fixed_batch_us": fixed,
                        "fitted_incremental_request_us": incremental,
                        "predicted_c1_batch_us": fixed + incremental})
    return results


async def count_polls(workload, batches):
    # Count calls while preserving the original selector behavior. These
    # instrumented executions do not supply throughput or timing results.
    selector = asyncio.get_running_loop()._selector
    original = selector.select
    calls = [0, 0]

    def counted(timeout=None):
        calls[0] += 1
        calls[1] += int(timeout == 0)
        return original(timeout)

    results = []
    selector.select = counted
    try:
        for concurrency in (1, 10, 100):
            for _ in range(2):
                await workload.batch(concurrency, 0)
            calls[:] = [0, 0]
            for _ in range(batches):
                samples = await workload.batch(concurrency, 0)
                assert len(samples) == concurrency
            results.append({"concurrency": concurrency, "batches": batches,
                            "selector_type": type(selector).__name__,
                            "selector_calls": calls[0], "zero_timeout_calls": calls[1],
                            "calls_per_batch": calls[0] / batches,
                            "calls_per_request": calls[0] / (batches * concurrency)})
    finally:
        selector.select = original
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--batches", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.batches < 1 or args.output.exists():
        parser.error("select a positive batch count and a new output")
    comparison = json.loads(args.comparison.read_text())
    if comparison.get("complete") is not True:
        parser.error("the source comparison must be complete")
    workload_path = ROOT / "benchmark_asyncio.py"
    spec = importlib.util.spec_from_file_location("batch_probe_workload", workload_path)
    workload = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(workload)
    import pcc
    core = Path(pcc.__file__).resolve().parents[1]
    sys.path.insert(0, str(core / "scripts"))
    from run_pcc_compile_ab import _performance_lock

    with _performance_lock():
        result = {"schema": "pcc-gateway.batch-costs.v1", "complete": False,
                  "created_utc": datetime.now(timezone.utc).isoformat(),
                  "python_version": sys.version,
                  "comparison": str(args.comparison),
                  "comparison_sha256": digest(args.comparison),
                  "workload_sha256": digest(workload_path),
                  "script_sha256": digest(__file__),
                  "model": "batch_us = fixed_batch_us + concurrency * incremental_request_us",
                  "fit_anchors": [10, 100],
                  "limitation": "Two-point fit, not independently timed phases; selector counts do not attribute all fitted fixed cost to I/O",
                  "fits": fit_costs(comparison)}
        save(args.output, result)
        result["selector_counts"] = asyncio.run(count_polls(workload, args.batches))
        result["complete"] = True
        save(args.output, result)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
