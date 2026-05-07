#!/usr/bin/env python3
"""Compare two judge models on the same perturbed RAG evaluation tasks."""

from __future__ import annotations

import argparse
import csv
import json
import math
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


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


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n) / denom
    return round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)


def rate_summary(values: list[bool]) -> dict[str, Any]:
    n = len(values)
    k = sum(1 for value in values if value)
    low, high = wilson_ci(k, n)
    return {
        "n": n,
        "count": k,
        "rate": round(k / n, 6) if n else None,
        "wilson95_low": low,
        "wilson95_high": high,
    }


def index_by_sample(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["sample_id"]].append(row)
    return grouped


def perturb_key(row: dict[str, Any]) -> tuple[str, str]:
    return row["prompt_id"], row["evidence_order"]


def sample_stats(rows: list[dict[str, Any]], gold_label: str) -> dict[str, Any]:
    verdicts = [row.get("verdict") for row in rows if row.get("verdict")]
    majority = majority_vote(verdicts)
    correct = majority == gold_label if majority in {"faithful", "unfaithful"} else None
    binary = [item for item in verdicts if item in {"faithful", "unfaithful"}]
    counts = Counter(binary)
    any_disagreement = counts["faithful"] > 0 and counts["unfaithful"] > 0
    judgment_correct = []
    for verdict in verdicts:
        pred = verdict_to_binary(verdict)
        if pred is None:
            continue
        judgment_correct.append(pred == (gold_label == "faithful"))
    return {
        "majority": majority,
        "majority_correct": correct,
        "faithful_count": counts["faithful"],
        "unfaithful_count": counts["unfaithful"],
        "insufficient_count": sum(1 for row in rows if row.get("verdict") == "insufficient"),
        "any_disagreement": any_disagreement,
        "judgment_accuracy": mean([1.0 if item else 0.0 for item in judgment_correct]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, default=Path("data/pilot/pilot_samples.jsonl"))
    parser.add_argument("--judge-a", type=Path, required=True)
    parser.add_argument("--label-a", default="judge_a")
    parser.add_argument("--judge-b", type=Path, required=True)
    parser.add_argument("--label-b", default="judge_b")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    samples = {row["sample_id"]: row for row in read_jsonl(args.samples)}
    rows_a = list(read_jsonl(args.judge_a))
    rows_b = list(read_jsonl(args.judge_b))
    by_sample_a = index_by_sample(rows_a)
    by_sample_b = index_by_sample(rows_b)

    sample_rows: list[dict[str, Any]] = []
    for sample_id in sorted(samples):
        sample = samples[sample_id]
        gold = sample["gold_label"]
        a_rows = by_sample_a.get(sample_id, [])
        b_rows = by_sample_b.get(sample_id, [])
        a_stats = sample_stats(a_rows, gold)
        b_stats = sample_stats(b_rows, gold)
        combined_stats = sample_stats(a_rows + b_rows, gold)

        a_by_key = {perturb_key(row): row for row in a_rows}
        b_by_key = {perturb_key(row): row for row in b_rows}
        matched_keys = sorted(set(a_by_key) & set(b_by_key))
        per_task_binary_disagreements = 0
        per_task_comparable = 0
        per_task_any_disagreements = 0
        for key in matched_keys:
            av = a_by_key[key].get("verdict")
            bv = b_by_key[key].get("verdict")
            if av != bv:
                per_task_any_disagreements += 1
            ab = verdict_to_binary(av)
            bb = verdict_to_binary(bv)
            if ab is not None and bb is not None:
                per_task_comparable += 1
                if ab != bb:
                    per_task_binary_disagreements += 1

        a_wrong = a_stats["majority_correct"] is False
        b_wrong = b_stats["majority_correct"] is False
        combined_wrong = combined_stats["majority_correct"] is False
        majority_disagree = (
            a_stats["majority"] in {"faithful", "unfaithful"}
            and b_stats["majority"] in {"faithful", "unfaithful"}
            and a_stats["majority"] != b_stats["majority"]
        )

        sample_rows.append(
            {
                "sample_id": sample_id,
                "dataset": sample["dataset"],
                "gold_label": gold,
                f"{args.label_a}_majority": a_stats["majority"],
                f"{args.label_a}_majority_correct": a_stats["majority_correct"],
                f"{args.label_a}_any_disagreement": a_stats["any_disagreement"],
                f"{args.label_a}_judgment_accuracy": a_stats["judgment_accuracy"],
                f"{args.label_b}_majority": b_stats["majority"],
                f"{args.label_b}_majority_correct": b_stats["majority_correct"],
                f"{args.label_b}_any_disagreement": b_stats["any_disagreement"],
                f"{args.label_b}_judgment_accuracy": b_stats["judgment_accuracy"],
                "combined_majority": combined_stats["majority"],
                "combined_majority_correct": combined_stats["majority_correct"],
                "combined_any_disagreement": combined_stats["any_disagreement"],
                "model_majority_disagreement": majority_disagree,
                "per_task_any_disagreement_rate": round(per_task_any_disagreements / len(matched_keys), 6)
                if matched_keys
                else None,
                "per_task_binary_disagreement_rate": round(
                    per_task_binary_disagreements / per_task_comparable, 6
                )
                if per_task_comparable
                else None,
                "both_wrong": a_wrong and b_wrong,
                "only_a_wrong": a_wrong and not b_wrong,
                "only_b_wrong": b_wrong and not a_wrong,
                "any_model_wrong": a_wrong or b_wrong,
                "combined_wrong": combined_wrong,
            }
        )

    def bool_col(name: str) -> list[bool]:
        return [bool(row[name]) for row in sample_rows if row[name] is not None]

    summary = {
        "n_samples": len(sample_rows),
        "judge_a": args.label_a,
        "judge_b": args.label_b,
        f"{args.label_a}_majority_accuracy": rate_summary(
            [bool(row[f"{args.label_a}_majority_correct"]) for row in sample_rows]
        ),
        f"{args.label_b}_majority_accuracy": rate_summary(
            [bool(row[f"{args.label_b}_majority_correct"]) for row in sample_rows]
        ),
        "combined_majority_accuracy": rate_summary(
            [bool(row["combined_majority_correct"]) for row in sample_rows]
        ),
        "model_majority_disagreement": rate_summary(bool_col("model_majority_disagreement")),
        "both_wrong": rate_summary(bool_col("both_wrong")),
        "only_a_wrong": rate_summary(bool_col("only_a_wrong")),
        "only_b_wrong": rate_summary(bool_col("only_b_wrong")),
        "any_model_wrong": rate_summary(bool_col("any_model_wrong")),
        "combined_wrong": rate_summary(bool_col("combined_wrong")),
        "mean_per_task_any_disagreement_rate": mean(
            [float(row["per_task_any_disagreement_rate"]) for row in sample_rows]
        ),
        "mean_per_task_binary_disagreement_rate": mean(
            [float(row["per_task_binary_disagreement_rate"]) for row in sample_rows]
        ),
    }

    by_dataset = []
    for dataset in sorted({row["dataset"] for row in sample_rows}):
        ds_rows = [row for row in sample_rows if row["dataset"] == dataset]
        by_dataset.append(
            {
                "dataset": dataset,
                "n": len(ds_rows),
                f"{args.label_a}_majority_accuracy": mean(
                    [1.0 if row[f"{args.label_a}_majority_correct"] else 0.0 for row in ds_rows]
                ),
                f"{args.label_b}_majority_accuracy": mean(
                    [1.0 if row[f"{args.label_b}_majority_correct"] else 0.0 for row in ds_rows]
                ),
                "combined_majority_accuracy": mean(
                    [1.0 if row["combined_majority_correct"] else 0.0 for row in ds_rows]
                ),
                "model_majority_disagreement_rate": mean(
                    [1.0 if row["model_majority_disagreement"] else 0.0 for row in ds_rows]
                ),
                "both_wrong_rate": mean([1.0 if row["both_wrong"] else 0.0 for row in ds_rows]),
                "only_a_wrong_rate": mean([1.0 if row["only_a_wrong"] else 0.0 for row in ds_rows]),
                "only_b_wrong_rate": mean([1.0 if row["only_b_wrong"] else 0.0 for row in ds_rows]),
                "mean_per_task_binary_disagreement_rate": mean(
                    [float(row["per_task_binary_disagreement_rate"]) for row in ds_rows]
                ),
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "multi_judge_per_sample.csv", sample_rows)
    write_csv(args.out_dir / "multi_judge_by_dataset.csv", by_dataset)
    write_json(args.out_dir / "multi_judge_summary.json", summary)

    print(f"Wrote multi-judge analysis to {args.out_dir}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
