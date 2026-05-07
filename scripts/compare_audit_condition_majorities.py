#!/usr/bin/env python3
"""Compare majority labels across audit labeling conditions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_table(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["audit_id"]: row for row in csv.DictReader(handle) if row.get("audit_id")}


def get_field(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name, "")
        if value:
            return value
    return ""


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def pairwise_stats(rows: list[dict[str, Any]], conditions: list[str]) -> dict[str, Any]:
    out = {}
    for i, left in enumerate(conditions):
        for right in conditions[i + 1 :]:
            comparable = [row for row in rows if row.get(left) and row.get(right)]
            diff = [row for row in comparable if row[left] != row[right]]
            key = f"{left}__vs__{right}"
            out[key] = {
                "n": len(comparable),
                "different": len(diff),
                "different_rate": len(diff) / len(comparable) if comparable else None,
                "left_counts": dict(Counter(row[left] for row in comparable)),
                "right_counts": dict(Counter(row[right] for row in comparable)),
            }
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--old-five",
        type=Path,
        default=Path("data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv"),
    )
    parser.add_argument(
        "--strict-five",
        type=Path,
        default=Path("data/audit/strict_independent_comparison_5models/strict_independent_by_item.csv"),
    )
    parser.add_argument(
        "--assisted-v1",
        type=Path,
        default=Path("data/audit/assisted_adjudication_comparison_3models/assisted_adjudication_by_item.csv"),
    )
    parser.add_argument(
        "--assisted-v2",
        type=Path,
        default=Path("data/audit/strict_assisted_v2_comparison_3models/assisted_adjudication_by_item.csv"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/audit/audit_condition_majority_comparison"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    old_five = read_table(args.old_five)
    strict_five = read_table(args.strict_five)
    assisted_v1 = read_table(args.assisted_v1)
    assisted_v2 = read_table(args.assisted_v2)

    common_ids = sorted(set(old_five) & set(strict_five) & set(assisted_v1) & set(assisted_v2))
    rows = []
    for audit_id in common_ids:
        old = old_five[audit_id]
        strict = strict_five[audit_id]
        v1 = assisted_v1[audit_id]
        v2 = assisted_v2[audit_id]
        row = {
            "audit_id": audit_id,
            "dataset": get_field(strict, "dataset", "missing"),
            "primary_stratum": get_field(strict, "primary_stratum", "missing"),
            "gold_label": get_field(strict, "gold_label", "missing"),
            "old_five_majority": get_field(old, "majority_label"),
            "strict_five_majority": get_field(strict, "strict_majority_label"),
            "assisted_v1_majority": get_field(v1, "majority_label"),
            "assisted_v2_majority": get_field(v2, "majority_label"),
            "old_to_strict_changed": str(get_field(old, "majority_label") != get_field(strict, "strict_majority_label")),
            "strict_to_v2_changed": str(get_field(strict, "strict_majority_label") != get_field(v2, "majority_label")),
            "v1_to_v2_changed": str(get_field(v1, "majority_label") != get_field(v2, "majority_label")),
        }
        rows.append(row)

    conditions = [
        "old_five_majority",
        "strict_five_majority",
        "assisted_v1_majority",
        "assisted_v2_majority",
    ]
    summary = {
        "n_items": len(rows),
        "condition_label_counts": {
            condition: dict(Counter(row[condition] for row in rows)) for condition in conditions
        },
        "pairwise": pairwise_stats(rows, conditions),
        "changed_counts": {
            "old_to_strict": sum(1 for row in rows if row["old_to_strict_changed"] == "True"),
            "strict_to_v2": sum(1 for row in rows if row["strict_to_v2_changed"] == "True"),
            "v1_to_v2": sum(1 for row in rows if row["v1_to_v2_changed"] == "True"),
        },
    }

    fields = [
        "audit_id",
        "dataset",
        "primary_stratum",
        "gold_label",
        "old_five_majority",
        "strict_five_majority",
        "assisted_v1_majority",
        "assisted_v2_majority",
        "old_to_strict_changed",
        "strict_to_v2_changed",
        "v1_to_v2_changed",
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "condition_majorities_by_item.csv", rows, fields)
    with (args.out_dir / "condition_majorities_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote outputs to {args.out_dir}")


if __name__ == "__main__":
    main()
