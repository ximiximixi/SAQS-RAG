#!/usr/bin/env python3
"""Compare weak audit labels produced by multiple LLM judges.

The script intentionally uses only the Python standard library so it can run in
the lightweight project environment. It aligns model CSV outputs by audit_id,
computes agreement/disagreement diagnostics, and optionally joins the hidden
audit metadata for research-side analysis.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


LABELS = ("faithful", "unfaithful", "insufficient")
NONFAITHFUL = {"unfaithful", "insufficient"}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "does",
    "evidence",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Model CSV files from run_audit_model_labels.py.",
    )
    parser.add_argument(
        "--metadata",
        default="data/audit/human_audit_batch_100_metadata.csv",
        help="Optional hidden metadata CSV for research-side stratified analysis.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/audit/weak_label_comparison",
        help="Directory for summary JSON and aligned CSV outputs.",
    )
    return parser.parse_args()


def model_slug(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


def clean_label(value: str) -> str:
    label = (value or "").strip().lower()
    if label in LABELS:
        return label
    if "faith" in label and "un" not in label:
        return "faithful"
    if "insufficient" in label or "unknown" in label or "not enough" in label:
        return "insufficient"
    if "unfaith" in label or "unsupported" in label:
        return "unfaithful"
    return label or "missing"


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_model_csv(path: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            audit_id = (row.get("audit_id") or "").strip()
            if not audit_id:
                continue
            model = (row.get("model") or path.stem).strip()
            row["label"] = clean_label(row.get("label", ""))
            row["confidence_float"] = parse_float(row.get("confidence", ""))
            row["parsed_ok_bool"] = parse_bool(row.get("parsed_ok", ""))
            row["issue_set"] = parse_issue_set(row.get("issue_categories", ""))
            rows[audit_id] = row
    if not rows:
        raise ValueError(f"No model rows loaded from {path}")
    first_model = next(iter(rows.values())).get("model") or path.stem
    return str(first_model), rows


def read_metadata(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {
            row["audit_id"]: row
            for row in csv.DictReader(f)
            if row.get("audit_id")
        }


def parse_issue_set(value: str) -> set[str]:
    if not value:
        return set()
    parts = re.split(r"[|,;/]+", value)
    return {p.strip().lower() for p in parts if p.strip()}


def token_set(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in tokens if len(t) > 2 and t not in STOPWORDS}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def mean(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None and not math.isnan(v)]
    if not vals:
        return None
    return sum(vals) / len(vals)


def stdev(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None and not math.isnan(v)]
    if len(vals) < 2:
        return None
    mu = sum(vals) / len(vals)
    return math.sqrt(sum((v - mu) ** 2 for v in vals) / (len(vals) - 1))


def cohen_kappa(a: list[str], b: list[str], labels: tuple[str, ...]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    ca = Counter(a)
    cb = Counter(b)
    expected = sum((ca[label] / n) * (cb[label] / n) for label in labels)
    if math.isclose(1.0, expected):
        return None
    return (observed - expected) / (1 - expected)


def binary_label(label: str) -> str:
    if label == "faithful":
        return "faithful"
    if label in NONFAITHFUL:
        return "nonfaithful"
    return "missing"


def majority(labels: list[str]) -> str:
    counts = Counter(labels)
    if not counts:
        return "missing"
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "all_different" if len(set(labels)) == len(labels) else "tie"
    return top[0][0]


def metadata_binary_gold(row: dict[str, str]) -> str:
    return binary_label(clean_label(row.get("gold_label", "")))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def build_label_summary(
    model_names: list[str], model_rows: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for model in model_names:
        rows = list(model_rows[model].values())
        label_counts = Counter(row["label"] for row in rows)
        parsed = sum(1 for row in rows if row.get("parsed_ok_bool"))
        confs = [row.get("confidence_float") for row in rows]
        by_label = {}
        for label in LABELS:
            label_confs = [
                row.get("confidence_float")
                for row in rows
                if row.get("label") == label and row.get("confidence_float") is not None
            ]
            by_label[label] = {
                "n": label_counts.get(label, 0),
                "confidence_mean": mean(label_confs),
                "confidence_stdev": stdev(label_confs),
            }
        issue_counts = Counter()
        for row in rows:
            issue_counts.update(row.get("issue_set", set()))
        summary[model] = {
            "n": len(rows),
            "parsed_ok": parsed,
            "parsed_ok_rate": parsed / len(rows) if rows else None,
            "errors": sum(1 for row in rows if row.get("error")),
            "label_counts": dict(label_counts),
            "confidence_mean": mean(confs),
            "confidence_stdev": stdev(confs),
            "by_label": by_label,
            "top_issue_categories": issue_counts.most_common(20),
        }
    return summary


def build_pairwise_summary(
    common_ids: list[str],
    model_names: list[str],
    model_rows: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pair_rows: list[dict[str, Any]] = []
    pair_summary: dict[str, Any] = {}
    for i, left in enumerate(model_names):
        for right in model_names[i + 1 :]:
            left_labels = [model_rows[left][audit_id]["label"] for audit_id in common_ids]
            right_labels = [model_rows[right][audit_id]["label"] for audit_id in common_ids]
            left_bin = [binary_label(x) for x in left_labels]
            right_bin = [binary_label(x) for x in right_labels]
            exact_agree = [
                audit_id
                for audit_id, x, y in zip(common_ids, left_labels, right_labels)
                if x == y
            ]
            binary_agree = [
                audit_id
                for audit_id, x, y in zip(common_ids, left_bin, right_bin)
                if x == y
            ]
            issue_j = [
                jaccard(
                    model_rows[left][audit_id].get("issue_set", set()),
                    model_rows[right][audit_id].get("issue_set", set()),
                )
                for audit_id in common_ids
            ]
            reason_j = [
                jaccard(
                    token_set(model_rows[left][audit_id].get("reason", "")),
                    token_set(model_rows[right][audit_id].get("reason", "")),
                )
                for audit_id in common_ids
            ]
            key = f"{left}__vs__{right}"
            stats = {
                "left": left,
                "right": right,
                "n": len(common_ids),
                "exact_agreement": len(exact_agree),
                "exact_agreement_rate": len(exact_agree) / len(common_ids),
                "exact_cohen_kappa": cohen_kappa(left_labels, right_labels, LABELS),
                "binary_agreement": len(binary_agree),
                "binary_agreement_rate": len(binary_agree) / len(common_ids),
                "binary_cohen_kappa": cohen_kappa(
                    left_bin, right_bin, ("faithful", "nonfaithful")
                ),
                "issue_jaccard_mean": mean(issue_j),
                "reason_token_jaccard_mean": mean(reason_j),
            }
            pair_summary[key] = stats
            pair_rows.append(stats)
    return pair_rows, pair_summary


def build_aligned_rows(
    common_ids: list[str],
    model_names: list[str],
    model_rows: dict[str, dict[str, dict[str, Any]]],
    metadata: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for audit_id in common_ids:
        labels = [model_rows[model][audit_id]["label"] for model in model_names]
        bins = [binary_label(label) for label in labels]
        label_counts = Counter(labels)
        binary_counts = Counter(bins)
        top_label_count = max(label_counts.values()) if label_counts else 0
        top_binary_count = max(binary_counts.values()) if binary_counts else 0
        maj = majority(labels)
        bin_maj = majority(bins)
        meta = metadata.get(audit_id, {})
        gold_bin = metadata_binary_gold(meta) if meta else ""
        out: dict[str, Any] = {
            "audit_id": audit_id,
            "n_models": len(model_names),
            "unique_label_count": len(set(labels)),
            "all_label_options_used": len(set(labels)) == len(LABELS),
            "label_vote_counts": json.dumps(dict(label_counts), ensure_ascii=False),
            "binary_vote_counts": json.dumps(dict(binary_counts), ensure_ascii=False),
            "top_label_vote_count": top_label_count,
            "top_label_vote_fraction": top_label_count / len(model_names),
            "top_binary_vote_count": top_binary_count,
            "top_binary_vote_fraction": top_binary_count / len(model_names),
            "unanimous_exact": len(set(labels)) == 1,
            "majority_label": maj,
            "majority_binary": bin_maj,
            "gold_label": meta.get("gold_label", ""),
            "gold_binary": gold_bin,
            "majority_binary_matches_gold": (
                str(bin_maj == gold_bin) if gold_bin and bin_maj != "all_different" else ""
            ),
            "dataset": meta.get("dataset", ""),
            "primary_stratum": meta.get("primary_stratum", ""),
            "candidate_strata": meta.get("candidate_strata", ""),
            "risk_multi_combined": meta.get("risk_multi_combined", ""),
            "qwen_majority_old": meta.get("qwen_majority", ""),
            "glm_majority_old": meta.get("glm_majority", ""),
            "model_majority_disagreement_old": meta.get(
                "model_majority_disagreement", ""
            ),
            "both_wrong_old": meta.get("both_wrong", ""),
            "any_model_wrong_old": meta.get("any_model_wrong", ""),
        }
        all_issue_sets = []
        reason_sets = []
        for model in model_names:
            slug = model_slug(model)
            row = model_rows[model][audit_id]
            out[f"{slug}_label"] = row.get("label", "")
            out[f"{slug}_binary"] = binary_label(row.get("label", ""))
            out[f"{slug}_confidence"] = row.get("confidence", "")
            out[f"{slug}_issues"] = row.get("issue_categories", "")
            out[f"{slug}_reason"] = row.get("reason", "")
            all_issue_sets.append(row.get("issue_set", set()))
            reason_sets.append(token_set(row.get("reason", "")))
        if len(all_issue_sets) >= 2:
            issue_pairs = [
                jaccard(all_issue_sets[i], all_issue_sets[j])
                for i in range(len(all_issue_sets))
                for j in range(i + 1, len(all_issue_sets))
            ]
            reason_pairs = [
                jaccard(reason_sets[i], reason_sets[j])
                for i in range(len(reason_sets))
                for j in range(i + 1, len(reason_sets))
            ]
            out["mean_issue_jaccard"] = mean(issue_pairs)
            out["mean_reason_token_jaccard"] = mean(reason_pairs)
        rows.append(out)
    return rows


def group_summary(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "") or "missing")].append(row)
    out: dict[str, dict[str, Any]] = {}
    for value, items in sorted(groups.items(), key=lambda item: item[0]):
        n = len(items)
        maj_known = [
            row
            for row in items
            if row.get("majority_binary_matches_gold") in {"True", "False"}
        ]
        out[value] = {
            "n": n,
            "unanimous_exact_rate": sum(
                1 for row in items if row.get("unanimous_exact") is True
            )
            / n,
            "all_label_options_used_rate": sum(
                1 for row in items if row.get("all_label_options_used") is True
            )
            / n,
            "mean_top_label_vote_fraction": mean(
                [
                    parse_float(str(row.get("top_label_vote_fraction", "")))
                    for row in items
                ]
            ),
            "mean_issue_jaccard": mean(
                [parse_float(str(row.get("mean_issue_jaccard", ""))) for row in items]
            ),
            "mean_reason_token_jaccard": mean(
                [
                    parse_float(str(row.get("mean_reason_token_jaccard", "")))
                    for row in items
                ]
            ),
            "majority_binary_vs_benchmark_gold_accuracy": (
                sum(
                    1
                    for row in maj_known
                    if row.get("majority_binary_matches_gold") == "True"
                )
                / len(maj_known)
                if maj_known
                else None
            ),
            "majority_label_counts": dict(Counter(row["majority_label"] for row in items)),
        }
    return out


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_rows: dict[str, dict[str, dict[str, Any]]] = {}
    model_names: list[str] = []
    for input_path in args.inputs:
        model, rows = read_model_csv(Path(input_path))
        if model in model_rows:
            raise ValueError(f"Duplicate model name in inputs: {model}")
        model_names.append(model)
        model_rows[model] = rows

    id_sets = [set(rows) for rows in model_rows.values()]
    common_ids = sorted(set.intersection(*id_sets))
    missing_by_model = {
        model: sorted(set.union(*id_sets) - set(rows))
        for model, rows in model_rows.items()
    }
    metadata = read_metadata(Path(args.metadata))

    aligned_rows = build_aligned_rows(common_ids, model_names, model_rows, metadata)
    label_summary = build_label_summary(model_names, model_rows)
    pair_rows, pair_summary = build_pairwise_summary(common_ids, model_names, model_rows)

    unique_label_counts = Counter(row["unique_label_count"] for row in aligned_rows)
    majority_counts = Counter(row["majority_label"] for row in aligned_rows)
    binary_majority_counts = Counter(row["majority_binary"] for row in aligned_rows)
    benchmark_known = [
        row for row in aligned_rows if row.get("majority_binary_matches_gold") in {"True", "False"}
    ]

    multi_model_stats = {
        "unique_label_count_distribution": dict(unique_label_counts),
        "unanimous_exact": unique_label_counts.get(1, 0),
        "unanimous_exact_rate": unique_label_counts.get(1, 0) / len(aligned_rows),
        "non_unanimous": len(aligned_rows) - unique_label_counts.get(1, 0),
        "non_unanimous_rate": 1 - unique_label_counts.get(1, 0) / len(aligned_rows),
        "all_label_options_used": unique_label_counts.get(len(LABELS), 0),
        "all_label_options_used_rate": unique_label_counts.get(len(LABELS), 0)
        / len(aligned_rows),
        "majority_label_counts": dict(majority_counts),
        "majority_binary_counts": dict(binary_majority_counts),
        "mean_top_label_vote_fraction": mean(
            [
                parse_float(str(row.get("top_label_vote_fraction", "")))
                for row in aligned_rows
            ]
        ),
        "mean_top_binary_vote_fraction": mean(
            [
                parse_float(str(row.get("top_binary_vote_fraction", "")))
                for row in aligned_rows
            ]
        ),
    }

    summary = {
        "n_models": len(model_names),
        "models": model_names,
        "n_common_items": len(common_ids),
        "missing_by_model": missing_by_model,
        "label_summary": label_summary,
        "pairwise": pair_summary,
        "multi_model": multi_model_stats,
        "benchmark_gold_comparison_note": (
            "Approximate only: benchmark gold is faithful/unfaithful, while audit labels "
            "allow insufficient as a separate non-faithful decision."
        ),
        "majority_binary_vs_benchmark_gold_accuracy": (
            sum(
                1
                for row in benchmark_known
                if row.get("majority_binary_matches_gold") == "True"
            )
            / len(benchmark_known)
            if benchmark_known
            else None
        ),
        "by_dataset": group_summary(aligned_rows, "dataset"),
        "by_primary_stratum": group_summary(aligned_rows, "primary_stratum"),
    }

    aligned_fields = [
        "audit_id",
        "dataset",
        "gold_label",
        "gold_binary",
        "primary_stratum",
        "candidate_strata",
        "risk_multi_combined",
        "n_models",
        "unique_label_count",
        "all_label_options_used",
        "label_vote_counts",
        "binary_vote_counts",
        "top_label_vote_count",
        "top_label_vote_fraction",
        "top_binary_vote_count",
        "top_binary_vote_fraction",
        "unanimous_exact",
        "majority_label",
        "majority_binary",
        "majority_binary_matches_gold",
        "mean_issue_jaccard",
        "mean_reason_token_jaccard",
        "qwen_majority_old",
        "glm_majority_old",
        "model_majority_disagreement_old",
        "both_wrong_old",
        "any_model_wrong_old",
    ]
    for model in model_names:
        slug = model_slug(model)
        aligned_fields.extend(
            [
                f"{slug}_label",
                f"{slug}_binary",
                f"{slug}_confidence",
                f"{slug}_issues",
                f"{slug}_reason",
            ]
        )

    write_csv(out_dir / "weak_label_comparison_by_item.csv", aligned_rows, aligned_fields)
    write_csv(
        out_dir / "weak_label_pairwise_agreement.csv",
        pair_rows,
        [
            "left",
            "right",
            "n",
            "exact_agreement",
            "exact_agreement_rate",
            "exact_cohen_kappa",
            "binary_agreement",
            "binary_agreement_rate",
            "binary_cohen_kappa",
            "issue_jaccard_mean",
            "reason_token_jaccard_mean",
        ],
    )

    disagreement_rows = sorted(
        [row for row in aligned_rows if row["unique_label_count"] > 1],
        key=lambda row: (
            -int(row.get("all_label_options_used") is True),
            parse_float(str(row.get("top_label_vote_fraction", "1"))) or 1.0,
            -(parse_float(str(row.get("risk_multi_combined", ""))) or -1.0),
        ),
    )
    write_csv(
        out_dir / "weak_label_disagreement_cases.csv",
        disagreement_rows,
        aligned_fields,
    )

    with (out_dir / "weak_label_comparison_summary.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote outputs to {out_dir}")


if __name__ == "__main__":
    main()
