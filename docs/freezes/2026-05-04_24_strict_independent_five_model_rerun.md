# Freeze 24: Strict Independent Five-Model Rerun

Date: 2026-05-04

## Purpose

Rerun the previous five audit models with the strict frozen faithfulness policy, but without giving them any previous AI labels, AI reasons, or AI issue suggestions.

This isolates the effect of prompt-policy clarification from the effect of assisted adjudication.

## Models

- `qwen3.6-max-preview`
- `deepseek-v4-pro`
- `kimi-k2.6`
- `qwen3-max-2026-01-23`
- `qwen3.6-plus-2026-04-02`

All used the existing OpenAI-compatible API endpoint configured in `.env`, with thinking disabled.

## Key Difference from Earlier Runs

Earlier five-model weak labels used a simpler prompt:

- `faithful`: answer claims are supported by evidence.
- `unfaithful`: answer contradicts evidence or adds unsupported facts.
- `insufficient`: evidence is not enough to judge.

The strict independent prompt additionally made the frozen boundary conditions explicit:

- A single supporting passage is not enough for `faithful` if other evidence creates clear entity ambiguity, multiple plausible answers, or conflict.
- If the answer gives a definite conclusion without handling such ambiguity/conflict, usually mark `unfaithful`.
- `insufficient` should be used sparingly; if the answer makes an unsupported or over-certain claim, prefer `unfaithful`.

Unlike Freeze 23 assisted adjudication, this run did not provide:

- previous five-model votes,
- previous model reasons,
- previous issue category suggestions.

## Scripts

New scripts:

- `scripts/run_strict_independent_judge_labels.py`
- `scripts/compare_strict_independent_judge_labels.py`

Both passed compilation.

## Inputs

- `data/audit/human_audit_batch_100_blind_zh.jsonl`
- `data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv` for comparison only
- `data/audit/assisted_adjudication_comparison_3models/assisted_adjudication_by_item.csv` for comparison only
- `data/audit/human_audit_batch_100_metadata.csv` for stratified comparison only

The strict judge calls themselves only received the audit item and strict policy.

## Outputs

Per-model outputs:

- `data/audit/strict_independent_qwen36maxpreview.jsonl`
- `data/audit/strict_independent_qwen36maxpreview.csv`
- `data/audit/strict_independent_deepseekv4pro.jsonl`
- `data/audit/strict_independent_deepseekv4pro.csv`
- `data/audit/strict_independent_kimik26.jsonl`
- `data/audit/strict_independent_kimik26.csv`
- `data/audit/strict_independent_qwen3max20260123.jsonl`
- `data/audit/strict_independent_qwen3max20260123.csv`
- `data/audit/strict_independent_qwen36plus20260402.jsonl`
- `data/audit/strict_independent_qwen36plus20260402.csv`

Comparison outputs:

- `data/audit/strict_independent_comparison_5models/strict_independent_summary.json`
- `data/audit/strict_independent_comparison_5models/strict_independent_by_item.csv`
- `data/audit/strict_independent_comparison_5models/strict_independent_pairwise.csv`

Smoke outputs were also generated with `_smoke` suffix.

## Run Status

All five full runs completed:

| Model | Items | Failures |
|---|---:|---:|
| `qwen3.6-max-preview` | 100 | 0 |
| `deepseek-v4-pro` | 100 | 0 |
| `kimi-k2.6` | 100 | 0 |
| `qwen3-max-2026-01-23` | 100 | 0 |
| `qwen3.6-plus-2026-04-02` | 100 | 0 |

## Label Summary

| Model | Faithful | Unfaithful | Insufficient |
|---|---:|---:|---:|
| `qwen3.6-max-preview` | 18 | 82 | 0 |
| `deepseek-v4-pro` | 19 | 81 | 0 |
| `kimi-k2.6` | 11 | 89 | 0 |
| `qwen3-max-2026-01-23` | 24 | 76 | 0 |
| `qwen3.6-plus-2026-04-02` | 23 | 77 | 0 |

Strict five-model majority:

- `unfaithful`: 80
- `faithful`: 20
- `insufficient`: 0

## Agreement

Five-model unanimous agreement:

- 76/100
- rate: 0.76

Pairwise exact agreement ranged from 0.83 to 0.92.

Strongest pair:

- `qwen3.6-max-preview` vs `qwen3-max-2026-01-23`: 0.92
- `qwen3-max-2026-01-23` vs `qwen3.6-plus-2026-04-02`: 0.91

Weakest pair:

- `kimi-k2.6` vs `qwen3-max-2026-01-23`: 0.83

## Comparison Against Earlier Five-Model Weak Labels

Compared with the earlier five-model weak-label majority:

- 16/100 items changed majority label.
- Change rate: 0.16.

Examples of changed items:

- `AUDIT-003`: old majority `faithful`, strict majority `unfaithful`.
- `AUDIT-036`: old majority tie, strict majority `unfaithful`.
- `AUDIT-040`: old majority `faithful`, strict majority `unfaithful`.
- `AUDIT-071`, `AUDIT-072`, `AUDIT-081`: old majority `faithful`, strict majority `unfaithful`.

This shows that policy clarification alone changes model verdicts.

## Comparison Against Assisted Three-Model Adjudication

Compared with the assisted three-model adjudication majority from Freeze 23:

- 9/100 items changed majority label.
- Change rate: 0.09.

This means the assisted setting is similar to the strict independent setting, but not identical. Providing prior model rationales can still shift some decisions.

## Stratified Results

By dataset:

| Dataset | n | Strict majority faithful | Strict majority unfaithful | Unanimous rate | Changed from old five-model |
|---|---:|---:|---:|---:|---:|
| RAGBench | 46 | 16 | 30 | 0.696 | 0.196 |
| RAGTruth | 16 | 3 | 13 | 0.500 | 0.000 |
| RAMDocs | 38 | 1 | 37 | 0.947 | 0.184 |

By primary stratum:

| Stratum | n | Strict majority faithful | Strict majority unfaithful | Unanimous rate | Changed from old five-model |
|---|---:|---:|---:|---:|---:|
| `coverage_fill` | 12 | 1 | 11 | 0.833 | 0.000 |
| `low_risk_control` | 20 | 12 | 8 | 0.550 | 0.150 |
| `model_majority_disagreement` | 13 | 0 | 13 | 0.615 | 0.077 |
| `ramdocs_instability` | 8 | 0 | 8 | 0.875 | 0.250 |
| `stable_shared_error` | 22 | 4 | 18 | 0.818 | 0.409 |
| `top_multi_risk` | 25 | 3 | 22 | 0.880 | 0.040 |

`stable_shared_error` has the largest change rate from the old five-model prompt, which supports the hypothesis that many stable shared errors are tied to ambiguous or underspecified evaluation policy.

## Interpretation

This rerun strengthens the paper's methodological story:

1. The earlier five-model prompt was useful for weak labeling and disagreement discovery, but it was not strict enough to enforce the frozen policy.
2. Explicit conflict/ambiguity policy makes judges more strict and eliminates nearly all `insufficient` labels.
3. Strict independent rerun and assisted adjudication are close but not identical, proving that prior AI rationales are an additional intervention.
4. Judge verdicts are not only model-dependent; they are also policy-prompt-dependent.

## Scientific Use

Use this as:

- the strict independent judge condition,
- a prompt-policy sensitivity experiment,
- a comparison against earlier weak labels,
- a comparison against assisted adjudication,
- a comparison against human annotations after they are complete.

Do not use this as:

- independent human ground truth,
- unbiased population accuracy estimate.

## Caveat

Smoke-test notes showed that some model rationales may include minor external-knowledge-like wording, even though the prompt forbids outside knowledge. The labels and most rationales are still driven by evidence ambiguity/conflict, but this should be noted as a residual limitation of LLM rationales.
