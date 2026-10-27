from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from baselines import build_baseline, predict_async, predict_sync
from metrics import evaluate

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "data" / "seed_pairs.jsonl"
DEFAULT_OUTPUT = ROOT / "report.json"


def load_pairs(path: Path) -> list[dict]:
    pairs = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate resume/JD matching baselines."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--baseline",
        action="append",
        choices=["tfidf", "hash", "minilm", "matcher", "cross-encoder", "opencode"],
        help="Repeatable. Defaults to tfidf, hash, and minilm.",
    )
    args = parser.parse_args()

    pairs = load_pairs(args.data)
    names = args.baseline or ["tfidf", "hash", "minilm"]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": args.data.name,
        "dataset_kind": "seed-smoke-test",
        "note": (
            "This is a small hand-labelled seed set for harness verification. "
            "It is not the final 300-1000 pair benchmark and must not be cited as one."
        ),
        "n_pairs": len(pairs),
        "baselines": {},
    }

    print(
        f"{'baseline':<16} {'NDCG@10':>8} {'MRR@10':>8} {'Recall@10':>10} {'Spearman':>9} {'ECE':>7}"
    )
    for name in names:
        print(f"Running {name}...", flush=True)
        baseline = build_baseline(name, pairs)
        if name == "opencode":
            predictions = asyncio.run(predict_async(baseline, pairs))
        else:
            predictions = predict_sync(baseline, pairs)
        metrics = evaluate(pairs, predictions)
        report["baselines"][name] = {
            "metrics": metrics,
            "predictions": [
                {
                    "pair_id": pair["pair_id"],
                    "resume_id": pair["resume_id"],
                    "jd_id": pair["jd_id"],
                    "relevance": pair["relevance"],
                    "prediction": round(float(prediction), 4),
                }
                for pair, prediction in zip(pairs, predictions)
            ],
        }
        spearman = metrics["spearman"] if metrics["spearman"] is not None else 0.0
        ece = metrics["ece"] if metrics["ece"] is not None else 0.0
        print(
            f"{name:<16} {metrics['ndcg@10']:>8.4f} {metrics['mrr@10']:>8.4f} "
            f"{metrics['recall@10']:>10.4f} {spearman:>9.4f} {ece:>7.4f}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
