#!/usr/bin/env python3
"""Build per-item issue-category suggestions from multi-model weak labels."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ISSUE_ORDER = [
    "unsupported_claim",
    "contradiction",
    "evidence_conflict",
    "insufficient_evidence",
    "entity_ambiguity",
    "temporal_conflict",
    "numeric_error",
    "over_specific_answer",
    "answer_format_issue",
    "benchmark_ambiguous",
    "other",
]


def parse_issues(value: str) -> list[str]:
    issues = []
    for part in (value or "").replace(",", "|").replace(";", "|").split("|"):
        issue = part.strip()
        if issue in ISSUE_ORDER and issue not in issues:
            issues.append(issue)
    return issues


def sort_issues(counter: Counter[str]) -> list[str]:
    order = {issue: idx for idx, issue in enumerate(ISSUE_ORDER)}
    return [
        issue
        for issue, _ in sorted(
            counter.items(),
            key=lambda item: (-item[1], order.get(item[0], 999), item[0]),
        )
    ]


def build_suggestions(rows: list[dict[str, str]], min_votes: int) -> dict[str, Any]:
    items: dict[str, Any] = {}
    for row in rows:
        audit_id = row["audit_id"]
        issue_fields = [name for name in row if name.endswith("_issues")]
        counts: Counter[str] = Counter()
        model_issues = {}
        for field in issue_fields:
            model = field[: -len("_issues")]
            issues = parse_issues(row.get(field, ""))
            model_issues[model] = issues
            counts.update(issues)

        suggested = [issue for issue in sort_issues(counts) if counts[issue] >= min_votes]
        fallback = sort_issues(counts)
        items[audit_id] = {
            "audit_id": audit_id,
            "suggested_issue_categories": suggested,
            "all_ai_issue_categories": fallback,
            "issue_category_counts": dict(counts),
            "model_issue_categories": model_issues,
            "ai_majority_label": row.get("majority_label", ""),
            "ai_label_vote_counts": row.get("label_vote_counts", ""),
            "ai_top_label_vote_fraction": row.get("top_label_vote_fraction", ""),
        }
    return {
        "source": "weak_label_comparison_5models",
        "min_votes": min_votes,
        "n_items": len(items),
        "items": items,
    }


def write_csv(path: Path, suggestions: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "audit_id",
        "suggested_issue_categories",
        "all_ai_issue_categories",
        "issue_category_counts",
        "ai_majority_label",
        "ai_label_vote_counts",
        "ai_top_label_vote_fraction",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for audit_id in sorted(suggestions["items"]):
            row = suggestions["items"][audit_id]
            writer.writerow(
                {
                    "audit_id": audit_id,
                    "suggested_issue_categories": "|".join(row["suggested_issue_categories"]),
                    "all_ai_issue_categories": "|".join(row["all_ai_issue_categories"]),
                    "issue_category_counts": json.dumps(row["issue_category_counts"], ensure_ascii=False),
                    "ai_majority_label": row["ai_majority_label"],
                    "ai_label_vote_counts": row["ai_label_vote_counts"],
                    "ai_top_label_vote_fraction": row["ai_top_label_vote_fraction"],
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv"),
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("data/audit/ai_issue_category_suggestions_5models.json"),
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("data/audit/ai_issue_category_suggestions_5models.csv"),
    )
    parser.add_argument("--min-votes", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    suggestions = build_suggestions(rows, args.min_votes)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as handle:
        json.dump(suggestions, handle, ensure_ascii=False, indent=2)
    write_csv(args.out_csv, suggestions)

    n_with = sum(1 for item in suggestions["items"].values() if item["suggested_issue_categories"])
    print(f"Wrote {len(suggestions['items'])} items; {n_with} have at least one suggestion.")
    print(f"JSON: {args.out_json}")
    print(f"CSV: {args.out_csv}")


if __name__ == "__main__":
    main()
