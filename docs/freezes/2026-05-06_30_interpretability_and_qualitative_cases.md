# Freeze 30: Interpretability and Qualitative Cases

Date: 2026-05-06

This freeze records the interpretability and qualitative-analysis step after the canonical reliability prediction experiment.

## Decision

This step is appropriate and paper-aligned.

It follows the remaining work listed in `docs/freezes/2026-05-06_29_reliability_prediction_results.md`:

- add feature importance or coefficient analysis for interpretability,
- write case studies from `data/audit/reliability/top_audit_cases.csv`.

Scope boundaries:

- Assisted adjudication is still excluded from main predictor features.
- Interpretability models are fitted on the full canonical feature tables for explanation only.
- Predictive performance claims still come from the grouped/LOO cross-validation results frozen in Freeze 29.
- Qualitative cases are for mechanism explanation and paper writing, not additional evaluation metrics.

## Commands

Feature importance and coefficient analysis:

```powershell
& 'C:\Users\11816\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\scripts\analyze_reliability_interpretability.py --features-dir .\data\audit\reliability --out-dir .\data\audit\reliability\interpretability
```

Qualitative case selection:

```powershell
& 'C:\Users\11816\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\scripts\build_qualitative_case_studies.py --out-dir .\data\audit\reliability\qualitative
```

## Frozen Artifacts

Scripts:

- `scripts/analyze_reliability_interpretability.py`
- `scripts/build_qualitative_case_studies.py`

Interpretability outputs:

- `data/audit/reliability/interpretability/logistic_coefficients_expanded.csv`
- `data/audit/reliability/interpretability/logistic_coefficients_by_raw_feature.csv`
- `data/audit/reliability/interpretability/logistic_coefficients_by_feature_group.csv`
- `data/audit/reliability/interpretability/random_forest_importance_expanded.csv`
- `data/audit/reliability/interpretability/random_forest_importance_by_raw_feature.csv`
- `data/audit/reliability/interpretability/random_forest_importance_by_feature_group.csv`
- `data/audit/reliability/interpretability/feature_group_ablation_summary.csv`
- `data/audit/reliability/interpretability/interpretability_summary.json`

Qualitative outputs:

- `data/audit/reliability/qualitative/qualitative_case_studies.csv`
- `data/audit/reliability/qualitative/qualitative_case_studies.md`
- `data/audit/reliability/qualitative/qualitative_case_summary.json`

## Interpretability Summary

The analysis covers seven selected targets:

- item-level `target_benchmark_mismatch`,
- item-level `target_any_main_llm_wrong`,
- item-level `target_human_unfaithful`,
- item-level `target_old_or_strict_wrong`,
- verdict-level `target_verdict_unreliable_strict`,
- verdict-level `target_verdict_unreliable_covered`,
- verdict-level `target_verdict_high_confidence_wrong`.

Generated rows:

- logistic coefficient expanded rows: 3,040,
- random-forest expanded importance rows: 1,520,
- ablation summary rows: 56.

## Main Mechanistic Finding

The reliability predictor works mainly because unreliable verdicts leave low-cost traces in cross-judge and cross-protocol disagreement patterns.

Random-forest feature-group importances:

| Target | Disagreement | Label/protocol | Text | Risk | Issue | Confidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Verdict unreliable, strict | 0.583 | 0.228 | 0.070 | 0.063 | 0.050 | 0.007 |
| High-confidence wrong verdict | 0.558 | 0.227 | 0.072 | 0.065 | 0.028 | 0.050 |
| Benchmark mismatch | 0.808 | 0.099 | 0.022 | 0.022 | 0.020 | 0.030 |
| Any main LLM wrong | 0.914 | 0.020 | 0.006 | 0.036 | 0.019 | 0.006 |
| Human unfaithful | 0.704 | 0.161 | 0.004 | 0.002 | 0.113 | 0.016 |

Interpretation:

- Disagreement is the dominant explanatory signal across the central targets.
- Label/protocol features matter because verdict reliability is protocol-dependent: benchmark/reference, old weak, strict independent, and pilot protocols fail differently.
- Issue-category features are especially useful for human-unfaithful items, where conflict/ambiguity and unsupported-claim bundles align with the human audit rationale.
- Confidence alone is weak, but it becomes useful for the `high_confidence_wrong` target when combined with disagreement and protocol features.

## Top Raw Feature Patterns

For the primary verdict-level strict unreliability target, the most important random-forest raw features are:

- agreement with strict independent majority,
- agreement with old weak majority,
- agreement with cross-LLM majority,
- agreement with cross-main majority,
- the verdict label itself,
- main-condition pairwise disagreement count,
- old-weak vote entropy and vote margin,
- risk score,
- unsupported/contradiction issue bundle.

For high-confidence wrong verdicts, the top features are similar, with additional contribution from:

- high-confidence indicator,
- confidence missingness,
- protocol and model identity.

For benchmark mismatch, the strongest raw features are:

- benchmark-vs-old-weak disagreement,
- benchmark-vs-strict disagreement,
- benchmark-vs-pilot disagreement,
- main-condition vote entropy and margin.

This supports the paper claim that the predictor is not merely memorizing a single risk score. It detects unstable evaluation situations where different judge protocols disagree about the same evidence-answer pair.

## Ablation Reading

Primary verdict-level target:

| Feature set | Best model | AUROC | AUPRC | Top-20 precision | Lift |
| --- | --- | ---: | ---: | ---: | ---: |
| All canonical | random forest | 0.968 | 0.896 | 0.584 | 4.75x |
| Disagreement only | logistic L2 | 0.938 | 0.831 | 0.584 | 4.75x |
| Risk + disagreement + confidence | logistic L2 | 0.938 | 0.819 | 0.584 | 4.75x |
| Label/protocol only | logistic L2 | 0.877 | 0.668 | 0.463 | 3.76x |
| Issue only | logistic L2 | 0.682 | 0.245 | 0.184 | 1.50x |
| Risk only | logistic L2 | 0.682 | 0.225 | 0.269 | 2.18x |
| Confidence only | logistic L2 | 0.613 | 0.170 | 0.197 | 1.60x |

High-confidence wrong verdict target:

| Feature set | Best model | AUROC | AUPRC | Top-20 precision | Lift |
| --- | --- | ---: | ---: | ---: | ---: |
| All canonical | random forest | 0.964 | 0.848 | 0.322 | 4.64x |
| Risk + disagreement + confidence | logistic L2 | 0.952 | 0.756 | 0.322 | 4.64x |
| Risk + disagreement | logistic L2 | 0.925 | 0.523 | 0.266 | 3.83x |
| Disagreement only | logistic L2 | 0.928 | 0.514 | 0.259 | 3.74x |
| Label/protocol only | logistic L2 | 0.837 | 0.415 | 0.231 | 3.33x |
| Issue only | logistic L2 | 0.621 | 0.201 | 0.128 | 1.85x |
| Confidence only | logistic L2 | 0.719 | 0.144 | 0.150 | 2.16x |
| Risk only | logistic L2 | 0.639 | 0.103 | 0.106 | 1.53x |

Interpretation:

- Disagreement alone is strong, but all-canonical features improve AUPRC for the main verdict target.
- For high-confidence wrong verdicts, confidence becomes valuable only in combination with disagreement/risk/protocol features.
- Risk-only, issue-only, and confidence-only baselines are not enough for the central reliability prediction claim.

## Logistic Coefficients

Logistic coefficient files are retained for transparency and sparse-feature inspection.

Caution:

- Expanded one-hot categorical features such as `condition`, `model_name`, `dataset`, and `protocol` have large coefficients in verdict-level targets.
- This is expected because verdict reliability differs sharply by protocol and because the audit sample is risk-enriched.
- Therefore, coefficient analysis should be reported as a secondary interpretability view, while ablation and grouped-CV performance remain the main evidence.

## Qualitative Case Set

The qualitative set contains 11 cases:

| Case group | Count |
| --- | ---: |
| Entity/title ambiguity | 2 |
| Entity/person ambiguity | 1 |
| Insufficient or weakly linked evidence | 1 |
| Evidence conflict | 1 |
| Temporal/evidence conflict | 1 |
| Unsupported specificity | 1 |
| Insufficient evidence in table context | 1 |
| Numeric error | 1 |
| False alarm / abstention failure | 1 |
| False alarm / policy boundary | 1 |

Human labels:

| Label | Count |
| --- | ---: |
| unfaithful | 9 |
| faithful | 2 |

Selected cases:

| Case | Group | Human label | Main use |
| --- | --- | --- | --- |
| AUDIT-018 | Entity/title ambiguity | unfaithful | Benchmark and weak-judge over-certainty under title ambiguity |
| AUDIT-024 | Entity/title ambiguity | unfaithful | Benchmark mismatch caused by unresolved media/title ambiguity |
| AUDIT-030 | Entity/person ambiguity | unfaithful | Name ambiguity where evidence supports multiple entities |
| AUDIT-020 | Insufficient or weakly linked evidence | unfaithful | Insufficient evidence despite superficially relevant snippets |
| AUDIT-061 | Evidence conflict | unfaithful | Conflict case for auditing confident automatic verdicts |
| AUDIT-065 | Temporal/evidence conflict | unfaithful | Temporal conflict |
| AUDIT-050 | Unsupported specificity | unfaithful | Claim-level over-specificity under near-matching evidence |
| AUDIT-075 | Insufficient evidence in table context | unfaithful | Table truncation / missing-evidence case |
| AUDIT-089 | Numeric error | unfaithful | Numeric/calculation failure |
| AUDIT-040 | False alarm / abstention failure | faithful | False-positive case for qualitative balance |
| AUDIT-009 | False alarm / policy boundary | faithful | Strict-prompt false alarm |

## Paper-Ready Interpretation

The qualitative cases support three arguments:

1. Many unreliable verdicts arise when evidence contains multiple plausible entities, titles, dates, or conflicting facts, and a judge presents one option as certain.
2. The reliability predictor is useful because those cases tend to produce measurable disagreement, abstention, protocol shifts, issue-category concentration, or confidence/protocol anomalies.
3. The method should be framed as audit prioritization, not automatic replacement of human judgment: the faithful false-alarm cases show why a high risk score should trigger review rather than final rejection.

## Remaining Work

Before paper submission:

- Convert the qualitative markdown into a concise paper subsection with 3-5 representative examples.
- Add figures/tables for feature-group importances and ablation deltas.
- If feasible, add a small second-human adjudication subset for inter-annotator agreement.
- Keep assisted adjudication in appendix/internal pilot unless rerun under the canonical English-input protocol.
