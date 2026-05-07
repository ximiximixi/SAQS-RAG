#!/usr/bin/env python3
"""Risk baselines that combine single-judge and cross-judge reliability features."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any


TARGETS = ["qwen_wrong", "glm_wrong", "combined_wrong", "any_model_wrong", "both_wrong"]
RISK_SCORES = [
    "risk_qwen_combined",
    "risk_glm_combined",
    "risk_avg_single",
    "risk_max_single",
    "risk_model_majority_disagreement",
    "risk_task_binary_disagreement",
    "risk_multi_combined",
]


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def read_csv_by_id(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["sample_id"]: row for row in csv.DictReader(handle)}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


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


def topk_metrics(rows: list[dict[str, Any]], target: str, score_name: str, fraction: float) -> dict[str, Any]:
    total_errors = sum(1 for row in rows if row[target])
    base_error_rate = total_errors / len(rows) if rows else 0.0
    base_accuracy = 1.0 - base_error_rate
    ranked = sorted(rows, key=lambda row: float(row[score_name]), reverse=True)
    k = max(1, math.ceil(len(ranked) * fraction))
    audited = ranked[:k]
    retained = ranked[k:]
    captured = sum(1 for row in audited if row[target])
    retained_correct = sum(1 for row in retained if not row[target])
    return {
        "target": target,
        "risk_score": score_name,
        "audit_fraction": fraction,
        "audit_n": k,
        "captured_errors": captured,
        "total_errors": total_errors,
        "precision": round(captured / k, 6),
        "recall": round(captured / total_errors, 6) if total_errors else None,
        "lift_over_random": round(captured / (k * base_error_rate), 6) if base_error_rate else None,
        "retained_accuracy": round(retained_correct / len(retained), 6) if retained else None,
        "base_accuracy": round(base_accuracy, 6),
        "accuracy_gain": round((retained_correct / len(retained)) - base_accuracy, 6)
        if retained
        else None,
    }


def build_rows(qwen: dict[str, dict[str, Any]], glm: dict[str, dict[str, Any]], multi: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for sample_id in sorted(set(qwen) & set(glm) & set(multi)):
        q = qwen[sample_id]
        g = glm[sample_id]
        m = multi[sample_id]
        q_risk = parse_float(q["risk_combined"])
        g_risk = parse_float(g["risk_combined"])
        model_disagree = 1.0 if parse_bool(m["model_majority_disagreement"]) else 0.0
        task_disagree = parse_float(m["per_task_binary_disagreement_rate"])
        avg_single = (q_risk + g_risk) / 2.0
        max_single = max(q_risk, g_risk)
        rows.append(
            {
                "sample_id": sample_id,
                "dataset": m["dataset"],
                "gold_label": m["gold_label"],
                "qwen_wrong": not parse_bool(m["qwen35plus_majority_correct"]),
                "glm_wrong": not parse_bool(m["glm51_majority_correct"]),
                "combined_wrong": not parse_bool(m["combined_majority_correct"]),
                "any_model_wrong": parse_bool(m["any_model_wrong"]),
                "both_wrong": parse_bool(m["both_wrong"]),
                "risk_qwen_combined": round(q_risk, 6),
                "risk_glm_combined": round(g_risk, 6),
                "risk_avg_single": round(avg_single, 6),
                "risk_max_single": round(max_single, 6),
                "risk_model_majority_disagreement": model_disagree,
                "risk_task_binary_disagreement": task_disagree,
                "risk_multi_combined": round(avg_single + max_single + model_disagree + task_disagree, 6),
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metric_rows = []
    topk_rows = []
    for target in TARGETS:
        labels = [bool(row[target]) for row in rows]
        for score_name in RISK_SCORES:
            scores = [float(row[score_name]) for row in rows]
            metric_rows.append(
                {
                    "target": target,
                    "risk_score": score_name,
                    "positive_count": sum(1 for label in labels if label),
                    "positive_rate": round(sum(1 for label in labels if label) / len(labels), 6),
                    "auroc": roc_auc(scores, labels),
                    "auprc": average_precision(scores, labels),
                }
            )
            for fraction in [0.1, 0.2, 0.3, 0.4]:
                topk_rows.append(topk_metrics(rows, target, score_name, fraction))
    return metric_rows, topk_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qwen-features", type=Path, required=True)
    parser.add_argument("--glm-features", type=Path, required=True)
    parser.add_argument("--multi-samples", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    qwen = read_csv_by_id(args.qwen_features)
    glm = read_csv_by_id(args.glm_features)
    multi = read_csv_by_id(args.multi_samples)
    rows = build_rows(qwen, glm, multi)
    metric_rows, topk_rows = summarize(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "multi_judge_risk_features.csv", rows)
    write_csv(args.out_dir / "multi_judge_risk_metrics.csv", metric_rows)
    write_csv(args.out_dir / "multi_judge_risk_topk.csv", topk_rows)

    print(f"Wrote multi-judge risk baselines to {args.out_dir}")
    for row in metric_rows:
        if row["target"] in {"combined_wrong", "any_model_wrong"} and row["risk_score"] in {
            "risk_qwen_combined",
            "risk_avg_single",
            "risk_multi_combined",
            "risk_model_majority_disagreement",
        }:
            print(row)


if __name__ == "__main__":
    main()
