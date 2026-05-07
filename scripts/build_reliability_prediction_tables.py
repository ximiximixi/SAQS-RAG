#!/usr/bin/env python3
"""Build canonical item-level and verdict-level reliability prediction tables."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


LABELS = ("faithful", "unfaithful", "insufficient", "tie", "missing")

ISSUE_CATEGORIES = [
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

OLD_WEAK_FILES = [
    ("old_weak_qwen36maxpreview", "qwen3.6-max-preview", "weak_labels_qwen36maxpreview.csv"),
    ("old_weak_deepseekv4pro", "deepseek-v4-pro", "weak_labels_deepseekv4pro.csv"),
    ("old_weak_kimik26", "kimi-k2.6", "weak_labels_kimik26.csv"),
    ("old_weak_qwen3max20260123", "qwen3-max-2026-01-23", "weak_labels_qwen3max20260123.csv"),
    ("old_weak_qwen36plus20260402", "qwen3.6-plus-2026-04-02", "weak_labels_qwen36plus20260402.csv"),
]

STRICT_EN_FILES = [
    (
        "strict_en_qwen36maxpreview",
        "qwen3.6-max-preview",
        "strict_independent_en_qwen36maxpreview.csv",
    ),
    ("strict_en_deepseekv4pro", "deepseek-v4-pro", "strict_independent_en_deepseekv4pro.csv"),
    ("strict_en_kimik26", "kimi-k2.6", "strict_independent_en_kimik26.csv"),
    ("strict_en_qwen3max20260123", "qwen3-max-2026-01-23", "strict_independent_en_qwen3max20260123.csv"),
    (
        "strict_en_qwen36plus20260402",
        "qwen3.6-plus-2026-04-02",
        "strict_independent_en_qwen36plus20260402.csv",
    ),
]

TEXT_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "or",
    "to",
    "in",
    "on",
    "for",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "by",
    "as",
    "that",
    "this",
    "it",
    "from",
    "at",
    "which",
    "who",
    "what",
    "when",
    "where",
    "how",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=2)


def norm_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"faithful", "unfaithful", "insufficient", "tie"}:
        return text
    if not text:
        return "missing"
    if "unfaithful" in text or "unsupported" in text or "contradict" in text:
        return "unfaithful"
    if "insufficient" in text:
        return "insufficient"
    if "faithful" in text or "supported" in text:
        return "faithful"
    return text


def parse_bool(value: Any) -> int:
    return 1 if str(value).strip().lower() in {"true", "1", "yes", "y"} else 0


def parse_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_categories(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        parts = value
    else:
        text = str(value).strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parts = json.loads(text)
            except json.JSONDecodeError:
                parts = re.split(r"[|,;]", text)
        else:
            parts = re.split(r"[|,;]", text)
    out = []
    for part in parts:
        cat = str(part).strip()
        if cat in ISSUE_CATEGORIES and cat not in out:
            out.append(cat)
    return out


def majority(labels: list[str]) -> str:
    labels = [norm_label(label) for label in labels if norm_label(label) != "missing"]
    if not labels:
        return "missing"
    counts = Counter(labels)
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "tie"
    return top[0][0]


def vote_stats(labels: list[str], prefix: str) -> dict[str, Any]:
    labels = [norm_label(label) for label in labels]
    counts = Counter(labels)
    total = len(labels)
    sorted_counts = sorted(counts.values(), reverse=True)
    top = sorted_counts[0] if sorted_counts else 0
    second = sorted_counts[1] if len(sorted_counts) > 1 else 0
    entropy = 0.0
    for count in counts.values():
        if count and total:
            p = count / total
            entropy -= p * math.log(p, 2)
    row: dict[str, Any] = {
        f"{prefix}_n_votes": total,
        f"{prefix}_unique_label_count": len(counts),
        f"{prefix}_unanimous": 1 if len(counts) == 1 else 0,
        f"{prefix}_top_vote_count": top,
        f"{prefix}_top_vote_fraction": top / total if total else 0,
        f"{prefix}_vote_margin": top - second,
        f"{prefix}_vote_margin_fraction": (top - second) / total if total else 0,
        f"{prefix}_vote_entropy": entropy,
    }
    for label in LABELS:
        row[f"{prefix}_label_count_{label}"] = counts.get(label, 0)
        row[f"{prefix}_label_fraction_{label}"] = counts.get(label, 0) / total if total else 0
    return row


def confidence_stats(values: list[float | None], prefix: str) -> dict[str, Any]:
    nums = [value for value in values if value is not None]
    if not nums:
        return {
            f"{prefix}_confidence_available_count": 0,
            f"{prefix}_confidence_mean": "",
            f"{prefix}_confidence_min": "",
            f"{prefix}_confidence_max": "",
            f"{prefix}_confidence_std": "",
            f"{prefix}_high_confidence_count": 0,
        }
    mean = sum(nums) / len(nums)
    var = sum((x - mean) ** 2 for x in nums) / len(nums)
    return {
        f"{prefix}_confidence_available_count": len(nums),
        f"{prefix}_confidence_mean": mean,
        f"{prefix}_confidence_min": min(nums),
        f"{prefix}_confidence_max": max(nums),
        f"{prefix}_confidence_std": math.sqrt(var),
        f"{prefix}_high_confidence_count": sum(1 for x in nums if x >= 0.9),
    }


def issue_stats(category_lists: list[list[str]], prefix: str) -> dict[str, Any]:
    counts = Counter()
    for cats in category_lists:
        counts.update(cats)
    row: dict[str, Any] = {
        f"{prefix}_issue_total_count": sum(counts.values()),
        f"{prefix}_issue_unique_count": len(counts),
        f"{prefix}_issue_conflict_ambiguity_bundle": sum(
            counts.get(cat, 0)
            for cat in ["entity_ambiguity", "evidence_conflict", "benchmark_ambiguous", "temporal_conflict"]
        ),
        f"{prefix}_issue_unsupported_contradiction_bundle": sum(
            counts.get(cat, 0)
            for cat in ["unsupported_claim", "contradiction", "numeric_error", "over_specific_answer"]
        ),
    }
    for cat in ISSUE_CATEGORIES:
        row[f"{prefix}_issue_count_{cat}"] = counts.get(cat, 0)
        row[f"{prefix}_issue_has_{cat}"] = 1 if counts.get(cat, 0) else 0
    return row


def tokenize(text: str) -> list[str]:
    tokens = [tok.lower() for tok in re.findall(r"[A-Za-z0-9]+", text or "")]
    return [tok for tok in tokens if tok not in TEXT_STOPWORDS]


def text_features(item: dict[str, Any]) -> dict[str, Any]:
    question = str(item.get("question", "") or "")
    answer = str(item.get("answer", "") or "")
    evidence_docs = item.get("evidence") or []
    evidence_text = " ".join(str(doc.get("text", "") or "") for doc in evidence_docs)
    q_tokens = tokenize(question)
    a_tokens = tokenize(answer)
    e_tokens = tokenize(evidence_text)
    e_set = set(e_tokens)
    answer_overlap = len(set(a_tokens) & e_set) / len(set(a_tokens)) if a_tokens else 0.0
    number_pattern = r"\b\d+(?:\.\d+)?%?\b"
    year_pattern = r"\b(?:18|19|20)\d{2}\b"
    return {
        "text_question_char_len": len(question),
        "text_answer_char_len": len(answer),
        "text_evidence_char_len": len(evidence_text),
        "text_question_token_len": len(q_tokens),
        "text_answer_token_len": len(a_tokens),
        "text_evidence_token_len": len(e_tokens),
        "text_evidence_doc_count": len(evidence_docs),
        "text_answer_evidence_token_overlap": answer_overlap,
        "text_answer_number_count": len(re.findall(number_pattern, answer)),
        "text_evidence_number_count": len(re.findall(number_pattern, evidence_text)),
        "text_answer_year_count": len(re.findall(year_pattern, answer)),
        "text_evidence_year_count": len(re.findall(year_pattern, evidence_text)),
        "text_answer_is_short": 1 if len(a_tokens) <= 8 else 0,
        "text_answer_has_number": 1 if re.search(number_pattern, answer) else 0,
    }


def read_model_outputs(audit_dir: Path, specs: list[tuple[str, str, str]]) -> dict[str, dict[str, dict[str, Any]]]:
    outputs: dict[str, dict[str, dict[str, Any]]] = {}
    for condition, model_name, filename in specs:
        rows = {}
        for row in read_csv(audit_dir / filename):
            audit_id = row["audit_id"]
            rows[audit_id] = {
                "condition": condition,
                "model_name": model_name,
                "label": norm_label(row.get("label")),
                "confidence": parse_float(row.get("confidence")),
                "issue_categories": parse_categories(row.get("issue_categories")),
                "raw": row,
            }
        outputs[condition] = rows
    return outputs


def label_mismatch(pred: str, human: str) -> int:
    return 1 if norm_label(pred) != norm_label(human) else 0


def binary_mismatch_or_blank(pred: str, human: str) -> str:
    pred = norm_label(pred)
    if pred not in {"faithful", "unfaithful"}:
        return ""
    return str(label_mismatch(pred, human))


def add_label_onehots(row: dict[str, Any], prefix: str, label: str) -> None:
    label = norm_label(label)
    row[f"{prefix}_label"] = label
    for option in LABELS:
        row[f"{prefix}_is_{option}"] = 1 if label == option else 0


def add_pairwise_label_features(row: dict[str, Any], labels: dict[str, str]) -> None:
    keys = list(labels)
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            row[f"disagree_{left}__{right}"] = 1 if norm_label(labels[left]) != norm_label(labels[right]) else 0
    row["main_condition_pairwise_disagreement_count"] = sum(
        1 for key, value in row.items() if key.startswith("disagree_") and value == 1
    )


def make_majority_record(
    audit_id: str,
    protocol: str,
    source_name: str,
    member_records: list[dict[str, Any]],
) -> dict[str, Any]:
    labels = [record["label"] for record in member_records]
    maj = majority(labels)
    selected = [record for record in member_records if record["label"] == maj]
    if not selected:
        selected = member_records
    cats = []
    confs = []
    for record in selected:
        cats.extend(record.get("issue_categories", []))
        if record.get("confidence") is not None:
            confs.append(record["confidence"])
    return {
        "audit_id": audit_id,
        "condition": source_name,
        "model_name": source_name,
        "protocol": protocol,
        "condition_type": "majority",
        "label": maj,
        "confidence": sum(confs) / len(confs) if confs else None,
        "issue_categories": sorted(set(cats)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", type=Path, default=Path("data/audit"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/audit/reliability"))
    args = parser.parse_args()

    audit_dir = args.audit_dir
    out_dir = args.out_dir

    metadata = {row["audit_id"]: row for row in read_csv(audit_dir / "human_audit_batch_100_metadata.csv")}
    human = {row["audit_id"]: row for row in read_csv(audit_dir / "human_audit_annotations_en.csv")}
    batch = {row["audit_id"]: row for row in read_jsonl(audit_dir / "human_audit_batch_100_blind.jsonl")}
    old_outputs = read_model_outputs(audit_dir, OLD_WEAK_FILES)
    strict_outputs = read_model_outputs(audit_dir, STRICT_EN_FILES)

    audit_ids = sorted(human, key=lambda x: int(x.split("-")[-1]))
    item_rows: list[dict[str, Any]] = []
    verdict_rows: list[dict[str, Any]] = []

    for audit_id in audit_ids:
        meta = metadata[audit_id]
        hrow = human[audit_id]
        human_label = norm_label(hrow["annotator_label"])
        text_row = text_features(batch[audit_id])
        old_records = [old_outputs[condition][audit_id] for condition, _, _ in OLD_WEAK_FILES]
        strict_records = [strict_outputs[condition][audit_id] for condition, _, _ in STRICT_EN_FILES]
        old_labels = [record["label"] for record in old_records]
        strict_labels = [record["label"] for record in strict_records]
        old_majority = make_majority_record(audit_id, "old_weak", "old_weak_5model_majority", old_records)
        strict_majority = make_majority_record(
            audit_id, "strict_independent_en", "strict_independent_en_5model_majority", strict_records
        )

        benchmark_label = norm_label(meta.get("gold_label"))
        pilot_qwen = norm_label(meta.get("qwen_majority"))
        pilot_glm = norm_label(meta.get("glm_majority"))
        pilot_combined = norm_label(meta.get("combined_majority"))
        main_condition_labels = {
            "benchmark": benchmark_label,
            "pilot_qwen": pilot_qwen,
            "pilot_glm": pilot_glm,
            "pilot_combined": pilot_combined,
            "old_weak_majority": old_majority["label"],
            "strict_en_majority": strict_majority["label"],
        }
        main_llm_labels = {
            key: value
            for key, value in main_condition_labels.items()
            if key != "benchmark"
        }
        cross_main_majority = majority(list(main_condition_labels.values()))
        cross_llm_majority = majority(list(main_llm_labels.values()))

        item: dict[str, Any] = {
            "audit_id": audit_id,
            "sample_id": meta.get("sample_id", ""),
            "dataset": meta.get("dataset", ""),
            "primary_stratum": meta.get("primary_stratum", ""),
            "candidate_strata": meta.get("candidate_strata", ""),
            "human_label": human_label,
            "human_confidence": hrow.get("annotator_confidence", ""),
            "human_issue_categories": hrow.get("issue_categories", ""),
            "human_notes": hrow.get("notes", ""),
            "risk_multi_combined": parse_float(meta.get("risk_multi_combined")) or 0.0,
            "risk_qwen_combined": parse_float(meta.get("risk_qwen_combined")) or 0.0,
            "risk_glm_combined": parse_float(meta.get("risk_glm_combined")) or 0.0,
            "per_task_binary_disagreement_rate": parse_float(meta.get("per_task_binary_disagreement_rate")) or 0.0,
            "model_majority_disagreement": parse_bool(meta.get("model_majority_disagreement")),
            "cross_main_majority_label": cross_main_majority,
            "cross_llm_majority_label": cross_llm_majority,
            "target_human_unfaithful": 1 if human_label == "unfaithful" else 0,
            "target_benchmark_mismatch": label_mismatch(benchmark_label, human_label),
            "target_pilot_qwen_wrong": label_mismatch(pilot_qwen, human_label),
            "target_pilot_glm_wrong": label_mismatch(pilot_glm, human_label),
            "target_pilot_combined_wrong_or_tie": label_mismatch(pilot_combined, human_label),
            "target_old_weak_majority_wrong_or_abstain": label_mismatch(old_majority["label"], human_label),
            "target_strict_en_majority_wrong": label_mismatch(strict_majority["label"], human_label),
        }
        item["target_any_main_llm_wrong"] = int(
            any(label_mismatch(label, human_label) for label in main_llm_labels.values())
        )
        item["target_old_or_strict_wrong"] = int(
            item["target_old_weak_majority_wrong_or_abstain"] or item["target_strict_en_majority_wrong"]
        )
        item.update(text_row)

        for name, label in main_condition_labels.items():
            add_label_onehots(item, name, label)
        add_pairwise_label_features(item, main_condition_labels)
        item.update(vote_stats(list(main_condition_labels.values()), "main_conditions"))
        item.update(vote_stats(list(main_llm_labels.values()), "main_llm_conditions"))
        item.update(vote_stats(old_labels, "old_weak"))
        item.update(vote_stats(strict_labels, "strict_en"))
        item.update(vote_stats(old_labels + strict_labels, "old_plus_strict_individual"))
        item.update(confidence_stats([record["confidence"] for record in old_records], "old_weak"))
        item.update(confidence_stats([record["confidence"] for record in strict_records], "strict_en"))
        item.update(
            confidence_stats(
                [record["confidence"] for record in old_records + strict_records],
                "old_plus_strict_individual",
            )
        )
        item.update(issue_stats([record["issue_categories"] for record in old_records], "old_weak"))
        item.update(issue_stats([record["issue_categories"] for record in strict_records], "strict_en"))
        item.update(
            issue_stats(
                [record["issue_categories"] for record in old_records + strict_records],
                "old_plus_strict_individual",
            )
        )
        item_rows.append(item)

        verdict_specs: list[dict[str, Any]] = [
            {
                "condition": "benchmark_reference",
                "model_name": "benchmark_reference",
                "protocol": "benchmark_reference",
                "condition_type": "reference",
                "label": benchmark_label,
                "confidence": None,
                "issue_categories": [],
            },
            {
                "condition": "pilot_qwen_majority",
                "model_name": "pilot_qwen_majority",
                "protocol": "pilot_original",
                "condition_type": "majority",
                "label": pilot_qwen,
                "confidence": None,
                "issue_categories": [],
            },
            {
                "condition": "pilot_glm_majority",
                "model_name": "pilot_glm_majority",
                "protocol": "pilot_original",
                "condition_type": "majority",
                "label": pilot_glm,
                "confidence": None,
                "issue_categories": [],
            },
            {
                "condition": "pilot_qwen_glm_combined_majority",
                "model_name": "pilot_qwen_glm_combined_majority",
                "protocol": "pilot_original",
                "condition_type": "majority",
                "label": pilot_combined,
                "confidence": None,
                "issue_categories": [],
            },
        ]
        for record in old_records:
            verdict_specs.append(
                {
                    "condition": record["condition"],
                    "model_name": record["model_name"],
                    "protocol": "old_weak",
                    "condition_type": "individual",
                    "label": record["label"],
                    "confidence": record["confidence"],
                    "issue_categories": record["issue_categories"],
                }
            )
        verdict_specs.append(old_majority)
        for record in strict_records:
            verdict_specs.append(
                {
                    "condition": record["condition"],
                    "model_name": record["model_name"],
                    "protocol": "strict_independent_en",
                    "condition_type": "individual",
                    "label": record["label"],
                    "confidence": record["confidence"],
                    "issue_categories": record["issue_categories"],
                }
            )
        verdict_specs.append(strict_majority)

        for spec in verdict_specs:
            label = norm_label(spec["label"])
            confidence = spec.get("confidence")
            cats = spec.get("issue_categories") or []
            verdict: dict[str, Any] = {
                "audit_id": audit_id,
                "verdict_id": f"{audit_id}::{spec['condition']}",
                "dataset": item["dataset"],
                "primary_stratum": item["primary_stratum"],
                "candidate_strata": item["candidate_strata"],
                "human_label": human_label,
                "condition": spec["condition"],
                "protocol": spec["protocol"],
                "condition_type": spec["condition_type"],
                "model_name": spec["model_name"],
                "verdict_label": label,
                "verdict_confidence": "" if confidence is None else confidence,
                "verdict_confidence_missing": 1 if confidence is None else 0,
                "verdict_high_confidence": 1 if confidence is not None and confidence >= 0.9 else 0,
                "verdict_issue_categories": "|".join(cats),
                "target_verdict_unreliable_strict": label_mismatch(label, human_label),
                "target_verdict_unreliable_covered": binary_mismatch_or_blank(label, human_label),
                "target_verdict_abstain_or_tie": 1 if label not in {"faithful", "unfaithful"} else 0,
                "target_verdict_high_confidence_wrong": 1
                if confidence is not None and confidence >= 0.9 and label_mismatch(label, human_label)
                else 0,
                "agrees_with_benchmark": 1 if label == benchmark_label else 0,
                "agrees_with_old_weak_majority": 1 if label == old_majority["label"] else 0,
                "agrees_with_strict_en_majority": 1 if label == strict_majority["label"] else 0,
                "agrees_with_cross_main_majority": 1 if label == cross_main_majority else 0,
                "agrees_with_cross_llm_majority": 1 if label == cross_llm_majority else 0,
                "cross_main_majority_label": cross_main_majority,
                "cross_llm_majority_label": cross_llm_majority,
                "protocol_old_weak_vote_margin": item["old_weak_vote_margin"],
                "protocol_strict_en_vote_margin": item["strict_en_vote_margin"],
                "protocol_old_weak_vote_entropy": item["old_weak_vote_entropy"],
                "protocol_strict_en_vote_entropy": item["strict_en_vote_entropy"],
                "main_condition_pairwise_disagreement_count": item[
                    "main_condition_pairwise_disagreement_count"
                ],
                "risk_multi_combined": item["risk_multi_combined"],
                "risk_qwen_combined": item["risk_qwen_combined"],
                "risk_glm_combined": item["risk_glm_combined"],
                "per_task_binary_disagreement_rate": item["per_task_binary_disagreement_rate"],
                "model_majority_disagreement": item["model_majority_disagreement"],
            }
            verdict.update(text_row)
            add_label_onehots(verdict, "verdict", label)
            verdict.update(issue_stats([cats], "verdict"))
            verdict_rows.append(verdict)

    write_csv(out_dir / "item_level_features.csv", item_rows)
    write_csv(out_dir / "verdict_level_features.csv", verdict_rows)

    summary = {
        "n_items": len(item_rows),
        "n_verdicts": len(verdict_rows),
        "item_targets": {
            key: sum(int(row.get(key, 0)) for row in item_rows)
            for key in [
                "target_human_unfaithful",
                "target_benchmark_mismatch",
                "target_any_main_llm_wrong",
                "target_old_or_strict_wrong",
                "target_strict_en_majority_wrong",
            ]
        },
        "verdict_targets": {
            "target_verdict_unreliable_strict": sum(
                int(row["target_verdict_unreliable_strict"]) for row in verdict_rows
            ),
            "target_verdict_unreliable_covered": sum(
                int(row["target_verdict_unreliable_covered"] or 0) for row in verdict_rows
            ),
            "target_verdict_abstain_or_tie": sum(int(row["target_verdict_abstain_or_tie"]) for row in verdict_rows),
            "target_verdict_high_confidence_wrong": sum(
                int(row["target_verdict_high_confidence_wrong"]) for row in verdict_rows
            ),
        },
        "n_verdicts_by_protocol": dict(Counter(row["protocol"] for row in verdict_rows)),
    }
    write_json(out_dir / "feature_table_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
