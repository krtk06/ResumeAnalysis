from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

import numpy as np


def ndcg_at_k(relevances: list[int], k: int = 10) -> float:
    gains = [(2**rel) - 1 for rel in relevances[:k]]
    discounts = [math.log2(index + 2) for index in range(len(gains))]
    dcg = sum(gain / discount for gain, discount in zip(gains, discounts))
    ideal = sorted(relevances, reverse=True)[:k]
    ideal_gains = [(2**rel) - 1 for rel in ideal]
    idcg = sum(gain / discount for gain, discount in zip(ideal_gains, discounts))
    return dcg / idcg if idcg else 0.0


def reciprocal_rank(relevances: list[int], threshold: int = 2) -> float:
    for index, rel in enumerate(relevances, start=1):
        if rel >= threshold:
            return 1.0 / index
    return 0.0


def recall_at_k(relevances: list[int], k: int = 10, threshold: int = 2) -> float:
    relevant = sum(1 for rel in relevances if rel >= threshold)
    if relevant == 0:
        return 0.0
    return sum(1 for rel in relevances[:k] if rel >= threshold) / relevant


def spearman(left: Iterable[float], right: Iterable[float]) -> float:
    a = np.asarray(list(left), dtype=float)
    b = np.asarray(list(right), dtype=float)
    if len(a) < 2 or len(a) != len(b):
        return 0.0
    a_rank = np.argsort(np.argsort(a))
    b_rank = np.argsort(np.argsort(b))
    if np.std(a_rank) == 0 or np.std(b_rank) == 0:
        return 0.0
    return float(np.corrcoef(a_rank, b_rank)[0, 1])


def expected_calibration_error(
    predictions: Iterable[float],
    targets: Iterable[float],
    bins: int = 10,
) -> float:
    pred = np.clip(np.asarray(list(predictions), dtype=float), 0, 1)
    target = np.clip(np.asarray(list(targets), dtype=float), 0, 1)
    if len(pred) == 0 or len(pred) != len(target):
        return 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        mask = (pred >= lower) & (pred < upper if index < bins - 1 else pred <= upper)
        if not np.any(mask):
            continue
        total += (mask.sum() / len(pred)) * abs(pred[mask].mean() - target[mask].mean())
    return float(total)


def bootstrap_ci(
    values: list[float], samples: int = 1000, seed: int = 7
) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    array = np.asarray(values, dtype=float)
    draws = [
        float(np.mean(rng.choice(array, size=len(array), replace=True)))
        for _ in range(samples)
    ]
    return (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)))


def evaluate(pairs: list[dict], predictions: list[float], *, k: int = 10) -> dict:
    if len(pairs) != len(predictions):
        raise ValueError("pairs and predictions must have the same length")

    grouped: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    for pair, prediction in zip(pairs, predictions):
        grouped[pair["jd_id"]].append((prediction, pair))

    ndcgs: list[float] = []
    reciprocal_ranks: list[float] = []
    recalls: list[float] = []
    per_jd: dict[str, dict] = {}

    for jd_id, rows in grouped.items():
        rows.sort(key=lambda item: item[0], reverse=True)
        relevances = [int(pair["relevance"]) for _, pair in rows]
        ndcg = ndcg_at_k(relevances, k)
        mrr = reciprocal_rank(relevances)
        recall = recall_at_k(relevances, k)
        ndcgs.append(ndcg)
        reciprocal_ranks.append(mrr)
        recalls.append(recall)
        per_jd[jd_id] = {
            "ndcg@10": round(ndcg, 4),
            "mrr@10": round(mrr, 4),
            "recall@10": round(recall, 4),
            "ranking": [
                {
                    "resume_id": pair["resume_id"],
                    "relevance": int(pair["relevance"]),
                    "prediction": round(float(prediction), 4),
                }
                for prediction, pair in rows
            ],
        }

    holistic = [pair.get("holistic_score") for pair in pairs]
    calibrated_targets = [
        float(value) / 10 if value is not None else None for value in holistic
    ]
    valid = [
        (pred, target)
        for pred, target in zip(predictions, calibrated_targets)
        if target is not None
    ]
    mae = (
        float(np.mean([abs(pred - target * 10) for pred, target in valid]))
        if valid
        else None
    )
    ece = (
        expected_calibration_error(
            [pred / 10 for pred, _ in valid],
            [target for _, target in valid],
        )
        if valid
        else None
    )
    rho = (
        spearman([pred for pred, _ in valid], [target for _, target in valid])
        if valid
        else None
    )

    non_resume_pairs = [pair for pair in pairs if not pair.get("is_resume", True)]
    non_resume_recall = None
    if non_resume_pairs:
        flagged = sum(
            1
            for pair, prediction in zip(pairs, predictions)
            if not pair.get("is_resume", True) and prediction <= 2.0
        )
        non_resume_recall = flagged / len(non_resume_pairs)

    return {
        "n_pairs": len(pairs),
        "n_jds": len(grouped),
        "ndcg@10": round(float(np.mean(ndcgs)), 4),
        "ndcg@10_ci": [round(value, 4) for value in bootstrap_ci(ndcgs)],
        "mrr@10": round(float(np.mean(reciprocal_ranks)), 4),
        "recall@10": round(float(np.mean(recalls)), 4),
        "spearman": round(rho, 4) if rho is not None else None,
        "mae": round(mae, 4) if mae is not None else None,
        "ece": round(ece, 4) if ece is not None else None,
        "non_resume_recall": round(non_resume_recall, 4)
        if non_resume_recall is not None
        else None,
        "per_jd": per_jd,
    }
