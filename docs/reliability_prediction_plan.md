# Reliability Prediction Plan

Date frozen: 2026-05-06

This document freezes the next experimental step under the canonical English-input protocol.

## 1. Goal

The goal is to evaluate whether a low-cost reliability layer can predict which RAG faithfulness judgments are unreliable relative to `HumanGold-v1`.

This is not a leaderboard of judge accuracy. The paper claim is:

> LLM-as-a-Judge verdicts for RAG faithfulness are policy- and evidence-condition dependent; a calibrated audit layer can prioritize unreliable verdicts and make automatic evaluation more transparent.

The reliability predictor should answer:

- Which items are likely to be human-unfaithful?
- Which benchmark/reference labels are likely to disagree with human audit?
- Which automatic judge verdicts are likely wrong?
- Which high-confidence or high-agreement verdicts still deserve audit?

## 2. Canonical Data

Use the canonical English-input setup from `docs/main_experiment_protocol.md`.

Inputs:

- Audit batch: `data/audit/human_audit_batch_100_blind.jsonl`
- Human gold: `data/audit/human_audit_annotations_en.csv`
- Metadata/risk scores: `data/audit/human_audit_batch_100_metadata.csv`

Canonical judge outputs:

- Pilot Qwen majority from the original perturbation run.
- Pilot GLM majority from the original perturbation run.
- Pilot Qwen+GLM combined majority.
- Old weak five-model outputs and majority.
- English strict independent five-model outputs and majority.

Assisted adjudication:

- Existing assisted outputs are internal pilot evidence only.
- They should not be used as main predictor features until rerun under the same canonical English-input protocol.
- They may be used only in appendix/sensitivity analysis with explicit caveat.

## 3. Prediction Tables

Build two tables.

### 3.1 Item-Level Table

One row per audit item.

Row count:

- 100 rows.

Purpose:

- Predict whether an item is risky or likely to contain unreliable automatic judgments.
- Useful for audit prioritization at the sample level.

Core columns:

- `audit_id`
- `dataset`
- `primary_stratum`
- `candidate_strata`
- `human_label`
- `human_confidence`
- `human_issue_categories`
- `benchmark_label`
- `pilot_qwen_majority`
- `pilot_glm_majority`
- `pilot_qwen_glm_combined_majority`
- `old_weak_5model_majority`
- `strict_independent_en_5model_majority`

### 3.2 Verdict-Level Table

One row per automatic verdict for an audit item.

Each automatic judge/condition produces one verdict row:

- Benchmark/reference label.
- Pilot Qwen majority.
- Pilot GLM majority.
- Pilot Qwen+GLM combined majority.
- Old weak individual model verdicts.
- Old weak five-model majority.
- English strict independent individual model verdicts.
- English strict independent five-model majority.

Purpose:

- Directly match the paper title: predicting unreliable verdicts.
- Gives more training/evaluation rows than the 100-item table.
- Allows verdict-specific features such as model family, protocol, confidence, abstention, and agreement margin.

Target:

```text
verdict_unreliable = predicted_label != human_label
```

For `tie` and `insufficient`, define two variants:

- strict variant: count as unreliable/non-matching for binary human gold.
- covered variant: evaluate only verdicts with `faithful` or `unfaithful`.

The strict variant is primary for audit planning; the covered variant is reported as a sensitivity check.

## 4. Targets

### 4.1 Primary Item-Level Targets

Use targets with enough positive examples for meaningful evaluation.

| Target | Definition | Current positives | Role |
| --- | --- | ---: | --- |
| `human_unfaithful` | `human_label == unfaithful` | 78/100 | Detect substantively problematic RAG answers |
| `benchmark_mismatch` | `benchmark_label != human_label` | 40/100 | Detect benchmark/reference policy mismatch |
| `any_main_llm_wrong` | Any main automatic LLM condition differs from human | 27/100 | Detect items likely to fool at least one judge |
| `old_or_strict_wrong` | Old weak majority or strict independent majority differs from human | 11/100 | Higher-quality judge failure target, but small |

Main item-level modeling should focus on `benchmark_mismatch` and `any_main_llm_wrong`.

`human_unfaithful` is useful but the audit batch is risk-enriched, so report it as audit-prioritization performance rather than population prevalence estimation.

### 4.2 Secondary Item-Level Targets

These have too few positives for stable supervised training, but are useful for ranking, top-k audit, and case studies.

| Target | Definition | Current positives | Role |
| --- | --- | ---: | --- |
| `strict_majority_wrong` | English strict majority differs from human | 4/100 | Case study/top-k only |
| `high_confidence_wrong` | High-confidence automatic verdict differs from human | TBD after feature build | Audit-risk analysis |
| `unanimous_but_wrong` | All models agree but majority differs from human | 2/100 for English strict | Case study only |

### 4.3 Primary Verdict-Level Target

| Target | Definition | Role |
| --- | --- | --- |
| `verdict_unreliable` | verdict label differs from human label | Main title-aligned prediction target |

Report separate results by protocol:

- benchmark/reference,
- pilot majority,
- old weak five-model,
- English strict independent five-model.

This matters because failure modes differ by protocol.

## 5. Feature Groups

All features must be available without using human labels, except when defining targets.

### 5.1 Metadata and Risk Features

From `human_audit_batch_100_metadata.csv`:

- `dataset`
- `primary_stratum`
- `candidate_strata`
- `risk_multi_combined`
- `risk_qwen_combined`
- `risk_glm_combined`
- `per_task_binary_disagreement_rate`
- `model_majority_disagreement`

These are core low-cost audit features.

### 5.2 Judge Label Features

For item-level prediction:

- one-hot labels for benchmark/reference, pilot Qwen, pilot GLM, combined pilot, old weak majority, strict independent majority,
- binary indicators for each condition predicting `faithful`, `unfaithful`, `tie`, or `insufficient`,
- pairwise disagreement indicators between judge conditions,
- number of conditions predicting `unfaithful`,
- number of conditions predicting `faithful`,
- entropy or vote margin across available conditions.

For verdict-level prediction:

- verdict label,
- protocol type,
- model name or condition name,
- model family,
- individual vs majority,
- abstention indicator,
- agreement with protocol majority,
- agreement with cross-protocol majority,
- protocol vote margin,
- cross-protocol disagreement count.

### 5.3 Confidence Features

Use model-provided confidence when available:

- raw confidence,
- mean confidence within protocol,
- min/max confidence within protocol,
- confidence gap between majority and dissenting models,
- high-confidence indicator, e.g. `confidence >= 0.9`.

Important caveat:

- Confidence is model-reported, not calibrated.
- It should be evaluated as a feature, not trusted.

### 5.4 Issue Category Features

Use automatic issue categories, not human issue categories, for prediction features.

Allowed sources:

- old weak individual issue categories,
- old weak majority issue union,
- English strict independent individual issue categories,
- English strict majority issue union.

Feature forms:

- one-hot category indicators,
- count per category across models,
- total number of issue categories,
- conflict/ambiguity bundle:
  - `entity_ambiguity`
  - `evidence_conflict`
  - `benchmark_ambiguous`
  - `temporal_conflict`
- unsupported/contradiction bundle:
  - `unsupported_claim`
  - `contradiction`
  - `numeric_error`
  - `over_specific_answer`

Do not use human issue categories as features; they are labels/analysis annotations.

### 5.5 Text-Derived Cheap Features

Optional CPU-only features:

- question length,
- answer length,
- number of evidence passages,
- total evidence length,
- answer-to-evidence lexical overlap,
- number of dates/numbers in answer,
- number of dates/numbers in evidence,
- whether answer contains a single short entity/date/number.

These are allowed because they do not require GPU or external model training.

## 6. Models

Use simple, low-cost, interpretable models first.

Baselines:

1. Random ranking.
2. Existing risk score only.
3. Model disagreement only.
4. Confidence only.
5. Issue-category count only.

Main predictors:

1. Logistic regression with L2 regularization.
2. Logistic regression with L1 regularization for sparse feature selection.
3. Shallow random forest or gradient boosting as a non-linear check.

Avoid complex neural models. The contribution is audit/calibration methodology, not large model training.

## 7. Evaluation Protocol

Because the audit set has only 100 items, evaluation must be conservative.

### 7.1 Cross-Validation

Use:

- leave-one-out cross-validation for item-level targets, or
- repeated stratified 5-fold cross-validation when the target has enough positives,
- grouped cross-validation by `audit_id` for verdict-level prediction so verdicts from the same item do not leak across train/test.

For verdict-level prediction, group by `audit_id` is mandatory.

### 7.2 Metrics

Report ranking and audit-efficiency metrics:

- AUROC,
- AUPRC,
- top-5/top-10/top-20 precision,
- lift over random audit,
- recall at fixed audit budget,
- calibration bins,
- Brier score,
- expected calibration error if stable enough.

For small-positive targets:

- report top-k precision and case studies,
- avoid overclaiming AUROC/AUPRC.

### 7.3 Confidence Intervals

Use bootstrap confidence intervals:

- item-level bootstrap by audit item,
- verdict-level grouped bootstrap by audit item.

Report 95% intervals for:

- AUROC,
- AUPRC,
- top-k precision,
- Brier score.

### 7.4 Ablations

Run feature ablations:

1. Risk scores only.
2. Disagreement only.
3. Confidence only.
4. Issue categories only.
5. Risk + disagreement.
6. Risk + disagreement + confidence.
7. All canonical features.

The paper needs to show which signals actually matter.

## 8. Expected Publishable Results

To support a CIKM submission, we need evidence like:

- reliability predictor improves top-k audit precision over random and risk-only baselines,
- model disagreement helps but is insufficient alone,
- issue categories improve conflict/ambiguity failure detection,
- confidence is miscalibrated or weak alone,
- combined features identify high-risk unreliable verdicts with meaningful lift,
- calibration curves show that predicted unreliability scores track empirical error rates.

Approximate target standards on this pilot:

- For `benchmark_mismatch`: AUROC >= 0.75 or top-20 precision >= 0.65 would be useful.
- For `any_main_llm_wrong`: AUROC >= 0.70 or top-20 precision >= 0.45 would be useful.
- For verdict-level `verdict_unreliable`: AUROC/AUPRC above risk-only and disagreement-only baselines, with clear top-k lift, would be publishable as pilot evidence.

These thresholds are not hard pass/fail rules. The final claim should be based on confidence intervals and ablations.

## 9. Negative Result Handling

If predictors fail to improve much:

- The paper can still report that current low-cost signals detect benchmark mismatch and human-unfaithful items but not high-quality strict judge failures.
- This would shift the contribution toward diagnostic auditing and policy-sensitive evaluation rather than fully automatic unreliability prediction.
- Do not overclaim if `strict_majority_wrong` remains too rare to model.

## 10. Outputs to Produce

Scripts:

- `scripts/build_reliability_prediction_tables.py`
- `scripts/run_reliability_prediction_experiments.py`

Tables:

- `data/audit/reliability/item_level_features.csv`
- `data/audit/reliability/verdict_level_features.csv`
- `data/audit/reliability/item_level_results.csv`
- `data/audit/reliability/verdict_level_results.csv`
- `data/audit/reliability/feature_ablation_results.csv`
- `data/audit/reliability/top_audit_cases.csv`
- `data/audit/reliability/calibration_bins.csv`

Freeze after running:

- `docs/freezes/YYYY-MM-DD_XX_reliability_prediction_results.md`

## 11. Decision

Proceed with reliability prediction, but under this scope:

- Main experiment: canonical English-input features only.
- Assisted signals: exclude from main predictor unless rerun under canonical protocol.
- Primary claims: audit prioritization and calibrated unreliability prediction, not perfect error detection.
- Main target: verdict-level unreliability plus item-level benchmark mismatch and any-main-LLM-wrong.
