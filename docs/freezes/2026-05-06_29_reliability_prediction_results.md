# Freeze 29: Reliability Prediction Results

Date: 2026-05-06

This freeze records the first canonical reliability prediction experiment.

## Protocol

Canonical setup:

- Audit batch: `data/audit/human_audit_batch_100_blind.jsonl`
- Human gold: `data/audit/human_audit_annotations_en.csv`
- Main protocol: `docs/main_experiment_protocol.md`
- Prediction plan: `docs/reliability_prediction_plan.md`
- Assisted adjudication is excluded from main predictor features.

Runtime:

- Bundled workspace Python was used because the system Python did not include `sklearn`, `pandas`, or `numpy`.

Command:

```powershell
& 'C:\Users\11816\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\scripts\run_reliability_prediction_experiments.py --features-dir .\data\audit\reliability --out-dir .\data\audit\reliability --bootstrap 300
```

## Frozen Artifacts

Scripts:

- `scripts/build_reliability_prediction_tables.py`
- `scripts/run_reliability_prediction_experiments.py`

Feature tables:

- `data/audit/reliability/item_level_features.csv`
- `data/audit/reliability/verdict_level_features.csv`
- `data/audit/reliability/feature_table_summary.json`

Prediction outputs:

- `data/audit/reliability/prediction_results.csv`
- `data/audit/reliability/item_level_results.csv`
- `data/audit/reliability/verdict_level_results.csv`
- `data/audit/reliability/feature_ablation_results.csv`
- `data/audit/reliability/score_baseline_results.csv`
- `data/audit/reliability/prediction_oof_scores.csv`
- `data/audit/reliability/calibration_bins.csv`
- `data/audit/reliability/top_audit_cases.csv`
- `data/audit/reliability/prediction_experiment_summary.json`

Validation:

- Item-level rows: 100
- Verdict-level rows: 1600
- Result rows: 147
- Out-of-fold prediction rows: 99,269

## Targets

Item-level targets:

| Target | Positives |
| --- | ---: |
| `target_human_unfaithful` | 78/100 |
| `target_benchmark_mismatch` | 40/100 |
| `target_any_main_llm_wrong` | 27/100 |
| `target_old_or_strict_wrong` | 11/100 |
| `target_strict_en_majority_wrong` | 4/100 |

Verdict-level targets:

| Target | Positives |
| --- | ---: |
| `target_verdict_unreliable_strict` | 197/1600 |
| `target_verdict_unreliable_covered` | 148/1551 |
| `target_verdict_high_confidence_wrong` | 111/1600 |

Important target decision:

- `target_strict_en_majority_wrong` has only 4 positives and is not suitable as a supervised training target. It is retained for ranking and case studies only.
- The most paper-aligned target is verdict-level `target_verdict_unreliable_strict`.

## Evaluation

Item-level:

- Leave-one-out cross-validation.
- Bootstrap confidence intervals over items.

Verdict-level:

- 5-fold grouped cross-validation by `audit_id`.
- Grouping by `audit_id` prevents verdicts from the same audit item appearing in both train and test folds.
- Bootstrap confidence intervals resample by audit item.

Models:

- direct score baselines,
- L2 logistic regression,
- L1 logistic regression,
- shallow random forest.

Feature ablations:

- risk only,
- disagreement only,
- confidence only,
- issue only,
- label/protocol only,
- risk + disagreement,
- risk + disagreement + confidence,
- all canonical features.

## Main Verdict-Level Results

These are the most important results for the paper because they directly predict unreliable automatic verdicts.

| Target | Model / features | AUROC | AUPRC | Top-20% precision | Lift | Brier |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| verdict unreliable, strict | random forest / all canonical | 0.968 | 0.896 | 0.584 | 4.75x | 0.037 |
| verdict unreliable, strict | logistic L2 / all canonical | 0.940 | 0.854 | 0.550 | 4.47x | 0.045 |
| verdict unreliable, strict | direct old-weak vote entropy | 0.760 | 0.271 | 0.322 | 2.61x | 0.153 |
| verdict unreliable, covered | random forest / all canonical | 0.949 | 0.852 | 0.444 | 4.65x | 0.035 |
| verdict unreliable, covered | logistic L2 / risk + disagreement | 0.921 | 0.769 | 0.444 | 4.65x | 0.044 |
| high-confidence wrong verdict | random forest / all canonical | 0.964 | 0.848 | 0.322 | 4.64x | 0.038 |

95% bootstrap intervals for key verdict results:

| Target | Model / features | AUROC CI | AUPRC CI | Brier CI |
| --- | --- | --- | --- | --- |
| verdict unreliable, strict | random forest / all canonical | [0.909, 1.000] | [0.747, 0.997] | [0.021, 0.059] |
| verdict unreliable, strict | logistic L2 / all canonical | [0.850, 0.996] | [0.691, 0.979] | [0.013, 0.086] |
| verdict unreliable, covered | random forest / all canonical | [0.850, 1.000] | [0.630, 1.000] | [0.017, 0.058] |
| high-confidence wrong verdict | random forest / all canonical | [0.894, 0.998] | [0.676, 0.980] | [0.024, 0.055] |

Interpretation:

- The main result is strong: unreliable verdicts can be prioritized with roughly 4.6-4.8x lift at a 20% audit budget.
- The model is not merely rediscovering one direct score; all-canonical models substantially outperform simple entropy/disagreement baselines in AUPRC.
- The logistic model is weaker than random forest but still strong and more interpretable, so both should be reported.

## Verdict Error Rates by Protocol

Strict target:

| Protocol | Verdicts | Unreliable | Rate |
| --- | ---: | ---: | ---: |
| benchmark/reference | 100 | 40 | 40.0% |
| pilot original | 300 | 39 | 13.0% |
| old weak | 600 | 80 | 13.3% |
| strict independent | 600 | 38 | 6.3% |

Covered target:

| Protocol | Covered verdicts | Unreliable | Rate |
| --- | ---: | ---: | ---: |
| benchmark/reference | 100 | 40 | 40.0% |
| pilot original | 296 | 35 | 11.8% |
| old weak | 555 | 35 | 6.3% |
| strict independent | 600 | 38 | 6.3% |

High-confidence wrong target:

| Protocol | Verdicts | High-confidence wrong | Rate |
| --- | ---: | ---: | ---: |
| old weak | 600 | 74 | 12.3% |
| strict independent | 600 | 37 | 6.2% |
| benchmark/reference | 100 | 0 | 0.0% |
| pilot original | 300 | 0 | 0.0% |

Interpretation:

- The benchmark/reference condition has the highest mismatch rate against the strict human audit.
- The strict independent protocol has the lowest verdict error rate, but still produces wrong and high-confidence wrong verdicts.
- This supports the paper claim that strong judge protocols still need reliability auditing.

## Item-Level Results

These are useful for audit prioritization, but they should be interpreted as audit-set results rather than population estimates.

| Target | Model / features | AUROC | AUPRC | Top-20% precision | Lift |
| --- | --- | ---: | ---: | ---: | ---: |
| benchmark mismatch | logistic L1 / all canonical | 0.995 | 0.991 | 1.000 | 2.50x |
| benchmark mismatch | direct pairwise disagreement count | 0.942 | 0.863 | 0.850 | 2.13x |
| any main LLM wrong | logistic L2 / disagreement only | 1.000 | 1.000 | 1.000 | 3.70x |
| any main LLM wrong | direct pairwise disagreement count | 0.973 | 0.919 | 1.000 | 3.70x |
| human unfaithful | random forest / all canonical | 0.995 | 0.999 | 1.000 | 1.28x |
| human unfaithful | direct issue total count | 0.996 | 0.999 | 1.000 | 1.28x |
| old-or-strict majority wrong | random forest / all canonical | 1.000 | 1.000 | 0.550 | 5.00x |

Interpretation:

- Benchmark mismatch is highly predictable from judge disagreement and protocol outputs.
- `any_main_llm_wrong` is almost mechanically tied to disagreement features, so this should be framed as audit triage rather than broad generalization.
- `human_unfaithful` has a high base rate in this risk-enriched batch, so top-20% lift is naturally capped at about 1.28x.

## Calibration

Calibration bins were generated for selected logistic L2 all-canonical predictors.

Key observations:

- For benchmark mismatch, predicted unreliability rises monotonically and aligns well in the high-risk bins:
  - highest bin: mean score 0.997, empirical rate 0.95.
  - fourth bin: mean score 0.949, empirical rate 0.90.
- For verdict-level strict unreliability, the model is rank-useful but not perfectly calibrated:
  - highest bin: mean score 0.714, empirical rate 0.55.
  - low bins have near-zero empirical error.

Interpretation:

- The reliability layer is already strong for ranking/audit prioritization.
- Absolute probability calibration needs more data or an explicit calibration step before being reported as final probability estimates.

## Scientific Takeaways

This experiment strongly supports the paper direction.

Supported claims:

1. Low-cost reliability features can predict unreliable RAG judge verdicts.
2. Disagreement is useful but insufficient; all-canonical features improve verdict-level AUPRC substantially.
3. High-confidence wrong verdicts are predictable, which directly supports the "auditing unreliable verdicts" framing.
4. Benchmark/reference mismatch is highly detectable, supporting the policy-misalignment argument.
5. Strict independent judging is strong but not self-certifying; it still benefits from an audit layer.

Claims to avoid:

- Do not claim population-level judge reliability from this risk-enriched 100-item audit set.
- Do not claim perfect calibration from the current pilot.
- Do not train or overinterpret `strict_en_majority_wrong` as a standalone supervised target because it has only 4 positives.
- Do not report assisted adjudication as a main predictor feature unless it is rerun under the canonical protocol.

## Publication Readiness

This is a publishable-strength pilot result for the reliability prediction component, especially the verdict-level results.

What is now strong:

- The experiment directly matches the paper title: predicting unreliable verdicts.
- It uses human gold, grouped evaluation, bootstrap intervals, and ablations.
- It shows clear audit-budget lift and identifies high-confidence wrong verdicts.

Remaining work before final paper:

- Add feature importance or coefficient analysis for interpretability.
- Write case studies from `top_audit_cases.csv`.
- Decide whether to rerun assisted adjudication under the canonical protocol or leave it as appendix/internal pilot.
- Ideally add a small second-human adjudication subset for inter-annotator agreement.
