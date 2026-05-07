#!/usr/bin/env python3
"""Prepare a blinded human-audit batch and separate metadata."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["sample_id"]: row for row in csv.DictReader(handle)}


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "1.0"}:
        return True
    if text in {"false", "no", "n", "0", "0.0", ""}:
        return False
    try:
        return float(text) != 0.0
    except ValueError:
        return False


def parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def compact_evidence(evidence: list[dict[str, Any]], max_docs: int, max_chars_per_doc: int) -> str:
    parts = []
    for idx, doc in enumerate(evidence[:max_docs], start=1):
        text = str(doc.get("text") or "").strip()
        if len(text) > max_chars_per_doc:
            text = text[:max_chars_per_doc].rstrip() + "..."
        parts.append(f"[{idx}] {text}")
    return "\n\n".join(parts)


def all_strata(row: dict[str, Any]) -> list[str]:
    strata = []
    if row["model_majority_disagreement"]:
        strata.append("model_majority_disagreement")
    if row["both_wrong"] and not row["model_majority_disagreement"]:
        strata.append("stable_shared_error")
    if row["dataset"] == "ramdocs" and (
        row["risk_task_binary_disagreement"] > 0
        or row["qwen_any_disagreement"]
        or row["glm_any_disagreement"]
    ):
        strata.append("ramdocs_instability")
    if row["risk_multi_combined"] >= row["risk_high_threshold"]:
        strata.append("top_multi_risk")
    if (not row["any_model_wrong"]) and row["risk_multi_combined"] <= row["risk_low_threshold"]:
        strata.append("low_risk_control")
    if not strata:
        strata.append("coverage_fill")
    return strata


def add_by_rule(
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    candidates: list[dict[str, Any]],
    target_total_for_rule: int,
    primary_stratum: str,
) -> None:
    for row in candidates:
        if len([x for x in selected if x["primary_stratum"] == primary_stratum]) >= target_total_for_rule:
            break
        if row["sample_id"] in selected_ids:
            continue
        row = dict(row)
        row["primary_stratum"] = primary_stratum
        selected.append(row)
        selected_ids.add(row["sample_id"])


def round_robin_fill(
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    candidates: list[dict[str, Any]],
    target_total: int,
    seed: int,
) -> None:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        if row["sample_id"] not in selected_ids:
            buckets[row["dataset"]].append(row)
    for rows in buckets.values():
        rng.shuffle(rows)

    while len(selected) < target_total:
        progressed = False
        for dataset in sorted(buckets):
            while buckets[dataset] and buckets[dataset][0]["sample_id"] in selected_ids:
                buckets[dataset].pop(0)
            if not buckets[dataset]:
                continue
            row = dict(buckets[dataset].pop(0))
            row["primary_stratum"] = "coverage_fill"
            selected.append(row)
            selected_ids.add(row["sample_id"])
            progressed = True
            if len(selected) >= target_total:
                break
        if not progressed:
            break


def build_candidate_rows(
    samples: dict[str, dict[str, Any]],
    multi_risk: dict[str, dict[str, str]],
    multi: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    risk_values = sorted(parse_float(row["risk_multi_combined"]) for row in multi_risk.values())
    high_idx = int(0.8 * (len(risk_values) - 1))
    low_idx = int(0.2 * (len(risk_values) - 1))
    high_threshold = risk_values[high_idx]
    low_threshold = risk_values[low_idx]

    rows = []
    for sample_id, sample in samples.items():
        risk = multi_risk[sample_id]
        mj = multi[sample_id]
        row = {
            "sample_id": sample_id,
            "dataset": sample["dataset"],
            "gold_label": sample["gold_label"],
            "question": sample["question"],
            "answer": sample["answer"],
            "evidence": sample.get("evidence") or [],
            "risk_multi_combined": parse_float(risk["risk_multi_combined"]),
            "risk_qwen_combined": parse_float(risk["risk_qwen_combined"]),
            "risk_glm_combined": parse_float(risk["risk_glm_combined"]),
            "risk_task_binary_disagreement": parse_float(risk["risk_task_binary_disagreement"]),
            "model_majority_disagreement": parse_bool(risk["risk_model_majority_disagreement"]),
            "qwen_wrong": parse_bool(risk["qwen_wrong"]),
            "glm_wrong": parse_bool(risk["glm_wrong"]),
            "both_wrong": parse_bool(risk["both_wrong"]),
            "any_model_wrong": parse_bool(risk["any_model_wrong"]),
            "combined_wrong": parse_bool(risk["combined_wrong"]),
            "qwen_majority": mj["qwen35plus_majority"],
            "glm_majority": mj["glm51_majority"],
            "combined_majority": mj["combined_majority"],
            "qwen_any_disagreement": parse_bool(mj["qwen35plus_any_disagreement"]),
            "glm_any_disagreement": parse_bool(mj["glm51_any_disagreement"]),
            "combined_any_disagreement": parse_bool(mj["combined_any_disagreement"]),
            "per_task_binary_disagreement_rate": parse_float(mj["per_task_binary_disagreement_rate"]),
            "risk_high_threshold": high_threshold,
            "risk_low_threshold": low_threshold,
        }
        row["candidate_strata"] = all_strata(row)
        rows.append(row)
    return rows


def select_batch(rows: list[dict[str, Any]], target_total: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    model_disagree = sorted(
        [row for row in rows if row["model_majority_disagreement"]],
        key=lambda row: row["risk_multi_combined"],
        reverse=True,
    )
    stable_shared = sorted(
        [row for row in rows if row["both_wrong"] and not row["model_majority_disagreement"]],
        key=lambda row: row["risk_multi_combined"],
        reverse=True,
    )
    ramdocs_instability = sorted(
        [
            row
            for row in rows
            if row["dataset"] == "ramdocs"
            and (
                row["risk_task_binary_disagreement"] > 0
                or row["qwen_any_disagreement"]
                or row["glm_any_disagreement"]
            )
        ],
        key=lambda row: row["risk_multi_combined"],
        reverse=True,
    )
    top_risk = sorted(rows, key=lambda row: row["risk_multi_combined"], reverse=True)
    low_risk = sorted(
        [row for row in rows if not row["any_model_wrong"]],
        key=lambda row: row["risk_multi_combined"],
    )

    # These are intentionally overlapping concepts. The selection is priority-based,
    # while candidate_strata records every reason a sample belongs to.
    add_by_rule(selected, selected_ids, model_disagree, 13, "model_majority_disagreement")
    add_by_rule(selected, selected_ids, stable_shared, 22, "stable_shared_error")
    add_by_rule(selected, selected_ids, ramdocs_instability, 20, "ramdocs_instability")
    add_by_rule(selected, selected_ids, top_risk, 25, "top_multi_risk")
    add_by_rule(selected, selected_ids, low_risk, 20, "low_risk_control")

    remaining = list(rows)
    rng.shuffle(remaining)
    round_robin_fill(selected, selected_ids, remaining, target_total, seed + 17)
    return selected[:target_total]


def make_outputs(selected: list[dict[str, Any]], out_prefix: str, out_dir: Path) -> None:
    blind_csv_rows = []
    blind_json_rows = []
    metadata_rows = []

    for idx, row in enumerate(selected, start=1):
        audit_id = f"AUDIT-{idx:03d}"
        evidence_compact = compact_evidence(row["evidence"], max_docs=8, max_chars_per_doc=1200)
        blind = {
            "audit_id": audit_id,
            "question": row["question"],
            "answer": row["answer"],
            "evidence": evidence_compact,
            "annotator_label": "",
            "annotator_confidence": "",
            "issue_categories": "",
            "notes": "",
        }
        blind_csv_rows.append(blind)
        blind_json_rows.append(
            {
                "audit_id": audit_id,
                "question": row["question"],
                "answer": row["answer"],
                "evidence": row["evidence"],
                "annotation": {
                    "annotator_label": "",
                    "annotator_confidence": "",
                    "issue_categories": [],
                    "notes": "",
                },
            }
        )
        metadata_rows.append(
            {
                "audit_id": audit_id,
                "sample_id": row["sample_id"],
                "dataset": row["dataset"],
                "gold_label": row["gold_label"],
                "primary_stratum": row["primary_stratum"],
                "candidate_strata": "|".join(row["candidate_strata"]),
                "risk_multi_combined": row["risk_multi_combined"],
                "risk_qwen_combined": row["risk_qwen_combined"],
                "risk_glm_combined": row["risk_glm_combined"],
                "model_majority_disagreement": row["model_majority_disagreement"],
                "per_task_binary_disagreement_rate": row["per_task_binary_disagreement_rate"],
                "qwen_majority": row["qwen_majority"],
                "glm_majority": row["glm_majority"],
                "combined_majority": row["combined_majority"],
                "qwen_wrong": row["qwen_wrong"],
                "glm_wrong": row["glm_wrong"],
                "both_wrong": row["both_wrong"],
                "any_model_wrong": row["any_model_wrong"],
                "combined_wrong": row["combined_wrong"],
            }
        )

    write_csv(out_dir / f"{out_prefix}_blind.csv", blind_csv_rows)
    write_jsonl(out_dir / f"{out_prefix}_blind.jsonl", blind_json_rows)
    write_csv(out_dir / f"{out_prefix}_metadata.csv", metadata_rows)

    summary = {
        "n": len(selected),
        "by_primary_stratum": dict(Counter(row["primary_stratum"] for row in selected)),
        "by_dataset": dict(Counter(row["dataset"] for row in selected)),
        "by_gold_label": dict(Counter(row["gold_label"] for row in selected)),
        "by_dataset_gold": {
            f"{dataset}|{label}": count
            for (dataset, label), count in Counter((row["dataset"], row["gold_label"]) for row in selected).items()
        },
        "model_majority_disagreement": sum(1 for row in selected if row["model_majority_disagreement"]),
        "both_wrong": sum(1 for row in selected if row["both_wrong"]),
        "any_model_wrong": sum(1 for row in selected if row["any_model_wrong"]),
        "combined_wrong": sum(1 for row in selected if row["combined_wrong"]),
    }
    write_json(out_dir / f"{out_prefix}_selection_summary.json", summary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, default=Path("data/pilot/pilot_samples.jsonl"))
    parser.add_argument("--multi-risk", type=Path, required=True)
    parser.add_argument("--multi-samples", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("data/audit"))
    parser.add_argument("--out-prefix", default="human_audit_batch_100")
    parser.add_argument("--target-total", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260424)
    args = parser.parse_args()

    samples = {row["sample_id"]: row for row in read_jsonl(args.samples)}
    multi_risk = read_csv_by_id(args.multi_risk)
    multi = read_csv_by_id(args.multi_samples)
    rows = build_candidate_rows(samples, multi_risk, multi)
    selected = select_batch(rows, args.target_total, args.seed)
    make_outputs(selected, args.out_prefix, args.out_dir)

    print(f"Wrote audit batch to {args.out_dir}")
    print(json.dumps(json.loads((args.out_dir / f"{args.out_prefix}_selection_summary.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
