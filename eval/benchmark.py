from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from baselines import build_baseline

ROOT = Path(__file__).resolve().parent


def timed(baseline, pairs: list[dict], repeats: int) -> list[float]:
    timings = []
    for _ in range(repeats):
        for pair in pairs:
            started = time.perf_counter()
            baseline.score_pair(pair["resume_text"], pair["jd_text"])
            timings.append((time.perf_counter() - started) * 1000)
    return timings


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark local scoring latency.")
    parser.add_argument(
        "--baseline", action="append", choices=["tfidf", "hash", "minilm", "matcher"]
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "seed_pairs.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark.json")
    args = parser.parse_args()

    pairs = [
        json.loads(line)
        for line in args.data.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    names = args.baseline or ["tfidf", "minilm", "matcher"]
    report = {"n_pairs": len(pairs), "repeats": args.repeats, "baselines": {}}
    for name in names:
        print(f"Benchmarking {name}...", flush=True)
        baseline = build_baseline(name, pairs)
        timings = timed(baseline, pairs, args.repeats)
        timings.sort()
        report["baselines"][name] = {
            "p50_ms": round(statistics.median(timings), 2),
            "p95_ms": round(timings[int(len(timings) * 0.95) - 1], 2),
            "mean_ms": round(statistics.mean(timings), 2),
            "max_ms": round(max(timings), 2),
        }
        print(report["baselines"][name])

    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
