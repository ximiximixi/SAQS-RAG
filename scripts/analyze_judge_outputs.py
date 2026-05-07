#!/usr/bin/env python3
"""Analyze judge outputs for accuracy and instability signals."""

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
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


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


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n) / denom
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


def rate_summary(values: list[bool]) -> dict[str, Any]:
    n = len(values)
    k = sum(1 for value in values if value)
    low, high = wilson_ci(k, n)
    return {
        "n": n,
        "count": k,
        "rate": round(k / n, 4) if n else None,
        "wilson95_low": low,
        "wilson95_high": high,
    }


def accuracy(rows: list[dict[str, Any]], count_insufficient_wrong: bool) -> dict[str, Any]:
    scored = []
    for row in rows:
        pred = verdict_to_binary(row.get("verdict"))
        gold = row.get("gold_label") == "faithful"
        if pred is None:
            if count_insufficient_wrong:
                scored.append(False)
            continue
        scored.append(pred == gold)
    correct = sum(1 for item in scored if item)
    low, high = wilson_ci(correct, len(scored))
    return {
        "n_scored": len(scored),
        "n_correct": correct,
        "accuracy": round(correct / len(scored), 4) if scored else None,
        "wilson95_low": low,
        "wilson95_high": high,
    }


def majority_vote(verdicts: list[str]) -> str | None:
    binary = [item for item in verdicts if item in {"faithful", "unfaithful"}]
    if not binary:
        return None
    counts = Counter(binary)
    if counts["faithful"] == counts["unfaithful"]:
        return "tie"
    return counts.most_common(1)[0][0]


def grouped_metrics(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[tuple(row.get(key) for key in keys)].append(row)

    result = []
    for group_key, group_rows in sorted(buckets.items(), key=lambda item: str(item[0])):
        entry = {key: value for key, value in zip(keys, group_key)}
        parsed_rows = [row for row in group_rows if row.get("parsed_ok") and not row.get("error")]
        entry["n"] = len(group_rows)
        entry["n_parsed_no_error"] = len(parsed_rows)
        entry["parsed_rate"] = mean([1.0 if row.get("parsed_ok") else 0.0 for row in group_rows])
        entry["error_rate"] = mean([1.0 if row.get("error") else 0.0 for row in group_rows])
        entry["length_finish_rate"] = mean([1.0 if row.get("finish_reason") == "length" else 0.0 for row in group_rows])
        entry["insufficient_rate"] = mean([1.0 if row.get("verdict") == "insufficient" else 0.0 for row in group_rows])
        entry["accuracy_ignore_insufficient"] = accuracy(group_rows, False)["accuracy"]
        entry["accuracy_count_insufficient_wrong"] = accuracy(group_rows, True)["accuracy"]
        entry["accuracy_parsed_only_ignore_insufficient"] = accuracy(parsed_rows, False)["accuracy"]
        entry["accuracy_parsed_only_count_insufficient_wrong"] = accuracy(parsed_rows, True)["accuracy"]
        result.append(entry)
    return result


def sample_reliability(samples: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_sample[row["sample_id"]].append(row)

    result = []
    for sample_id, sample_rows in sorted(by_sample.items()):
        sample = samples.get(sample_id, {})
        verdicts = [row.get("verdict") for row in sample_rows if row.get("verdict")]
        binary_verdicts = [v for v in verdicts if v in {"faithful", "unfaithful"}]
        unique_binary = sorted(set(binary_verdicts))
        majority = majority_vote(binary_verdicts)
        gold = sample.get("gold_label")

        by_prompt: dict[str, set[str]] = defaultdict(set)
        by_order: dict[str, set[str]] = defaultdict(set)
        for row in sample_rows:
            verdict = row.get("verdict")
            if not verdict:
                continue
            by_prompt[row.get("prompt_id")].add(verdict)
            by_order[row.get("evidence_order")].add(verdict)

        prompt_flip_count = sum(1 for values in by_order.values() if len(values) > 1)
        order_flip_count = sum(1 for values in by_prompt.values() if len(values) > 1)
        confidences = [
            float(row["confidence"])
            for row in sample_rows
            if isinstance(row.get("confidence"), (int, float))
        ]
        majority_correct = None
        if majority in {"faithful", "unfaithful"} and gold:
            majority_correct = majority == gold

        result.append(
            {
                "sample_id": sample_id,
                "dataset": sample.get("dataset") or (sample_rows[0].get("dataset") if sample_rows else None),
                "gold_label": gold,
                "n_judgments": len(sample_rows),
                "distinct_binary_verdicts": "|".join(unique_binary),
                "majority_verdict": majority,
                "majority_correct": majority_correct,
                "any_disagreement": len(unique_binary) > 1,
                "prompt_flip_count": prompt_flip_count,
                "order_flip_count": order_flip_count,
                "insufficient_count": sum(1 for row in sample_rows if row.get("verdict") == "insufficient"),
                "parse_failure_count": sum(1 for row in sample_rows if not row.get("parsed_ok")),
                "mean_confidence": mean(confidences),
                "confidence_std": round(statistics.pstdev(confidences), 4) if len(confidences) > 1 else None,
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, default=Path("data/pilot/pilot_samples.jsonl"))
    parser.add_argument("--judgments", type=Path, default=Path("data/pilot/judge_outputs.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/pilot/analysis"))
    args = parser.parse_args()

    samples = {row["sample_id"]: row for row in read_jsonl(args.samples)}
    rows = list(read_jsonl(args.judgments))
    if not rows:
        print(f"No judgments found at {args.judgments}")
        return

    summary = {
        "n_samples_total": len(samples),
        "n_judgments": len(rows),
        "n_samples_with_judgments": len({row["sample_id"] for row in rows}),
        "n_errors": sum(1 for row in rows if row.get("error")),
        "n_parsed_no_error": sum(1 for row in rows if row.get("parsed_ok") and not row.get("error")),
        "verdict_counts": dict(sorted(Counter(row.get("verdict") for row in rows).items(), key=lambda item: str(item[0]))),
        "finish_reason_counts": dict(sorted(Counter(row.get("finish_reason") for row in rows).items(), key=lambda item: str(item[0]))),
        "parsed_rate": mean([1.0 if row.get("parsed_ok") else 0.0 for row in rows]),
        "error_rate": mean([1.0 if row.get("error") else 0.0 for row in rows]),
        "length_finish_rate": mean([1.0 if row.get("finish_reason") == "length" else 0.0 for row in rows]),
        "overall_accuracy_ignore_insufficient": accuracy(rows, False),
        "overall_accuracy_count_insufficient_wrong": accuracy(rows, True),
        "parsed_only_accuracy_ignore_insufficient": accuracy(
            [row for row in rows if row.get("parsed_ok") and not row.get("error")], False
        ),
        "parsed_only_accuracy_count_insufficient_wrong": accuracy(
            [row for row in rows if row.get("parsed_ok") and not row.get("error")], True
        ),
        "by_dataset": grouped_metrics(rows, ["dataset"]),
        "by_prompt": grouped_metrics(rows, ["prompt_id"]),
        "by_order": grouped_metrics(rows, ["evidence_order"]),
        "by_dataset_prompt": grouped_metrics(rows, ["dataset", "prompt_id"]),
    }

    per_sample = sample_reliability(samples, rows)
    summary["sample_disagreement"] = rate_summary([bool(row["any_disagreement"]) for row in per_sample])
    summary["sample_disagreement_rate"] = summary["sample_disagreement"]["rate"]
    majority_values = [bool(row["majority_correct"]) for row in per_sample if row["majority_correct"] is not None]
    summary["majority_accuracy_summary"] = rate_summary(majority_values)
    summary["majority_accuracy"] = summary["majority_accuracy_summary"]["rate"]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "summary.json", summary)
    write_csv(args.out_dir / "per_sample_reliability.csv", per_sample)
    write_csv(args.out_dir / "metrics_by_dataset_prompt.csv", summary["by_dataset_prompt"])

    print(f"Wrote analysis to {args.out_dir}")
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
