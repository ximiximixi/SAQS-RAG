# Freeze 25: Strict-Assisted V2 from Strict Five-Model References

Date: 2026-05-04

## Purpose

Run a second assisted adjudication round with three models, this time using the newly generated strict independent five-model labels and notes as the reference material.

This differs from Freeze 23:

- Freeze 23 used the earlier five-model weak labels and reasons as references.
- Freeze 25 uses the strict independent five-model rerun from Freeze 24 as references.

The goal is to test whether adjudication becomes more stable or stricter after the reference opinions themselves are policy-aligned.

## Models

Adjudicator models:

- `deepseek-v4-pro`
- `qwen3.5-plus-2026-04-20`
- `qwen3.6-max-preview`

Reference models:

- `qwen3.6-max-preview`
- `deepseek-v4-pro`
- `kimi-k2.6`
- `qwen3-max-2026-01-23`
- `qwen3.6-plus-2026-04-02`

All calls used the existing OpenAI-compatible endpoint configured in `.env`, with thinking disabled.

## Prompt Policy

The adjudication prompt remains the strict frozen-policy prompt:

- `faithful`: every important answer claim is supported by evidence, and the answer does not ignore important conflict or ambiguity.
- `unfaithful`: contradiction, unsupported important facts, selecting one side of conflict/ambiguity without support, wrong entity/date/number, or presenting uncertainty as certainty when evidence is conflicting or incomplete.
- `insufficient`: evidence itself is not enough to decide faithful vs unfaithful. Use sparingly; if the answer makes an unsupported or over-certain claim, prefer `unfaithful`.

The prompt also states:

- A single supporting passage is not enough for `faithful` if other evidence creates entity ambiguity, multiple plausible answers, or conflict.
- If the answer gives a definite conclusion without handling such ambiguity/conflict, usually mark `unfaithful`.
- AI reference opinions are only references; the adjudicator must still make its own final decision under the frozen definition.

## Scripts

New script:

- `scripts/build_strict_reference_reviews.py`
- `scripts/compare_audit_condition_majorities.py`

Reused scripts:

- `scripts/run_assisted_adjudication_labels.py`
- `scripts/compare_assisted_adjudication_labels.py`

Patch:

- `scripts/compare_assisted_adjudication_labels.py` was updated to recognize `strict_majority_label` and `strict_label_vote_counts` when using strict-five outputs as the previous/reference condition.

All relevant scripts passed compilation.

## Inputs

Strict five-model references:

- `data/audit/strict_independent_qwen36maxpreview.csv`
- `data/audit/strict_independent_deepseekv4pro.csv`
- `data/audit/strict_independent_kimik26.csv`
- `data/audit/strict_independent_qwen3max20260123.csv`
- `data/audit/strict_independent_qwen36plus20260402.csv`

Generated reference files:

- `data/audit/strict_independent_reference_reviews_5models.json`
- `data/audit/strict_independent_reference_reviews_5models.csv`
- `data/audit/strict_independent_issue_suggestions_5models.json`
- `data/audit/strict_independent_issue_suggestions_5models.csv`

Audit batch:

- `data/audit/human_audit_batch_100_blind_zh.jsonl`

## Outputs

Per-adjudicator outputs:

- `data/audit/strict_assisted_v2_deepseekv4pro.jsonl`
- `data/audit/strict_assisted_v2_deepseekv4pro.csv`
- `data/audit/strict_assisted_v2_qwen35plus20260420.jsonl`
- `data/audit/strict_assisted_v2_qwen35plus20260420.csv`
- `data/audit/strict_assisted_v2_qwen36maxpreview.jsonl`
- `data/audit/strict_assisted_v2_qwen36maxpreview.csv`

Three-model comparison:

- `data/audit/strict_assisted_v2_comparison_3models/assisted_adjudication_summary.json`
- `data/audit/strict_assisted_v2_comparison_3models/assisted_adjudication_by_item.csv`
- `data/audit/strict_assisted_v2_comparison_3models/assisted_adjudication_pairwise.csv`

Condition-level comparison:

- `data/audit/audit_condition_majority_comparison/condition_majorities_summary.json`
- `data/audit/audit_condition_majority_comparison/condition_majorities_by_item.csv`

## Run Status

All three full adjudication runs completed:

| Model | Items | Failures |
|---|---:|---:|
| `deepseek-v4-pro` | 100 | 0 |
| `qwen3.5-plus-2026-04-20` | 100 | 0 |
| `qwen3.6-max-preview` | 100 | 0 |

At the time of this freeze, active human annotations had 45 rows. They were not modified by this run.

## Label Summary

| Model | Faithful | Unfaithful | Insufficient |
|---|---:|---:|---:|
| `deepseek-v4-pro` | 11 | 89 | 0 |
| `qwen3.5-plus-2026-04-20` | 16 | 84 | 0 |
| `qwen3.6-max-preview` | 15 | 85 | 0 |

Three-model majority:

- `unfaithful`: 85
- `faithful`: 15
- `insufficient`: 0

## Agreement

Pairwise agreement:

| Pair | Agreement | Cohen kappa |
|---|---:|---:|
| DeepSeek vs Qwen3.5 Plus | 0.95 | 0.787 |
| DeepSeek vs Qwen3.6 Max | 0.96 | 0.824 |
| Qwen3.5 Plus vs Qwen3.6 Max | 0.99 | 0.962 |

Three-model unanimous agreement:

- 95/100
- rate: 0.95

## Comparison Across Conditions

Four condition majorities:

| Condition | Faithful | Unfaithful | Insufficient | Tie |
|---|---:|---:|---:|---:|
| Old five-model weak labels | 23 | 72 | 2 | 3 |
| Strict independent five-model labels | 20 | 80 | 0 | 0 |
| Assisted V1 from old five-model references | 19 | 81 | 0 | 0 |
| Assisted V2 from strict five-model references | 15 | 85 | 0 | 0 |

Pairwise changes:

| Comparison | Different items |
|---|---:|
| Old five vs strict five | 16 |
| Old five vs assisted V1 | 9 |
| Old five vs assisted V2 | 13 |
| Strict five vs assisted V1 | 9 |
| Strict five vs assisted V2 | 9 |
| Assisted V1 vs assisted V2 | 4 |

Items changed from assisted V1 to assisted V2:

- `AUDIT-029`: V1 `faithful`, V2 `unfaithful`
- `AUDIT-073`: V1 `faithful`, V2 `unfaithful`
- `AUDIT-081`: V1 `faithful`, V2 `unfaithful`
- `AUDIT-095`: V1 `faithful`, V2 `unfaithful`

## Interpretation

This round shows:

1. Once the reference opinions are themselves strict-policy aligned, assisted adjudication becomes slightly stricter.
2. Assisted V2 is close to strict independent five-model majority but not identical: 9/100 items differ.
3. Assisted V1 and V2 differ on only 4/100 items, which suggests the strict frozen prompt is the dominant intervention, while reference-source quality is a secondary intervention.
4. `insufficient` remains absent because the frozen policy tells models to use it sparingly and prefer `unfaithful` when an answer makes an unsupported or over-certain claim.

## Scientific Use

Use this as:

- strict assisted adjudication with policy-aligned references,
- a comparison against strict independent judging,
- a comparison against old weak labels,
- a source of high-consensus rationales for case studies.

Do not use this as:

- independent human ground truth,
- unbiased judge accuracy estimate,
- a replacement for human audit.

