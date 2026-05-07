# Freeze 16 - Human Audit Batch

Date: 2026-04-24

## Purpose

Prepare a blinded human audit batch to validate the benchmark/model-based findings.

The goal is to support or challenge the current conclusion:

> Reliability features can prioritize human audit and identify unreliable RAG judge verdicts, but benchmark labels may not always align with human judgment.

## Script

Audit batch generation script:

- `scripts/prepare_human_audit_batch.py`

Inputs:

- `data/pilot/pilot_samples.jsonl`
- `data/pilot/multi_judge_risk_qwen35plus_glm51_v2/multi_judge_risk_features.csv`
- `data/pilot/multi_judge_qwen35plus_glm51_v2/multi_judge_per_sample.csv`

Outputs:

- `data/audit/human_audit_batch_100_blind.csv`
- `data/audit/human_audit_batch_100_blind.jsonl`
- `data/audit/human_audit_batch_100_metadata.csv`
- `data/audit/human_audit_batch_100_selection_summary.json`

Annotation guide:

- `docs/audit_annotation_guidelines.md`

## Blinding

The blind annotation files include:

- audit id,
- question,
- answer,
- evidence,
- empty annotation fields.

They do not include:

- benchmark gold label,
- dataset name,
- model predictions,
- risk score,
- sampling stratum.

The metadata file contains those hidden fields and should be used only after annotation.

## Selection Strategy

The target batch size is 100 examples.

Priority-based strata:

1. `model_majority_disagreement`
2. `stable_shared_error`
3. `ramdocs_instability`
4. `top_multi_risk`
5. `low_risk_control`
6. `coverage_fill`

The strata are used for selection, but each example also records all candidate strata in metadata.

## Batch Composition

Final selection summary:

| Category | Count |
|---|---:|
| Total examples | 100 |
| Model-majority disagreement | 13 |
| Both models wrong by benchmark label | 27 |
| At least one model wrong by benchmark label | 40 |
| Combined majority wrong by benchmark label | 35 |

Primary stratum:

| Primary stratum | Count |
|---|---:|
| `model_majority_disagreement` | 13 |
| `stable_shared_error` | 22 |
| `ramdocs_instability` | 8 |
| `top_multi_risk` | 25 |
| `low_risk_control` | 20 |
| `coverage_fill` | 12 |

Dataset distribution, hidden from annotator:

| Dataset | Count |
|---|---:|
| RAGBench | 46 |
| RAMDocs | 38 |
| RAGTruth | 16 |

Benchmark label distribution, hidden from annotator:

| Benchmark label | Count |
|---|---:|
| faithful | 56 |
| unfaithful | 44 |

## Intended Analyses After Annotation

After annotation, compare human labels against:

1. benchmark labels,
2. Qwen majority verdict,
3. GLM majority verdict,
4. combined majority verdict,
5. risk strata.

Primary audit questions:

- Do high-risk examples have higher human-confirmed error rates?
- Are stable shared errors true judge failures or benchmark/label ambiguity?
- Are RAMDocs instability cases genuinely conflict-driven?
- Do low-risk controls have high agreement with human labels?

## Scientific Caveat

This is a risk-enriched audit batch, not a representative random sample.

It is suitable for:

- validating error mechanisms,
- measuring top-risk precision,
- qualitative analysis,
- checking benchmark/model disagreement.

It is not suitable by itself for:

- unbiased estimation of overall judge accuracy.

For unbiased population estimates, use random or stratified-proportional audit designs from Freeze 12.

