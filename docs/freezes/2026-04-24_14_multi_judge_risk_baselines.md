# Freeze 14 - Multi-Judge Risk Baselines

Date: 2026-04-24

## Purpose

This freeze records whether cross-model disagreement features improve reliability/audit scoring after adding GLM-5.1 as a second judge.

The main question:

> Should multi-judge signals be used as a direct voting mechanism, or as audit-risk features?

## Inputs

Single-judge features:

- `data/pilot/reliability_full_v2_qwen35plus_nothink/sample_reliability_features.csv`
- `data/pilot/reliability_full_v2_glm51_nothink/sample_reliability_features.csv`

Multi-judge alignment:

- `data/pilot/multi_judge_qwen35plus_glm51_v2/multi_judge_per_sample.csv`

Script:

- `scripts/multi_judge_risk_baselines.py`

Outputs:

- `data/pilot/multi_judge_risk_qwen35plus_glm51_v2/`

## Risk Scores

Compared scores:

- `risk_qwen_combined`
- `risk_glm_combined`
- `risk_avg_single`
- `risk_max_single`
- `risk_model_majority_disagreement`
- `risk_task_binary_disagreement`
- `risk_multi_combined`

Targets:

- `combined_wrong`: combined 18-judgment majority is wrong or non-correct.
- `any_model_wrong`: at least one model's sample-level majority verdict is wrong.
- `both_wrong`: both model majorities are wrong.

## Key Result 1 - Multi-Judge Voting Does Not Improve Accuracy

From Freeze 13:

| Judge setup | Majority accuracy |
|---|---:|
| Qwen3.5-Plus | 0.6800 |
| GLM-5.1 | 0.6733 |
| Combined 18-judgment majority | 0.6667 |

Interpretation:

- Adding a second judge does not automatically improve correctness.
- Errors are highly overlapping: both models are wrong on 42/150 samples.
- Therefore, the method should not be framed as "use more judges and vote."

## Key Result 2 - Multi-Judge Features Help Audit-Oriented Risk

For target `combined_wrong`:

| Risk score | AUROC | AUPRC |
|---|---:|---:|
| `risk_qwen_combined` | 0.6972 | 0.5390 |
| `risk_multi_combined` | 0.6901 | 0.5145 |
| `risk_avg_single` | 0.6809 | 0.5159 |
| `risk_glm_combined` | 0.6711 | 0.4810 |
| `risk_model_majority_disagreement` | 0.5550 | 0.4259 |

For target `any_model_wrong`:

| Risk score | AUROC | AUPRC |
|---|---:|---:|
| `risk_multi_combined` | 0.7423 | 0.6696 |
| `risk_max_single` | 0.7302 | 0.6373 |
| `risk_avg_single` | 0.7281 | 0.6339 |
| `risk_qwen_combined` | 0.7228 | 0.6449 |
| `risk_task_binary_disagreement` | 0.6796 | 0.6618 |
| `risk_model_majority_disagreement` | 0.6182 | 0.5781 |

Interpretation:

- Multi-judge features are strongest when the target is "does any judge become unreliable?"
- They are not stronger for predicting the combined-vote label.
- This supports using multi-judge disagreement as an audit trigger, not a vote aggregator.

## Top-K Audit Results

Target: `any_model_wrong`

| Risk score | Audit fraction | Precision | Recall | Lift over random |
|---|---:|---:|---:|---:|
| `risk_multi_combined` | 20% | 0.8000 | 0.4364 | 2.1818 |
| `risk_avg_single` | 20% | 0.7333 | 0.4000 | 2.0000 |
| `risk_qwen_combined` | 20% | 0.7000 | 0.3818 | 1.9091 |
| `risk_multi_combined` | 30% | 0.6222 | 0.5091 | 1.6970 |

Target: `combined_wrong`

| Risk score | Audit fraction | Precision | Recall | Lift over random |
|---|---:|---:|---:|---:|
| `risk_multi_combined` | 20% | 0.6333 | 0.3800 | 1.9000 |
| `risk_avg_single` | 20% | 0.6000 | 0.3600 | 1.8000 |
| `risk_qwen_combined` | 20% | 0.5667 | 0.3400 | 1.7000 |
| `risk_multi_combined` | 30% | 0.5111 | 0.4600 | 1.5333 |

Interpretation:

- For audit prioritization, multi-judge risk is useful.
- At 20% audit budget, it reaches 80% precision for finding samples where at least one model is wrong.
- This is a strong supporting result for an audit-centered paper.

## Scientific Framing Update

Keep:

> Multi-judge signals improve auditability and expose shared failure modes.

Avoid:

> Multi-judge majority voting fixes LLM judge unreliability.

Best method framing:

1. Run cheap perturbation diagnostics for one or more judges.
2. Compute interpretable risk features.
3. Treat cross-model disagreement as an additional audit-risk feature.
4. Defer or audit high-risk samples.
5. Report calibrated scores with conservative intervals.

## Publication Criteria Update

This result strengthens the full-paper case:

- two judge models tested,
- unreliability patterns replicate,
- multi-judge risk improves audit prioritization,
- disagreement-only remains weaker than combined risk,
- simple majority voting fails, making calibration/audit necessary.

Remaining gaps:

- human audit sanity check,
- larger sample size or one additional dataset/model if time permits,
- stronger calibration estimator for interval narrowing.

