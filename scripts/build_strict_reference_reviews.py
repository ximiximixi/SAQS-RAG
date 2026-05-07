#!/usr/bin/env python3
"""Build reference-review JSON from strict independent five-model outputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
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

LABEL_ZH = {
    "faithful": "忠实",
    "unfaithful": "不忠实",
    "insufficient": "证据不足",
    "tie": "平票",
}

ISSUE_ZH = {
    "answer_format_issue": "回答格式问题",
    "benchmark_ambiguous": "基准/题目歧义",
    "contradiction": "与证据矛盾",
    "entity_ambiguity": "实体歧义",
    "evidence_conflict": "证据冲突",
    "insufficient_evidence": "证据不足",
    "numeric_error": "数字错误",
    "other": "其他",
    "over_specific_answer": "回答过于具体",
    "temporal_conflict": "时间冲突",
    "unsupported_claim": "无证据支持",
}


def model_slug(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


def parse_issues(value: str) -> list[str]:
    out = []
    for part in (value or "").split("|"):
        issue = part.strip()
        if issue and issue not in out:
            out.append(issue)
    return out


def majority(labels: list[str]) -> str:
    counts = Counter(labels)
    if not counts:
        return ""
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "tie"
    return top[0][0]


def sort_issues(counter: Counter[str]) -> list[str]:
    order = {issue: idx for idx, issue in enumerate(ISSUE_ORDER)}
    return [
        issue
        for issue, _ in sorted(counter.items(), key=lambda item: (-item[1], order.get(item[0], 999), item[0]))
    ]


def read_model_csv(path: Path) -> tuple[str, dict[str, dict[str, str]]]:
    rows = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            audit_id = row.get("audit_id", "").strip()
            if audit_id:
                rows[audit_id] = row
    if not rows:
        raise ValueError(f"No rows loaded from {path}")
    model = next(iter(rows.values())).get("model", path.stem)
    return model, rows


def write_suggestions_csv(path: Path, suggestions: dict[str, Any]) -> None:
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
                    "ai_label_vote_counts": json.dumps(row["label_vote_counts"], ensure_ascii=False),
                    "ai_top_label_vote_fraction": row["ai_top_label_vote_fraction"],
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument(
        "--out-reviews-json",
        type=Path,
        default=Path("data/audit/strict_independent_reference_reviews_5models.json"),
    )
    parser.add_argument(
        "--out-reviews-csv",
        type=Path,
        default=Path("data/audit/strict_independent_reference_reviews_5models.csv"),
    )
    parser.add_argument(
        "--out-suggestions-json",
        type=Path,
        default=Path("data/audit/strict_independent_issue_suggestions_5models.json"),
    )
    parser.add_argument(
        "--out-suggestions-csv",
        type=Path,
        default=Path("data/audit/strict_independent_issue_suggestions_5models.csv"),
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
    review_items = {}
    suggestion_items = {}
    flat_rows = []

    for audit_id in common_ids:
        reviews = []
        labels = []
        issue_counts: Counter[str] = Counter()
        model_issue_categories = {}
        for model in models:
            slug = model_slug(model)
            row = model_rows[model][audit_id]
            label = row.get("label", "")
            issues = parse_issues(row.get("issue_categories", ""))
            labels.append(label)
            issue_counts.update(issues)
            model_issue_categories[slug] = issues
            review = {
                "review_id": f"{audit_id}::{slug}",
                "audit_id": audit_id,
                "model": model,
                "model_slug": slug,
                "label": label,
                "label_zh": LABEL_ZH.get(label, label),
                "confidence": row.get("confidence", ""),
                "issues": issues,
                "issues_zh": [ISSUE_ZH.get(issue, issue) for issue in issues],
                "reason": row.get("notes", ""),
                "reason_zh": row.get("notes", ""),
                "definition_applied": row.get("definition_applied", ""),
            }
            reviews.append(review)
            flat_rows.append(review)

        vote_counts = Counter(labels)
        maj = majority(labels)
        top_votes = vote_counts[maj] if maj and maj != "tie" else 0
        top_fraction = top_votes / len(models) if models else 0
        sorted_issues = sort_issues(issue_counts)
        review_items[audit_id] = {
            "audit_id": audit_id,
            "ai_majority_label": maj,
            "ai_majority_label_zh": LABEL_ZH.get(maj, maj),
            "ai_label_vote_counts": json.dumps(dict(vote_counts), ensure_ascii=False),
            "ai_top_label_vote_fraction": str(round(top_fraction, 4)),
            "model_reviews": reviews,
        }
        suggestion_items[audit_id] = {
            "audit_id": audit_id,
            "suggested_issue_categories": sorted_issues,
            "all_ai_issue_categories": sorted_issues,
            "issue_category_counts": dict(issue_counts),
            "model_issue_categories": model_issue_categories,
            "ai_majority_label": maj,
            "label_vote_counts": dict(vote_counts),
            "ai_top_label_vote_fraction": str(round(top_fraction, 4)),
        }

    reviews_output = {
        "source": "strict_independent_five_model_rerun",
        "models": models,
        "n_items": len(review_items),
        "n_models": len(models),
        "items": review_items,
    }
    suggestions_output = {
        "source": "strict_independent_five_model_rerun",
        "models": models,
        "n_items": len(suggestion_items),
        "items": suggestion_items,
    }

    args.out_reviews_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_reviews_json.open("w", encoding="utf-8") as handle:
        json.dump(reviews_output, handle, ensure_ascii=False, indent=2)
    with args.out_suggestions_json.open("w", encoding="utf-8") as handle:
        json.dump(suggestions_output, handle, ensure_ascii=False, indent=2)

    args.out_reviews_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_reviews_csv.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "audit_id",
            "model",
            "label",
            "label_zh",
            "confidence",
            "issues",
            "issues_zh",
            "reason_zh",
            "definition_applied",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in flat_rows:
            writer.writerow(
                {
                    "audit_id": row["audit_id"],
                    "model": row["model"],
                    "label": row["label"],
                    "label_zh": row["label_zh"],
                    "confidence": row["confidence"],
                    "issues": "|".join(row["issues"]),
                    "issues_zh": "|".join(row["issues_zh"]),
                    "reason_zh": row["reason_zh"],
                    "definition_applied": row["definition_applied"],
                }
            )
    write_suggestions_csv(args.out_suggestions_csv, suggestions_output)

    print(f"Wrote {len(review_items)} items and {len(flat_rows)} model reviews.")
    print(f"Reviews JSON: {args.out_reviews_json}")
    print(f"Suggestions JSON: {args.out_suggestions_json}")


if __name__ == "__main__":
    main()
