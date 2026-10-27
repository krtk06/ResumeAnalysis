from __future__ import annotations

import argparse
import json
from pathlib import Path

from torch.utils.data import DataLoader


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fine-tune a cross-encoder on labelled resume/JD pairs."
    )
    parser.add_argument(
        "--data", type=Path, default=Path(__file__).parent / "data" / "pairs.jsonl"
    )
    parser.add_argument("--model", default="BAAI/bge-reranker-base")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).parent / "models" / "reranker"
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(
            f"Missing {args.data}. Build the labelled 300-1000 pair set first; "
            "the seed set is not sufficient for fine-tuning."
        )

    from sentence_transformers import CrossEncoder, InputExample

    rows = [
        json.loads(line)
        for line in args.data.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    examples = [
        InputExample(
            texts=[row["jd_text"], row["resume_text"]],
            label=float(row["relevance"]) / 3.0,
        )
        for row in rows
    ]
    model = CrossEncoder(args.model, num_labels=1, max_length=args.max_length)
    loader = DataLoader(examples, batch_size=args.batch_size, shuffle=True)
    args.output.mkdir(parents=True, exist_ok=True)
    model.fit(
        train_dataloader=loader,
        epochs=args.epochs,
        warmup_steps=max(10, len(loader) // 10),
        optimizer_params={"lr": args.learning_rate},
        output_path=str(args.output),
        show_progress_bar=True,
    )
    print(f"Saved cross-encoder to {args.output}")
    print(
        "Next: evaluate on the held-out split, then export to ONNX and benchmark on ARM."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
