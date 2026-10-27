from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fit an isotonic calibration curve from an eval report."
    )
    parser.add_argument(
        "--report", type=Path, default=Path(__file__).parent / "report.json"
    )
    parser.add_argument("--baseline", default="minilm")
    parser.add_argument(
        "--data", type=Path, default=Path(__file__).parent / "data" / "seed_pairs.jsonl"
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).parent / "calibration.seed.json"
    )
    args = parser.parse_args()

    from sklearn.isotonic import IsotonicRegression

    report = json.loads(args.report.read_text(encoding="utf-8"))
    predictions = report["baselines"][args.baseline]["predictions"]
    labels = {}
    with args.data.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            labels[row["pair_id"]] = row["holistic_score"]

    raw = np.array([item["prediction"] * 10 for item in predictions], dtype=float)
    target = np.array([labels[item["pair_id"]] for item in predictions], dtype=float)
    model = IsotonicRegression(increasing=True, out_of_bounds="clip")
    model.fit(raw, target)
    points = [
        [round(float(x), 3), round(float(y), 3)]
        for x, y in zip(model.X_thresholds_, model.y_thresholds_)
    ]
    payload = {
        "version": f"isotonic-seed-{datetime.now(UTC).strftime('%Y%m%d')}",
        "dataset": args.data.name,
        "baseline": args.baseline,
        "warning": "Seed smoke-test fit only. Refit on the full labelled validation split before production.",
        "points": points,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} with {len(points)} points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
