#!/usr/bin/env python3
"""Build qualitative case-study artifacts for the reliability paper."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd


CASE_SPECS = [
    {
        "audit_id": "AUDIT-018",
        "case_group": "Entity/title ambiguity",
        "phenomenon": "A judge accepts one plausible title interpretation as certain.",
        "why_selected": "Top-ranked unreliable verdict; human gold marks the answer unfaithful because several songs titled 'Shy Boy' appear in evidence.",
        "preferred_target": "target_verdict_unreliable_strict",
        "paper_use": "Benchmark and weak-judge over-certainty under title ambiguity.",
    },
    {
        "audit_id": "AUDIT-024",
        "case_group": "Entity/title ambiguity",
        "phenomenon": "A benchmark/reference label treats a partially supported answer as faithful despite multiple works with the same title.",
        "why_selected": "Top unreliable benchmark/reference verdict; useful for the policy-misalignment argument.",
        "preferred_target": "target_verdict_unreliable_strict",
        "paper_use": "Benchmark mismatch caused by unresolved media/title ambiguity.",
    },
    {
        "audit_id": "AUDIT-030",
        "case_group": "Entity/person ambiguity",
        "phenomenon": "A judge chooses one person among multiple people sharing the queried name.",
        "why_selected": "High-scoring unreliable benchmark/reference verdict; human note identifies footballer/cricketer ambiguity.",
        "preferred_target": "target_verdict_unreliable_strict",
        "paper_use": "Name ambiguity where evidence supports multiple entities.",
    },
    {
        "audit_id": "AUDIT-020",
        "case_group": "Insufficient or weakly linked evidence",
        "phenomenon": "Evidence contains demographic facts but does not clearly link them to the queried location.",
        "why_selected": "High-scoring unreliable benchmark/reference verdict; illustrates unsupported inference rather than simple contradiction.",
        "preferred_target": "target_verdict_unreliable_strict",
        "paper_use": "Insufficient evidence despite superficially relevant snippets.",
    },
    {
        "audit_id": "AUDIT-061",
        "case_group": "Evidence conflict",
        "phenomenon": "Evidence directly conflicts about the base location of the entity.",
        "why_selected": "Human issue categories include contradiction and evidence conflict; model confidence can still be high.",
        "preferred_target": "target_verdict_high_confidence_wrong",
        "paper_use": "Conflict case for auditing confident automatic verdicts.",
    },
    {
        "audit_id": "AUDIT-065",
        "case_group": "Temporal/evidence conflict",
        "phenomenon": "Evidence conflicts on when a player first represented Papua New Guinea.",
        "why_selected": "Human note identifies conflicting dates; useful to show temporal conflict beyond entity ambiguity.",
        "preferred_target": "target_human_unfaithful",
        "paper_use": "Temporal conflict case.",
    },
    {
        "audit_id": "AUDIT-050",
        "case_group": "Unsupported specificity",
        "phenomenon": "Answer confuses first transatlantic flight with first nonstop flight.",
        "why_selected": "Human issue categories include unsupported claim and answer-format issue; benchmark/reference label disagrees with human gold.",
        "preferred_target": "target_human_unfaithful",
        "paper_use": "Claim-level over-specificity under near-matching evidence.",
    },
    {
        "audit_id": "AUDIT-075",
        "case_group": "Insufficient evidence in table context",
        "phenomenon": "Answer requires table values that are not visible in the truncated evidence.",
        "why_selected": "Human issue categories include unsupported claim and insufficient evidence; shows failure on structured/table-like evidence.",
        "preferred_target": "target_human_unfaithful",
        "paper_use": "Table truncation / missing-evidence case.",
    },
    {
        "audit_id": "AUDIT-089",
        "case_group": "Numeric error",
        "phenomenon": "Answer makes an unsupported projection from operating-profit values.",
        "why_selected": "Human issue categories include numeric error and unsupported claim; useful as a non-ambiguity failure type.",
        "preferred_target": "target_human_unfaithful",
        "paper_use": "Numeric/calculation failure case.",
    },
    {
        "audit_id": "AUDIT-040",
        "case_group": "False alarm / abstention failure",
        "phenomenon": "Human gold says the answer is faithful, but some automatic verdicts abstain or mark it unfaithful.",
        "why_selected": "Strict majority is wrong and a high-confidence weak verdict is wrong; shows the audit layer must support review rather than automatic rejection.",
        "preferred_target": "target_verdict_high_confidence_wrong",
        "paper_use": "False-positive case for qualitative balance.",
    },
    {
        "audit_id": "AUDIT-009",
        "case_group": "False alarm / policy boundary",
        "phenomenon": "Human gold and benchmark/reference agree, while the strict majority is unfaithful.",
        "why_selected": "One of only four strict-majority-wrong items; useful as a caution against overclaiming strict prompts.",
        "preferred_target": "target_strict_en_majority_wrong",
        "paper_use": "Strict-prompt false alarm.",
    },
]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, max_chars: int = 420) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            obj = json.loads(line)
            records[obj["audit_id"]] = obj
    return records


def series_to_dict(row: pd.Series | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: clean_text(value) for key, value in row.to_dict().items()}


def select_top_case(top_df: pd.DataFrame, audit_id: str, preferred_target: str) -> pd.Series | None:
    sub = top_df[top_df["audit_id"] == audit_id].copy()
    if preferred_target:
        target_sub = sub[sub["target"] == preferred_target].copy()
        if not target_sub.empty:
            sub = target_sub
    if sub.empty:
        return None
    sub["score_num"] = pd.to_numeric(sub["score"], errors="coerce").fillna(-1)
    sub["rank_num"] = pd.to_numeric(sub["rank"], errors="coerce").fillna(10**9)
    sub = sub.sort_values(["score_num", "rank_num"], ascending=[False, True])
    return sub.iloc[0]


def build_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    audit_records = read_jsonl(args.audit_batch)
    item_df = pd.read_csv(args.item_features)
    top_df = pd.read_csv(args.top_cases)

    items = {row["audit_id"]: row for _, row in item_df.iterrows()}
    rows = []
    for spec in CASE_SPECS:
        audit_id = spec["audit_id"]
        item = series_to_dict(items.get(audit_id))
        audit = audit_records.get(audit_id, {})
        selected = series_to_dict(select_top_case(top_df, audit_id, spec.get("preferred_target", "")))
        evidence = audit.get("evidence", []) or []

        row = {
            "audit_id": audit_id,
            "case_group": spec["case_group"],
            "phenomenon": spec["phenomenon"],
            "why_selected": spec["why_selected"],
            "paper_use": spec["paper_use"],
            "dataset": item.get("dataset", ""),
            "primary_stratum": item.get("primary_stratum", ""),
            "question": clean_text(audit.get("question", "")),
            "answer": clean_text(audit.get("answer", "")),
            "human_label": item.get("human_label", ""),
            "human_confidence": item.get("human_confidence", ""),
            "human_issue_categories": item.get("human_issue_categories", ""),
            "human_notes": item.get("human_notes", ""),
            "benchmark_label": item.get("benchmark_label", ""),
            "old_weak_majority_label": item.get("old_weak_majority_label", ""),
            "strict_en_majority_label": item.get("strict_en_majority_label", ""),
            "target_benchmark_mismatch": item.get("target_benchmark_mismatch", ""),
            "target_any_main_llm_wrong": item.get("target_any_main_llm_wrong", ""),
            "target_strict_en_majority_wrong": item.get("target_strict_en_majority_wrong", ""),
            "risk_multi_combined": item.get("risk_multi_combined", ""),
            "main_conditions_vote_entropy": item.get("main_conditions_vote_entropy", ""),
            "old_weak_vote_entropy": item.get("old_weak_vote_entropy", ""),
            "strict_en_vote_entropy": item.get("strict_en_vote_entropy", ""),
            "old_plus_strict_individual_issue_conflict_ambiguity_bundle": item.get(
                "old_plus_strict_individual_issue_conflict_ambiguity_bundle", ""
            ),
            "old_plus_strict_individual_issue_unsupported_contradiction_bundle": item.get(
                "old_plus_strict_individual_issue_unsupported_contradiction_bundle", ""
            ),
            "selected_top_case_target": selected.get("target", ""),
            "selected_top_case_rank": selected.get("rank", ""),
            "selected_top_case_score": selected.get("score", ""),
            "selected_top_case_y_true": selected.get("y_true", ""),
            "selected_verdict_condition": selected.get("condition", ""),
            "selected_verdict_protocol": selected.get("protocol", ""),
            "selected_verdict_label": selected.get("verdict_label", ""),
        }
        for idx, ev in enumerate(evidence[:3], start=1):
            row[f"evidence_excerpt_{idx}"] = truncate(f"[{ev.get('doc_id', idx)}] {ev.get('text', '')}")
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Qualitative Case Studies",
        "",
        "These cases are selected from the canonical English-input reliability outputs. Assisted adjudication is not used.",
        "",
        "## Overview",
        "",
        "| Case | Group | Human | Benchmark | Old weak maj. | Strict maj. | Selected unreliable-score row | Paper use |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        selected = (
            f"{row['selected_top_case_target']} / {row['selected_verdict_condition']} "
            f"/ label={row['selected_verdict_label']} / score={row['selected_top_case_score']}"
        )
        lines.append(
            "| {audit_id} | {case_group} | {human_label} | {benchmark_label} | {old_weak_majority_label} | "
            "{strict_en_majority_label} | {selected} | {paper_use} |".format(
                selected=clean_text(selected).replace("|", "\\|"),
                **{key: clean_text(value).replace("|", "\\|") for key, value in row.items()},
            )
        )
    lines.extend(["", "## Detailed Notes", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row['audit_id']}: {row['case_group']}",
                "",
                f"- Phenomenon: {row['phenomenon']}",
                f"- Why selected: {row['why_selected']}",
                f"- Question: {row['question']}",
                f"- Answer: {row['answer']}",
                f"- Human gold: {row['human_label']} ({row['human_issue_categories']})",
                f"- Human rationale: {row['human_notes']}",
                (
                    f"- Audit signal: benchmark={row['benchmark_label']}, old weak majority={row['old_weak_majority_label']}, "
                    f"strict majority={row['strict_en_majority_label']}, selected score={row['selected_top_case_score']}"
                ),
                f"- Evidence excerpt 1: {row.get('evidence_excerpt_1', '')}",
                f"- Evidence excerpt 2: {row.get('evidence_excerpt_2', '')}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    groups: dict[str, int] = {}
    labels: dict[str, int] = {}
    for row in rows:
        groups[row["case_group"]] = groups.get(row["case_group"], 0) + 1
        labels[row["human_label"]] = labels.get(row["human_label"], 0) + 1
    summary = {
        "n_cases": len(rows),
        "case_groups": groups,
        "human_label_counts": labels,
        "artifact_note": "Case studies are for qualitative analysis and paper writing; they are not additional evaluation metrics.",
    }
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-batch", type=Path, default=Path("data/audit/human_audit_batch_100_blind.jsonl"))
    parser.add_argument("--item-features", type=Path, default=Path("data/audit/reliability/item_level_features.csv"))
    parser.add_argument("--top-cases", type=Path, default=Path("data/audit/reliability/top_audit_cases.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/audit/reliability/qualitative"))
    args = parser.parse_args()

    rows = build_rows(args)
    write_csv(args.out_dir / "qualitative_case_studies.csv", rows)
    write_markdown(args.out_dir / "qualitative_case_studies.md", rows)
    write_summary(args.out_dir / "qualitative_case_summary.json", rows)
    print(json.dumps({"n_cases": len(rows), "out_dir": str(args.out_dir)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
