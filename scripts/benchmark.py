"""
FraudLens — Prediction Latency Benchmark

Measures p50/p95/p99 latency for the single-prediction hot path
and the SHAP explanation path. Run before and after performance
optimizations to quantify wins.

Usage:
    # Make sure the API is running first:
    uvicorn api.main:app --host 0.0.0.0 --port 8000

    # Run benchmark:
    python scripts/benchmark.py

    # Output:
    # ── Single Prediction (no SHAP) ──
    #   p50:  1.23ms
    #   p95:  2.45ms
    #   p99:  3.67ms
    #   avg:  1.34ms
    # ── Single Prediction (with SHAP) ──
    #   p50:  45.67ms
    #   p95:  89.12ms
    #   p99: 120.45ms
    #   avg:  52.34ms
    # ── Batch Prediction (10 txns) ──
    #   p50:  3.45ms
    #   p95:  6.78ms
    #   p99:  9.01ms
    #   avg:  3.89ms
"""

import random
import statistics
import time
from typing import Any

import httpx

API_URL = "http://localhost:8000"
NUM_REQUESTS = 200  # Number of requests per benchmark scenario


def _generate_transaction() -> dict[str, float]:
    """Generate a random transaction for benchmarking."""
    tx: dict[str, float] = {"Time": random.uniform(0, 172792)}
    for i in range(1, 29):
        tx[f"V{i}"] = random.uniform(-5, 5)
    tx["Amount"] = random.uniform(0, 1000)
    return tx


def _print_stats(label: str, latencies: list[float]) -> None:
    """Print latency statistics for a benchmark scenario."""
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    avg = statistics.mean(latencies)

    print(f"  p50: {p50:>8.2f}ms")
    print(f"  p95: {p95:>8.2f}ms")
    print(f"  p99: {p99:>8.2f}ms")
    print(f"  avg: {avg:>8.2f}ms")


def benchmark_single_predict(client: httpx.Client, n: int) -> dict[str, Any]:
    """Benchmark single prediction (no SHAP)."""
    latencies: list[float] = []
    for _ in range(n):
        tx = _generate_transaction()
        start = time.perf_counter()
        response = client.post(f"{API_URL}/predict", json=tx)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        if response.status_code == 200:
            latencies.append(elapsed)
    return {
        "label": "Single Prediction (no SHAP)",
        "latencies": latencies,
    }


def benchmark_single_with_shap(client: httpx.Client, n: int) -> dict[str, Any]:
    """Benchmark single prediction WITH SHAP explanation."""
    latencies: list[float] = []
    for _ in range(n):
        tx = _generate_transaction()
        start = time.perf_counter()
        response = client.post(f"{API_URL}/predict?explain=true", json=tx)
        elapsed = (time.perf_counter() - start) * 1000
        if response.status_code == 200:
            latencies.append(elapsed)
    return {
        "label": "Single Prediction (with SHAP)",
        "latencies": latencies,
    }


def benchmark_batch(client: httpx.Client, n: int) -> dict[str, Any]:
    """Benchmark batch prediction (10 transactions)."""
    latencies: list[float] = []
    for _ in range(n):
        batch = {"transactions": [_generate_transaction() for _ in range(10)]}
        start = time.perf_counter()
        response = client.post(f"{API_URL}/predict/batch", json=batch)
        elapsed = (time.perf_counter() - start) * 1000
        if response.status_code == 200:
            latencies.append(elapsed)
    return {
        "label": "Batch Prediction (10 txns)",
        "latencies": latencies,
    }


def main() -> None:
    """Run all benchmarks and print results."""
    print("=" * 50)
    print("FraudLens — Prediction Latency Benchmark")
    print("=" * 50)
    print(f"Target API: {API_URL}")
    print(f"Requests per scenario: {NUM_REQUESTS}")
    print()

    with httpx.Client(timeout=30.0) as client:
        # Health check
        try:
            response = client.get(f"{API_URL}/health")
            response.raise_for_status()
            print("✓ API is healthy\n")
        except Exception as e:
            print(f"✗ API not reachable: {e}")
            print("  Start the API: uvicorn api.main:app --host 0.0.0.0 --port 8000")
            return

        # Run benchmarks
        scenarios = [
            benchmark_single_predict,
            benchmark_single_with_shap,
            benchmark_batch,
        ]

        for bench_fn in scenarios:
            result = bench_fn(client, NUM_REQUESTS)
            label = result["label"]
            latencies = result["latencies"]
            print(f"── {label} ──")
            if len(latencies) >= 10:
                _print_stats(label, latencies)
            else:
                print(f"  (only {len(latencies)} successful responses)")
            print()

    print("Done. Compare these numbers with previous runs to track performance wins.")


if __name__ == "__main__":
    main()
