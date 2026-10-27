from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path

from baselines import build_baseline, predict_async, predict_sync

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Counterfactual name/school fairness probe."
    )
    parser.add_argument(
        "--baseline",
        default="minilm",
        choices=["tfidf", "hash", "minilm", "matcher", "opencode"],
    )
    parser.add_argument(
        "--data", type=Path, default=ROOT / "data" / "fairness_seed.jsonl"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "fairness_report.json")
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in args.data.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline = build_baseline(args.baseline, rows)
    predictions = (
        asyncio.run(predict_async(baseline, rows))
        if args.baseline == "opencode"
        else predict_sync(baseline, rows)
    )

    groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row, prediction in zip(rows, predictions):
        attribute = row["group"].split(":", 1)[0]
        groups[attribute].append((row["variant"], float(prediction)))

    deltas = {}
    for group, values in groups.items():
        scores = [score for _, score in values]
        deltas[group] = {
            "scores": {variant: round(score, 4) for variant, score in values},
            "max_delta": round(max(scores) - min(scores), 4),
        }

    payload = {
        "baseline": args.baseline,
        "note": "Counterfactual probe on synthetic names/schools; not a fairness audit.",
        "groups": deltas,
        "max_delta_all": round(
            max(item["max_delta"] for item in deltas.values()) if deltas else 0.0,
            4,
        ),
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
