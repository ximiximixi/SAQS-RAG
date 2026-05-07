#!/usr/bin/env python3
"""Build sample-level judge reliability features and cheap audit baselines."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def verdict_to_binary(verdict: Any) -> bool | None:
    if verdict == "faithful":
        return True
    if verdict == "unfaithful":
        return False
    return None


def majority_vote(verdicts: list[str]) -> str | None:
    binary = [item for item in verdicts if item in {"faithful", "unfaithful"}]
    if not binary:
        return None
    counts = Counter(binary)
    if counts["faithful"] == counts["unfaithful"]:
        return "tie"
    return counts.most_common(1)[0][0]


def entropy_from_counts(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log(p, 2)
    return entropy


def safe_mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def safe_std(values: list[float]) -> float | None:
    return round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0 if values else None


def avg_bool(values: list[bool]) -> float | None:
    return round(sum(1 for value in values if value) / len(values), 6) if values else None


def build_features(samples: dict[str, dict[str, Any]], judgments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in judgments:
        by_sample[row["sample_id"]].append(row)

    features: list[dict[str, Any]] = []
    for sample_id, rows in sorted(by_sample.items()):
        sample = samples.get(sample_id, {})
        gold_label = sample.get("gold_label") or rows[0].get("gold_label")
        verdicts = [row.get("verdict") for row in rows if row.get("verdict")]
        verdict_counts = Counter(verdicts)
        binary_verdicts = [v for v in verdicts if v in {"faithful", "unfaithful"}]
        binary_counts = Counter(binary_verdicts)
        majority = majority_vote(binary_verdicts)
        binary_n = len(binary_verdicts)
        faithful_n = binary_counts["faithful"]
        unfaithful_n = binary_counts["unfaithful"]
        majority_n = max(faithful_n, unfaithful_n) if binary_n else 0
        majority_margin = (majority_n - min(faithful_n, unfaithful_n)) / binary_n if binary_n else 0.0
        majority_correct = majority == gold_label if majority in {"faithful", "unfaithful"} else None

        by_prompt: dict[str, set[str]] = defaultdict(set)
        by_order: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            verdict = row.get("verdict")
            if not verdict:
                continue
            by_prompt[row.get("prompt_id")].add(verdict)
            by_order[row.get("evidence_order")].add(verdict)

        prompt_flip_count = sum(1 for values in by_order.values() if len(values) > 1)
        order_flip_count = sum(1 for values in by_prompt.values() if len(values) > 1)
        confidences = [
            float(row["confidence"])
            for row in rows
            if isinstance(row.get("confidence"), (int, float))
        ]
        binary_preds = [verdict_to_binary(row.get("verdict")) for row in rows]
        judgment_wrong_values = []
        for pred in binary_preds:
            if pred is None:
                judgment_wrong_values.append(True)
            else:
                judgment_wrong_values.append(pred != (gold_label == "faithful"))

        any_disagreement = faithful_n > 0 and unfaithful_n > 0
        instability_score = (
            (1.0 if any_disagreement else 0.0)
            + prompt_flip_count / 3.0
            + order_flip_count / 3.0
            + verdict_counts["insufficient"] / max(1, len(rows))
            + (safe_std(confidences) or 0.0)
        )

        feature = {
            "sample_id": sample_id,
            "dataset": sample.get("dataset") or rows[0].get("dataset"),
            "gold_label": gold_label,
            "n_judgments": len(rows),
            "faithful_count": faithful_n,
            "unfaithful_count": unfaithful_n,
            "insufficient_count": verdict_counts["insufficient"],
            "parse_failure_count": sum(1 for row in rows if not row.get("parsed_ok")),
            "error_count": sum(1 for row in rows if row.get("error")),
            "majority_verdict": majority,
            "majority_correct": majority_correct,
            "majority_wrong": (not majority_correct) if majority_correct is not None else None,
            "majority_margin": round(majority_margin, 6),
            "binary_entropy": round(entropy_from_counts([faithful_n, unfaithful_n]), 6),
            "verdict_entropy": round(
                entropy_from_counts(
                    [
                        verdict_counts["faithful"],
                        verdict_counts["unfaithful"],
                        verdict_counts["insufficient"],
                    ]
                ),
                6,
            ),
            "faithful_rate": round(faithful_n / max(1, len(rows)), 6),
            "unfaithful_rate": round(unfaithful_n / max(1, len(rows)), 6),
            "insufficient_rate": round(verdict_counts["insufficient"] / max(1, len(rows)), 6),
            "any_disagreement": any_disagreement,
            "prompt_flip_count": prompt_flip_count,
            "order_flip_count": order_flip_count,
            "mean_confidence": safe_mean(confidences),
            "min_confidence": round(min(confidences), 6) if confidences else None,
            "max_confidence": round(max(confidences), 6) if confidences else None,
            "confidence_std": safe_std(confidences),
            "judgment_wrong_rate": avg_bool(judgment_wrong_values),
            "instability_score": round(instability_score, 6),
            "risk_disagreement": 1.0 if any_disagreement else 0.0,
            "risk_instability": round(instability_score, 6),
            "risk_entropy": round(entropy_from_counts([faithful_n, unfaithful_n]), 6),
            "risk_low_margin": round(1.0 - majority_margin, 6),
            "risk_low_confidence": round(1.0 - (safe_mean(confidences) or 1.0), 6),
            "risk_insufficient": round(verdict_counts["insufficient"] / max(1, len(rows)), 6),
        }
        feature["risk_combined"] = round(
            feature["risk_instability"]
            + feature["risk_entropy"]
            + feature["risk_low_margin"]
            + feature["risk_low_confidence"]
            + feature["risk_insufficient"],
            6,
        )
        features.append(feature)

    return features


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


def topk_metrics(features: list[dict[str, Any]], score_name: str, fractions: list[float]) -> list[dict[str, Any]]:
    rows = [row for row in features if row.get("majority_wrong") is not None]
    total_errors = sum(1 for row in rows if row["majority_wrong"])
    total_correct = len(rows) - total_errors
    base_error_rate = total_errors / len(rows) if rows else 0.0
    ranked = sorted(rows, key=lambda row: float(row.get(score_name) or 0.0), reverse=True)

    results = []
    for fraction in fractions:
        k = max(1, math.ceil(len(ranked) * fraction))
        audited = ranked[:k]
        retained = ranked[k:]
        captured = sum(1 for row in audited if row["majority_wrong"])
        retained_correct = sum(1 for row in retained if not row["majority_wrong"])
        results.append(
            {
                "risk_score": score_name,
                "audit_fraction": fraction,
                "audit_n": k,
                "captured_errors": captured,
                "total_errors": total_errors,
                "precision": round(captured / k, 6) if k else None,
                "recall": round(captured / total_errors, 6) if total_errors else None,
                "random_expected_errors": round(k * base_error_rate, 6),
                "lift_over_random": round(captured / (k * base_error_rate), 6) if base_error_rate else None,
                "retained_n": len(retained),
                "retained_accuracy": round(retained_correct / len(retained), 6) if retained else None,
                "base_accuracy": round(total_correct / len(rows), 6) if rows else None,
            }
        )
    return results


def summarize_scores(features: list[dict[str, Any]], score_names: list[str]) -> list[dict[str, Any]]:
    rows = [row for row in features if row.get("majority_wrong") is not None]
    labels = [bool(row["majority_wrong"]) for row in rows]
    summary = []
    for score_name in score_names:
        scores = [float(row.get(score_name) or 0.0) for row in rows]
        summary.append(
            {
                "risk_score": score_name,
                "auc_majority_wrong": roc_auc(scores, labels),
                "mean_score_wrong": safe_mean([score for score, label in zip(scores, labels) if label]),
                "mean_score_correct": safe_mean([score for score, label in zip(scores, labels) if not label]),
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, default=Path("data/pilot/pilot_samples.jsonl"))
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    samples = {row["sample_id"]: row for row in read_jsonl(args.samples)}
    judgments = list(read_jsonl(args.judgments))
    features = build_features(samples, judgments)

    score_names = [
        "risk_disagreement",
        "risk_instability",
        "risk_entropy",
        "risk_low_margin",
        "risk_low_confidence",
        "risk_insufficient",
        "risk_combined",
    ]
    score_summary = summarize_scores(features, score_names)
    audit_rows: list[dict[str, Any]] = []
    for score_name in score_names:
        audit_rows.extend(topk_metrics(features, score_name, [0.1, 0.2, 0.3, 0.4]))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "sample_reliability_features.csv", features)
    write_csv(args.out_dir / "risk_score_summary.csv", score_summary)
    write_csv(args.out_dir / "audit_topk_metrics.csv", audit_rows)

    print(f"Wrote reliability features and baselines to {args.out_dir}")
    print("Score summary:")
    for row in score_summary:
        print(row)


if __name__ == "__main__":
    main()
