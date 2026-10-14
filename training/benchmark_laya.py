"""High-performance inference benchmark measuring throughput and latency percentiles."""

from __future__ import annotations
import sys
import os
import json
import time
import argparse
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.laya_engine import LayaSimulationClassifier
from backend.app.simulation.feature_extractor import SimulationFeatures


def run_benchmark(model_version: str = "v1", iterations: int = 2000) -> dict[str, Any]:
    print(f"\n=== [DOIP Phase 8.5] Benchmarking Laya Inference ({model_version.upper()}) ===")
    ckpt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", f"laya_doip_{model_version}"))
    model_file = os.path.join(ckpt_dir, "model.pt")

    classifier = LayaSimulationClassifier(checkpoint_path=model_file)
    dummy_feats = SimulationFeatures(
        numeric_vector=[0.5, 0.5, 0.6, 0.3, 0.45, 0.9, 0.2, 0.0, 0.8, 0.2, 0.7, 0.1, 0.15, 0.3, 0.8],
        feature_names=[""] * 15,
        raw_dict={},
        prompt_text="",
    )

    # Warmup
    for _ in range(50):
        classifier.predict(dummy_feats)

    # 1. Single Item Latency Benchmark
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = classifier.predict(dummy_feats)
        lat = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat)

    lat_arr = np.array(latencies)
    mean_lat = float(np.mean(lat_arr))
    p50_lat = float(np.percentile(lat_arr, 50))
    p95_lat = float(np.percentile(lat_arr, 95))
    p99_lat = float(np.percentile(lat_arr, 99))

    # 2. Batched Throughput Benchmark
    batch_sizes = [1, 16, 64, 256]
    throughput_results = {}

    model = classifier.model
    device = classifier.device

    for b in batch_sizes:
        batch_tensor = torch.randn((b, 15), dtype=torch.float32, device=device)
        # Warmup
        for _ in range(10):
            with torch.no_grad():
                _ = model(batch_tensor)

        n_batches = 100
        t0 = time.perf_counter()
        for _ in range(n_batches):
            with torch.no_grad():
                _ = model(batch_tensor)
        t_total = time.perf_counter() - t0
        samples_sec = (b * n_batches) / max(1e-6, t_total)
        throughput_results[f"batch_{b}"] = round(samples_sec, 1)

    result = {
        "model_id": f"laya_doip_{model_version}",
        "iterations": iterations,
        "latency_ms": {
            "mean": round(mean_lat, 4),
            "p50": round(p50_lat, 4),
            "p95": round(p95_lat, 4),
            "p99": round(p99_lat, 4),
        },
        "throughput_samples_per_sec": throughput_results,
        "sub_millisecond_p50": p50_lat < 1.0,
    }

    print(f"Latency: Mean={mean_lat:.4f} ms | P50={p50_lat:.4f} ms | P95={p95_lat:.4f} ms | P99={p99_lat:.4f} ms")
    print(f"Throughput: {throughput_results}")
    print(f"Sub-Millisecond Inference: {'PASSED' if result['sub_millisecond_p50'] else 'FAILED'}")

    bench_path = os.path.join(ckpt_dir, "benchmark_metrics.json")
    with open(bench_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, default="v1", choices=["v1", "v2"])
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()
    run_benchmark(model_version=args.version, iterations=args.iterations)


if __name__ == "__main__":
    main()
