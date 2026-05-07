#!/usr/bin/env python3
"""Compare strict independent five-model labels against earlier conditions."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


LABELS = ("faithful", "unfaithful", "insufficient")


def model_slug(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


def read_model_csv(path: Path) -> tuple[str, dict[str, dict[str, str]]]:
    rows = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            audit_id = row.get("audit_id", "").strip()
            if not audit_id:
                continue
            row["label"] = row.get("label", "").strip().lower()
            rows[audit_id] = row
    if not rows:
        raise ValueError(f"No rows loaded from {path}")
    model = next(iter(rows.values())).get("model", path.stem)
    return model, rows


def read_table(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["audit_id"]: row for row in csv.DictReader(handle) if row.get("audit_id")}


def majority(labels: list[str]) -> str:
    counts = Counter(labels)
    if not counts:
        return ""
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "tie"
    return top[0][0]


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    ca = Counter(a)
    cb = Counter(b)
    expected = sum((ca[label] / n) * (cb[label] / n) for label in LABELS)
    if math.isclose(expected, 1.0):
        return None
    return (observed - expected) / (1 - expected)


def parse_issues(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument(
        "--old-five",
        type=Path,
        default=Path("data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv"),
    )
    parser.add_argument(
        "--assisted-three",
        type=Path,
        default=Path("data/audit/assisted_adjudication_comparison_3models/assisted_adjudication_by_item.csv"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("data/audit/human_audit_batch_100_metadata.csv"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/audit/strict_independent_comparison_5models"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_rows = {}
    models = []
    for input_path in args.inputs:
        model, rows = read_model_csv(Path(input_path))
        models.append(model)
        model_rows[model] = rows

    common_ids = sorted(set.intersection(*(set(rows) for rows in model_rows.values())))
    old_five = read_table(args.old_five)
    assisted_three = read_table(args.assisted_three)
    metadata = read_table(args.metadata)

    aligned = []
    for audit_id in common_ids:
        labels = [model_rows[model][audit_id].get("label", "") for model in models]
        maj = majority(labels)
        meta = metadata.get(audit_id, {})
        old = old_five.get(audit_id, {})
        assisted = assisted_three.get(audit_id, {})
        out = {
            "audit_id": audit_id,
            "dataset": meta.get("dataset", old.get("dataset", "")),
            "primary_stratum": meta.get("primary_stratum", old.get("primary_stratum", "")),
            "gold_label": meta.get("gold_label", old.get("gold_label", "")),
            "n_models": len(models),
            "unique_label_count": len(set(labels)),
            "unanimous": len(set(labels)) == 1,
            "strict_majority_label": maj,
            "strict_label_vote_counts": json.dumps(dict(Counter(labels)), ensure_ascii=False),
            "old_5model_majority_label": old.get("majority_label", ""),
            "old_5model_vote_counts": old.get("label_vote_counts", ""),
            "assisted_3model_majority_label": assisted.get("majority_label", ""),
            "assisted_3model_vote_counts": assisted.get("label_vote_counts", ""),
            "strict_changed_from_old_5model": str(bool(old.get("majority_label")) and maj != old.get("majority_label")),
            "strict_changed_from_assisted_3model": str(bool(assisted.get("majority_label")) and maj != assisted.get("majority_label")),
        }
        for model in models:
            slug = model_slug(model)
            row = model_rows[model][audit_id]
            out[f"{slug}_label"] = row.get("label", "")
            out[f"{slug}_confidence"] = row.get("confidence", "")
            out[f"{slug}_issues"] = row.get("issue_categories", "")
            out[f"{slug}_notes"] = row.get("notes", "")
        aligned.append(out)

    pairwise = []
    for i, left in enumerate(models):
        for right in models[i + 1 :]:
            left_labels = [model_rows[left][audit_id].get("label", "") for audit_id in common_ids]
            right_labels = [model_rows[right][audit_id].get("label", "") for audit_id in common_ids]
            agree = sum(1 for x, y in zip(left_labels, right_labels) if x == y)
            pairwise.append(
                {
                    "left": left,
                    "right": right,
                    "n": len(common_ids),
                    "agreement": agree,
                    "agreement_rate": agree / len(common_ids),
                    "cohen_kappa": cohen_kappa(left_labels, right_labels),
                }
            )

    label_summary = {}
    issue_summary = {}
    for model in models:
        rows = list(model_rows[model].values())
        label_summary[model] = dict(Counter(row.get("label", "") for row in rows))
        issues = Counter()
        for row in rows:
            issues.update(parse_issues(row.get("issue_categories", "")))
        issue_summary[model] = issues.most_common(20)

    def group_counts(key: str) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in aligned:
            groups.setdefault(str(row.get(key, "") or "missing"), []).append(row)
        out = {}
        for value, rows in sorted(groups.items()):
            out[value] = {
                "n": len(rows),
                "strict_majority_counts": dict(Counter(row["strict_majority_label"] for row in rows)),
                "unanimous_rate": sum(1 for row in rows if row["unanimous"]) / len(rows),
                "changed_from_old_5model_rate": sum(
                    1 for row in rows if row["strict_changed_from_old_5model"] == "True"
                )
                / len(rows),
            }
        return out

    summary = {
        "models": models,
        "n_common_items": len(common_ids),
        "label_summary": label_summary,
        "issue_summary": issue_summary,
        "pairwise": pairwise,
        "unanimous": sum(1 for row in aligned if row["unanimous"]),
        "unanimous_rate": sum(1 for row in aligned if row["unanimous"]) / len(aligned),
        "strict_majority_label_counts": dict(Counter(row["strict_majority_label"] for row in aligned)),
        "changed_from_old_5model": sum(1 for row in aligned if row["strict_changed_from_old_5model"] == "True"),
        "changed_from_old_5model_rate": sum(1 for row in aligned if row["strict_changed_from_old_5model"] == "True")
        / len(aligned),
        "changed_from_assisted_3model": sum(
            1 for row in aligned if row["strict_changed_from_assisted_3model"] == "True"
        ),
        "changed_from_assisted_3model_rate": sum(
            1 for row in aligned if row["strict_changed_from_assisted_3model"] == "True"
        )
        / len(aligned),
        "by_dataset": group_counts("dataset"),
        "by_primary_stratum": group_counts("primary_stratum"),
    }

    fields = [
        "audit_id",
        "dataset",
        "primary_stratum",
        "gold_label",
        "n_models",
        "unique_label_count",
        "unanimous",
        "strict_majority_label",
        "strict_label_vote_counts",
        "old_5model_majority_label",
        "old_5model_vote_counts",
        "assisted_3model_majority_label",
        "assisted_3model_vote_counts",
        "strict_changed_from_old_5model",
        "strict_changed_from_assisted_3model",
    ]
    for model in models:
        slug = model_slug(model)
        fields.extend(
            [
                f"{slug}_label",
                f"{slug}_confidence",
                f"{slug}_issues",
                f"{slug}_notes",
            ]
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "strict_independent_by_item.csv", aligned, fields)
    write_csv(
        args.out_dir / "strict_independent_pairwise.csv",
        pairwise,
        ["left", "right", "n", "agreement", "agreement_rate", "cohen_kappa"],
    )
    with (args.out_dir / "strict_independent_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote outputs to {args.out_dir}")


if __name__ == "__main__":
    main()
