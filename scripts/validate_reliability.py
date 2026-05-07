#!/usr/bin/env python3
"""Held-out and leave-one-dataset-out validation for reliability scores."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


RISK_SCORES = [
    "risk_disagreement",
    "risk_instability",
    "risk_entropy",
    "risk_low_margin",
    "risk_low_confidence",
    "risk_insufficient",
    "risk_combined",
]

MODEL_FEATURES = [
    "faithful_rate",
    "unfaithful_rate",
    "insufficient_rate",
    "majority_margin",
    "binary_entropy",
    "verdict_entropy",
    "prompt_flip_count",
    "order_flip_count",
    "mean_confidence",
    "min_confidence",
    "confidence_std",
    "risk_low_confidence",
    "risk_insufficient",
]


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Cannot parse bool: {value}")


def parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def read_feature_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["majority_wrong"] = parse_bool(row["majority_wrong"])
        row["majority_correct"] = parse_bool(row["majority_correct"])
        row["any_disagreement"] = parse_bool(row["any_disagreement"])
        for key in RISK_SCORES + MODEL_FEATURES + ["judgment_wrong_rate"]:
            row[key] = parse_float(row.get(key))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def stdev(values: list[float]) -> float | None:
    return round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0 if values else None


def roc_auc(scores: list[float], labels: list[bool]) -> float | None:
    positives = sum(1 for label in labels if label)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None

    indexed = sorted(enumerate(scores), key=lambda item: item[1])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1

    sum_pos_ranks = sum(rank for rank, label in zip(ranks, labels) if label)
    auc = (sum_pos_ranks - positives * (positives + 1) / 2.0) / (positives * negatives)
    return round(auc, 6)


def average_precision(scores: list[float], labels: list[bool]) -> float | None:
    positives = sum(1 for label in labels if label)
    if positives == 0:
        return None
    ranked = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
    hits = 0
    precision_sum = 0.0
    for idx, (_, label) in enumerate(ranked, start=1):
        if label:
            hits += 1
            precision_sum += hits / idx
    return round(precision_sum / positives, 6)


def topk_eval(rows: list[dict[str, Any]], scores: list[float], fraction: float) -> dict[str, Any]:
    labels = [bool(row["majority_wrong"]) for row in rows]
    total_errors = sum(1 for label in labels if label)
    base_accuracy = 1.0 - total_errors / len(rows) if rows else None
    base_error_rate = total_errors / len(rows) if rows else 0.0
    ranked = sorted(zip(rows, scores), key=lambda item: item[1], reverse=True)
    k = max(1, math.ceil(len(ranked) * fraction))
    audited = ranked[:k]
    retained = ranked[k:]
    captured = sum(1 for row, _ in audited if row["majority_wrong"])
    retained_correct = sum(1 for row, _ in retained if not row["majority_wrong"])
    return {
        "audit_fraction": fraction,
        "audit_n": k,
        "captured_errors": captured,
        "total_errors": total_errors,
        "precision": round(captured / k, 6) if k else None,
        "recall": round(captured / total_errors, 6) if total_errors else None,
        "lift_over_random": round(captured / (k * base_error_rate), 6) if base_error_rate else None,
        "retained_n": len(retained),
        "retained_accuracy": round(retained_correct / len(retained), 6) if retained else None,
        "base_accuracy": round(base_accuracy, 6) if base_accuracy is not None else None,
        "accuracy_gain": round((retained_correct / len(retained)) - base_accuracy, 6)
        if retained and base_accuracy is not None
        else None,
    }


def stratified_folds(rows: list[dict[str, Any]], k: int, seed: int) -> list[list[int]]:
    rng = random.Random(seed)
    buckets: dict[tuple[str, bool], list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        buckets[(row["dataset"], bool(row["majority_wrong"]))].append(idx)

    folds = [[] for _ in range(k)]
    for indices in buckets.values():
        shuffled = list(indices)
        rng.shuffle(shuffled)
        for pos, idx in enumerate(shuffled):
            folds[pos % k].append(idx)
    return folds


def standardize_train_test(train_x: np.ndarray, test_x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean_x = train_x.mean(axis=0)
    std_x = train_x.std(axis=0)
    std_x[std_x == 0] = 1.0
    return (train_x - mean_x) / std_x, (test_x - mean_x) / std_x


def fit_logistic(
    train_x: np.ndarray,
    train_y: np.ndarray,
    lr: float = 0.05,
    epochs: int = 2000,
    l2: float = 0.01,
) -> np.ndarray:
    x = np.concatenate([np.ones((train_x.shape[0], 1)), train_x], axis=1)
    weights = np.zeros(x.shape[1])
    pos = max(1, int(train_y.sum()))
    neg = max(1, int(len(train_y) - train_y.sum()))
    sample_weights = np.where(train_y == 1, len(train_y) / (2 * pos), len(train_y) / (2 * neg))

    for _ in range(epochs):
        logits = np.clip(x @ weights, -30, 30)
        probs = 1 / (1 + np.exp(-logits))
        grad = (x.T @ ((probs - train_y) * sample_weights)) / len(train_y)
        grad[1:] += l2 * weights[1:]
        weights -= lr * grad
    return weights


def predict_logistic(weights: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    x = np.concatenate([np.ones((test_x.shape[0], 1)), test_x], axis=1)
    logits = np.clip(x @ weights, -30, 30)
    return 1 / (1 + np.exp(-logits))


def matrix(rows: list[dict[str, Any]], indices: list[int], columns: list[str]) -> np.ndarray:
    return np.asarray([[parse_float(rows[idx].get(col)) for col in columns] for idx in indices], dtype=float)


def labels(rows: list[dict[str, Any]], indices: list[int]) -> np.ndarray:
    return np.asarray([1.0 if rows[idx]["majority_wrong"] else 0.0 for idx in indices], dtype=float)


def eval_predictions(
    rows: list[dict[str, Any]],
    test_indices: list[int],
    score_name: str,
    scores: list[float],
    protocol: str,
    split_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    test_rows = [rows[idx] for idx in test_indices]
    y = [bool(row["majority_wrong"]) for row in test_rows]
    metric = {
        "protocol": protocol,
        "split_id": split_id,
        "risk_score": score_name,
        "n_test": len(test_rows),
        "error_rate": round(sum(y) / len(y), 6) if y else None,
        "auroc": roc_auc(scores, y),
        "auprc": average_precision(scores, y),
    }
    topk_rows = []
    for frac in [0.1, 0.2, 0.3, 0.4]:
        item = topk_eval(test_rows, scores, frac)
        item.update(
            {
                "protocol": protocol,
                "split_id": split_id,
                "risk_score": score_name,
                "n_test": len(test_rows),
            }
        )
        topk_rows.append(item)
    return metric, topk_rows


def random_cv(rows: list[dict[str, Any]], folds: int, repeats: int, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metric_rows: list[dict[str, Any]] = []
    topk_rows: list[dict[str, Any]] = []

    for repeat in range(repeats):
        fold_indices = stratified_folds(rows, folds, seed + repeat)
        for fold_id, test_indices in enumerate(fold_indices):
            train_indices = [idx for idx in range(len(rows)) if idx not in set(test_indices)]
            split_id = f"repeat{repeat}_fold{fold_id}"
            for score_name in RISK_SCORES:
                scores = [float(rows[idx].get(score_name) or 0.0) for idx in test_indices]
                metric, topk = eval_predictions(rows, test_indices, score_name, scores, "stratified_cv", split_id)
                metric_rows.append(metric)
                topk_rows.extend(topk)

            train_x = matrix(rows, train_indices, MODEL_FEATURES)
            test_x = matrix(rows, test_indices, MODEL_FEATURES)
            train_x, test_x = standardize_train_test(train_x, test_x)
            train_y = labels(rows, train_indices)
            weights = fit_logistic(train_x, train_y)
            probs = predict_logistic(weights, test_x).tolist()
            metric, topk = eval_predictions(rows, test_indices, "logistic_features", probs, "stratified_cv", split_id)
            metric_rows.append(metric)
            topk_rows.extend(topk)

    return metric_rows, topk_rows


def leave_one_dataset_out(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metric_rows: list[dict[str, Any]] = []
    topk_rows: list[dict[str, Any]] = []
    datasets = sorted({row["dataset"] for row in rows})

    for dataset in datasets:
        test_indices = [idx for idx, row in enumerate(rows) if row["dataset"] == dataset]
        train_indices = [idx for idx, row in enumerate(rows) if row["dataset"] != dataset]
        for score_name in RISK_SCORES:
            scores = [float(rows[idx].get(score_name) or 0.0) for idx in test_indices]
            metric, topk = eval_predictions(rows, test_indices, score_name, scores, "leave_one_dataset_out", dataset)
            metric_rows.append(metric)
            topk_rows.extend(topk)

        train_x = matrix(rows, train_indices, MODEL_FEATURES)
        test_x = matrix(rows, test_indices, MODEL_FEATURES)
        train_x, test_x = standardize_train_test(train_x, test_x)
        train_y = labels(rows, train_indices)
        weights = fit_logistic(train_x, train_y)
        probs = predict_logistic(weights, test_x).tolist()
        metric, topk = eval_predictions(rows, test_indices, "logistic_features", probs, "leave_one_dataset_out", dataset)
        metric_rows.append(metric)
        topk_rows.extend(topk)

    return metric_rows, topk_rows


def aggregate_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(row["protocol"], row["risk_score"])].append(row)

    result = []
    for (protocol, score_name), items in sorted(buckets.items()):
        aurocs = [float(item["auroc"]) for item in items if item.get("auroc") is not None]
        auprcs = [float(item["auprc"]) for item in items if item.get("auprc") is not None]
        result.append(
            {
                "protocol": protocol,
                "risk_score": score_name,
                "n_splits": len(items),
                "mean_auroc": mean(aurocs),
                "std_auroc": stdev(aurocs),
                "mean_auprc": mean(auprcs),
                "std_auprc": stdev(auprcs),
            }
        )
    return result


def aggregate_topk(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(row["protocol"], row["risk_score"], str(row["audit_fraction"]))].append(row)

    result = []
    for (protocol, score_name, frac), items in sorted(buckets.items()):
        for key in [
            "precision",
            "recall",
            "lift_over_random",
            "retained_accuracy",
            "base_accuracy",
            "accuracy_gain",
        ]:
            values = [float(item[key]) for item in items if item.get(key) not in {None, ""}]
            if key == "precision":
                row = {
                    "protocol": protocol,
                    "risk_score": score_name,
                    "audit_fraction": frac,
                    "n_splits": len(items),
                }
            row[f"mean_{key}"] = mean(values)
            row[f"std_{key}"] = stdev(values)
        result.append(row)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260424)
    args = parser.parse_args()

    rows = read_feature_csv(args.features)
    cv_metrics, cv_topk = random_cv(rows, args.folds, args.repeats, args.seed)
    lodo_metrics, lodo_topk = leave_one_dataset_out(rows)
    all_metrics = cv_metrics + lodo_metrics
    all_topk = cv_topk + lodo_topk
    metric_summary = aggregate_metrics(all_metrics)
    topk_summary = aggregate_topk(all_topk)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "split_metrics.csv", all_metrics)
    write_csv(args.out_dir / "split_topk_metrics.csv", all_topk)
    write_csv(args.out_dir / "metric_summary.csv", metric_summary)
    write_csv(args.out_dir / "topk_summary.csv", topk_summary)
    write_json(
        args.out_dir / "run_config.json",
        {
            "features": str(args.features),
            "folds": args.folds,
            "repeats": args.repeats,
            "seed": args.seed,
            "risk_scores": RISK_SCORES,
            "model_features": MODEL_FEATURES,
        },
    )

    print(f"Wrote validation outputs to {args.out_dir}")
    print("Metric summary:")
    for row in metric_summary:
        if row["protocol"] == "leave_one_dataset_out":
            print(row)


if __name__ == "__main__":
    main()
