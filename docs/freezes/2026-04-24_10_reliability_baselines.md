# Freeze 10 - Reliability Feature And Audit Baselines

Date: 2026-04-24

## Frozen Goal

Turn the full v2 judge outputs into sample-level reliability features and test whether cheap, interpretable risk scores can prioritize unreliable majority verdicts for human audit.

This is an exploratory baseline, not a final generalization claim. The full paper still needs larger-scale validation and held-out/cross-dataset evaluation.

## Inputs

Judgment file:

- `data/pilot/judge_outputs_full_v2_qwen35plus_nothink.jsonl`

Sample file:

- `data/pilot/pilot_samples.jsonl`

Script:

- `scripts/reliability_baselines.py`

Output directory:

- `data/pilot/reliability_full_v2_qwen35plus_nothink/`

Outputs:

- `sample_reliability_features.csv`
- `risk_score_summary.csv`
- `audit_topk_metrics.csv`

## Target

Prediction target:

- `majority_wrong`: whether the sample-level majority verdict disagrees with the benchmark label.

Observed target prevalence:

- 48/150 samples = 32.0% majority wrong.
- Majority-vote sample accuracy = 68.0%.

## Reliability Features

Features are derived only from judge outputs and perturbation structure:

- faithful/unfaithful/insufficient vote counts,
- majority margin,
- binary vote entropy,
- verdict entropy,
- prompt flip count,
- order flip count,
- insufficient rate,
- mean/min/max/std confidence,
- parse/error counts,
- hand-composed instability and combined risk scores.

No model training or GPU is used.

## Risk Score AUC

Exploratory AUC for predicting `majority_wrong`:

| Risk score | AUC | Mean score wrong | Mean score correct |
|---|---:|---:|---:|
| `risk_combined` | 0.6965 | 1.4674 | 0.6173 |
| `risk_low_confidence` | 0.6807 | 0.0678 | 0.0445 |
| `risk_instability` | 0.6567 | 0.9004 | 0.3886 |
| `risk_low_margin` | 0.5931 | 0.1818 | 0.0635 |
| `risk_entropy` | 0.5931 | 0.2596 | 0.0979 |
| `risk_disagreement` | 0.5876 | 0.3125 | 0.1373 |
| `risk_insufficient` | 0.5689 | 0.0579 | 0.0229 |

Interpretation:

- Single disagreement is weak but non-random.
- A combined risk score is stronger than any single perturbation signal.
- This supports the paper's claim that calibrated reliability estimation should combine multiple diagnostic signals.

## Top-K Audit Simulation

Base majority accuracy:

- 102/150 = 68.0%

Base error rate:

- 48/150 = 32.0%

Using `risk_combined`:

| Audit fraction | Audit n | Captured errors | Precision | Recall | Lift over random | Retained accuracy |
|---|---:|---:|---:|---:|---:|---:|
| 10% | 15 | 11 | 0.7333 | 0.2292 | 2.2917 | 0.7259 |
| 20% | 30 | 16 | 0.5333 | 0.3333 | 1.6667 | 0.7333 |
| 30% | 45 | 21 | 0.4667 | 0.4375 | 1.4583 | 0.7429 |
| 40% | 60 | 28 | 0.4667 | 0.5833 | 1.4583 | 0.7778 |

Interpretation:

- Auditing the top-risk 10% catches errors at 73.3% precision, compared with a 32.0% random baseline.
- Selectively deferring the top-risk 40% raises retained-sample majority accuracy from 68.0% to 77.8%.
- This supports an audit-oriented framing, but not yet a final calibrated guarantee.

## Scientific Caveats

This result is encouraging but still preliminary:

1. Risk scores were evaluated on the same pilot from which we inspected phenomena.
2. The combined score is hand-designed, not learned on a training split.
3. Full paper claims need held-out validation, preferably cross-dataset.
4. Benchmark labels may themselves differ in strictness from judge criteria, especially RAGTruth and RAMDocs constructed cases.
5. Human audit simulation currently uses dataset labels as proxy humans.

## Decision

Proceed to the next methodological layer:

1. create train/test or leave-one-dataset-out reliability evaluation,
2. add audit-stratified confidence intervals,
3. simulate small human audit budgets,
4. compare against baselines: single judge, majority vote, disagreement-only abstention, confidence-only abstention.

