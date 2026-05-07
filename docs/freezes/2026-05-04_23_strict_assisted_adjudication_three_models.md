# Freeze 23: Strict Assisted Adjudication with Three Models

Date: 2026-05-04

## Purpose

Run a stricter assisted adjudication round using three models:

- `deepseek-v4-pro`
- `qwen3.5-plus-2026-04-20`
- `qwen3.6-max-preview`

Unlike the earlier weak-label runs, this round explicitly includes:

- the frozen human annotation definitions,
- the Chinese translated audit item,
- the five previous AI labels,
- the five previous AI issue categories,
- the five previous AI reasons translated into Chinese.

The goal is to see what happens when stronger prompt alignment forces adjudicators to apply the frozen strict definition of faithfulness.

## Important Caveat

This is not an independent human audit and not an independent model-only baseline.

It is an **LLM-assisted adjudication** setting because the models receive previous AI judgments and reasons. It should be analyzed separately from:

- blind weak labels,
- human labels,
- independent human audit.

The active human annotation files were not modified. At the time of this freeze, `data/audit/human_audit_annotations.jsonl` had 36 rows.

## Scripts

New scripts:

- `scripts/run_assisted_adjudication_labels.py`
- `scripts/compare_assisted_adjudication_labels.py`

Both scripts passed compilation.

## Prompt Policy

The adjudication prompt explicitly states:

- `faithful`: every important answer claim is supported by evidence, and the answer does not ignore important conflict or ambiguity.
- `unfaithful`: contradiction, unsupported important facts, selecting one side of conflict/ambiguity without support, wrong entity/date/number, or presenting uncertainty as certainty when evidence is conflicting or incomplete.
- `insufficient`: evidence itself is not enough to decide faithful vs unfaithful. Use sparingly; if the answer makes unsupported claims, prefer `unfaithful`.

It also emphasizes:

- A single supporting passage is not enough for `faithful` if other evidence creates clear entity ambiguity, multiple candidate answers, or conflict.
- If the answer gives a definite conclusion without handling such ambiguity/conflict, prefer `unfaithful`.
- The five AI opinions are reference material only; the adjudicator must apply the frozen definitions.

## Inputs

- Chinese audit batch: `data/audit/human_audit_batch_100_blind_zh.jsonl`
- Five-model translated reasons: `data/audit/ai_weak_reviews_5models_zh.json`
- Five-model issue suggestions: `data/audit/ai_issue_category_suggestions_5models.json`
- Previous five-model comparison: `data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv`

## Outputs

Per-model outputs:

- `data/audit/assisted_adjudication_deepseekv4pro.jsonl`
- `data/audit/assisted_adjudication_deepseekv4pro.csv`
- `data/audit/assisted_adjudication_qwen35plus20260420.jsonl`
- `data/audit/assisted_adjudication_qwen35plus20260420.csv`
- `data/audit/assisted_adjudication_qwen36maxpreview.jsonl`
- `data/audit/assisted_adjudication_qwen36maxpreview.csv`

Comparison outputs:

- `data/audit/assisted_adjudication_comparison_3models/assisted_adjudication_summary.json`
- `data/audit/assisted_adjudication_comparison_3models/assisted_adjudication_by_item.csv`
- `data/audit/assisted_adjudication_comparison_3models/assisted_adjudication_pairwise.csv`

Smoke outputs were also generated separately with `_smoke` suffix.

## Run Status

All three full runs completed:

| Model | Items | Failures |
|---|---:|---:|
| `deepseek-v4-pro` | 100 | 0 |
| `qwen3.5-plus-2026-04-20` | 100 | 0 |
| `qwen3.6-max-preview` | 100 | 0 |

## Label Summary

| Model | Faithful | Unfaithful | Insufficient |
|---|---:|---:|---:|
| `deepseek-v4-pro` | 18 | 82 | 0 |
| `qwen3.5-plus-2026-04-20` | 18 | 82 | 0 |
| `qwen3.6-max-preview` | 19 | 81 | 0 |

Three-model majority:

- `unfaithful`: 81
- `faithful`: 19
- `insufficient`: 0

## Agreement

Pairwise agreement:

| Pair | Agreement | Cohen kappa |
|---|---:|---:|
| DeepSeek vs Qwen3.5 Plus | 0.98 | 0.932 |
| DeepSeek vs Qwen3.6 Max | 0.99 | 0.967 |
| Qwen3.5 Plus vs Qwen3.6 Max | 0.99 | 0.967 |

Three-model unanimous agreement:

- 98/100
- rate: 0.98

## Change from Previous Five-Model Majority

Compared with the earlier five-model weak-label majority:

- 9/100 items changed majority label.
- Most important examples include ambiguity/conflict cases where the earlier five-model majority was `faithful`, `insufficient`, or tie, but the strict adjudication majority became `unfaithful`.

Examples:

- `AUDIT-003`: previous majority `faithful`, strict assisted majority `unfaithful`.
- `AUDIT-036`: previous majority tie, strict assisted majority `unfaithful`.
- `AUDIT-070`: previous majority `faithful`, strict assisted majority `unfaithful`.

## Interpretation

This round shows that explicit frozen-policy prompting strongly changes model behavior:

1. The adjudicators become much more consistent.
2. The adjudicators become much stricter about entity ambiguity and evidence conflict.
3. `insufficient` almost disappears because the frozen guideline says to use it sparingly and prefer `unfaithful` when the answer makes an unsupported or over-certain claim.

This supports the paper's core argument that LLM judge verdicts are policy-sensitive. A judge may understand the evidence but still produce different labels depending on whether the prompt defines faithfulness as:

- narrow support by at least one passage, or
- strict support under ambiguity/conflict.

## Scientific Use

Use this round as:

- evidence for prompt-policy sensitivity,
- an assisted adjudication baseline,
- a source of candidate rationales for case studies,
- a comparison point against human annotation.

Do not use it as:

- independent human ground truth,
- unbiased judge accuracy,
- blind model-only evaluation.

