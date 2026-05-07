# Freeze 13 - Multi-Judge Robustness With GLM-5.1

Date: 2026-04-24

## Purpose

This freeze records the first multi-judge robustness experiment after the Qwen3.5-Plus full v2 pilot.

The goal was to test whether the observed LLM-as-a-Judge unreliability patterns persist under another judge model and whether simple multi-model voting improves reliability.

## Model Choice And Thinking Mode

Second judge model:

- `glm-5.1`

Endpoint:

- DashScope OpenAI-compatible chat completions.

Thinking:

- `enable_thinking=false`

Official note:

- Alibaba Cloud Model Studio documentation for GLM states that `enable_thinking` can switch thinking/non-thinking mode, and structured output is supported in non-thinking mode.
- Reference: https://help.aliyun.com/zh/model-studio/glm

We used the same v2 strict JSON protocol as Qwen:

- `configs/prompts/judge_prompts_v2_strict_json.json`
- `data/pilot/judge_tasks_v2_strict_json.jsonl`

## Files

GLM full output:

- `data/pilot/judge_outputs_full_v2_glm51_nothink.jsonl`

GLM analysis:

- `data/pilot/analysis_full_v2_glm51_nothink/`
- `data/pilot/reliability_full_v2_glm51_nothink/`
- `data/pilot/validation_full_v2_glm51_nothink/`

Multi-judge analysis:

- `scripts/multi_judge_analysis.py`
- `data/pilot/multi_judge_qwen35plus_glm51_v2/`

## GLM Run Integrity

The GLM full run completed cleanly:

- 1350/1350 tasks completed.
- 0 API errors.
- 1350/1350 parsed JSON.
- 1350/1350 `finish_reason=stop`.
- 0 truncations.
- median latency: about 2.258 seconds.
- mean latency: about 2.349 seconds.
- max latency: about 5.625 seconds.
- median prompt tokens: about 766.5.
- max prompt tokens: 2647.
- median completion tokens: about 40.
- max completion tokens: 224.

## GLM Single-Judge Results

Judgment-level:

- verdict counts: 351 faithful, 970 unfaithful, 29 insufficient.
- accuracy ignoring insufficient: 0.6722, Wilson 95% CI [0.6464, 0.6970].
- accuracy counting insufficient wrong: 0.6578, Wilson 95% CI [0.6321, 0.6826].

Sample-level:

- majority-vote accuracy: 101/150 = 0.6733.
- sample disagreement: 29/150 = 0.1933.
- broader instability: 37/150.
- majority-wrong samples: 49/150.

By dataset:

| Dataset | Judgment accuracy ignoring insufficient | Majority-wrong samples | Binary disagreement samples | Broader instability samples |
|---|---:|---:|---:|---:|
| RAGBench | 0.7245 | 14/50 | 9/50 | 16/50 |
| RAGTruth | 0.6600 | 17/50 | 0/50 | 0/50 |
| RAMDocs | 0.6333 | 18/50 | 20/50 | 21/50 |

Interpretation:

- GLM reproduces the same high-level pattern seen in Qwen.
- RAMDocs is the main instability source.
- RAGTruth mainly produces stable errors rather than perturbation disagreement.
- This supports the claim that the phenomenon is not specific to Qwen3.5-Plus.

## GLM Reliability Prediction

Within-sample exploratory AUC for predicting `majority_wrong`:

| Risk score | AUC |
|---|---:|
| `risk_combined` | 0.6751 |
| `risk_low_confidence` | 0.6541 |
| `risk_instability` | 0.6536 |
| `risk_disagreement` | 0.5989 |

Stratified CV:

| Risk score | Mean AUROC | Mean AUPRC |
|---|---:|---:|
| `risk_combined` | 0.6768 | 0.5216 |
| `risk_instability` | 0.6581 | 0.5272 |
| `risk_low_confidence` | 0.6556 | 0.5124 |

Leave-one-dataset-out:

| Risk score | Mean AUROC | Mean AUPRC |
|---|---:|---:|
| `risk_combined` | 0.6543 | 0.4936 |
| `risk_low_confidence` | 0.6460 | 0.4957 |
| `risk_instability` | 0.6382 | 0.4771 |

Interpretation:

- GLM reliability prediction remains above the short/resource threshold of 0.65 in stratified CV.
- LODO is weaker than Qwen but still near the minimum publishable threshold.
- Again, combined risk is stronger than disagreement-only.

## Qwen vs GLM Multi-Judge Analysis

Single-model majority accuracy:

| Judge | Majority accuracy |
|---|---:|
| Qwen3.5-Plus | 102/150 = 0.6800 |
| GLM-5.1 | 101/150 = 0.6733 |
| Combined 18-judgment majority | 100/150 = 0.6667 |

Important: simple multi-model majority did not improve accuracy.

Model complementarity:

| Category | Count | Rate |
|---|---:|---:|
| both models wrong | 42 | 0.2800 |
| only Qwen wrong | 6 | 0.0400 |
| only GLM wrong | 7 | 0.0467 |
| at least one model wrong | 55 | 0.3667 |
| model-majority disagreement | 13 | 0.0867 |

Disagreement:

- Mean per-task any-verdict disagreement rate: 0.1326.
- Mean per-task binary disagreement rate: 0.0920.
- Model-majority disagreement occurs in 13/150 samples.

By dataset:

| Dataset | Qwen majority acc | GLM majority acc | Combined majority acc | Model-majority disagreement |
|---|---:|---:|---:|---:|
| RAGBench | 0.7400 | 0.7200 | 0.7200 | 0.1000 |
| RAGTruth | 0.6800 | 0.6600 | 0.6400 | 0.0600 |
| RAMDocs | 0.6200 | 0.6400 | 0.6400 | 0.1000 |

Interpretation:

- Most errors are shared, not complementary.
- Multi-model voting is not a reliable fix.
- Model disagreement is rare but high-value as an audit signal: if model majorities disagree, at least one model is necessarily wrong under binary benchmark labels.
- Stable shared errors remain a central failure mode.

## Scientific Implication

This strengthens the paper's refined thesis:

1. Judge unreliability is reproducible across at least two judge models.
2. Conflict-heavy RAMDocs produces more perturbation/model instability.
3. RAGTruth produces stable errors across judges.
4. Simple majority voting across perturbations or models is insufficient.
5. Multi-judge disagreement should be treated as a reliability feature for audit, not as a replacement for calibration.

## Publication Criteria Update

Compared with Freeze 11:

Met:

- at least two judge models tested.
- same protocol works with clean outputs for both.
- unreliability phenomena replicate across models.
- combined risk remains stronger than disagreement-only.

Not met yet:

- multi-model voting does not improve accuracy.
- cross-model learned reliability is not yet tested.
- human audit sanity check is still missing.
- calibration interval improvement remains weak.

Decision:

- Keep multi-judge robustness as a supporting experiment.
- Do not frame the method as "more judges solve the problem."
- Frame the method as "multi-judge signals improve auditability and reveal shared failure modes."

Recommended next experiment:

- Build a multi-judge reliability feature table that includes model-majority disagreement and per-task cross-model disagreement.
- Compare it against single-judge risk scores for audit prioritization.
- Then run a human/proxy audit selection study using the top-risk samples from the multi-judge score.

