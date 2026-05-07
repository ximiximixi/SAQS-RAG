# Freeze 09 - Full V2 Pilot Results

Date: 2026-04-24

## Frozen Goal

Run the first scientifically cleaner full pilot after fixing the exploratory v1 issues:

- strict JSON output contract,
- short rationale limit,
- `finish_reason` logging,
- parsed-only analysis,
- Wilson confidence intervals for key rates.

This freeze is the main pilot baseline going forward.

## Protocol

Model and endpoint:

- model: `qwen3.5-plus`
- endpoint: DashScope OpenAI-compatible chat completions
- thinking mode: disabled
- temperature: 0
- max output tokens: 384

Prompt config:

- `configs/prompts/judge_prompts_v2_strict_json.json`

Task file:

- `data/pilot/judge_tasks_v2_strict_json.jsonl`

Judgment file:

- `data/pilot/judge_outputs_full_v2_qwen35plus_nothink.jsonl`

Analysis directory:

- `data/pilot/analysis_full_v2_qwen35plus_nothink/`

## Run Integrity

The run completed successfully:

- 150 samples
- 1350 judge tasks
- 1350/1350 completed
- 0 API errors
- 1350/1350 parsed JSON
- 1350/1350 `finish_reason=stop`
- 0 length truncations
- median latency: about 1.604 seconds
- mean latency: about 1.646 seconds
- max latency: about 9.168 seconds
- median prompt tokens: about 815.5
- max prompt tokens: 2798
- median completion tokens: about 51
- max completion tokens: 92

This is clean enough to treat as the first formal pilot, not merely a smoke test.

## Headline Metrics

Judgment-level:

- verdict counts: 374 faithful, 930 unfaithful, 46 insufficient
- accuracy ignoring insufficient: 0.6933, Wilson 95% CI [0.6677, 0.7177]
- accuracy counting insufficient as wrong: 0.6696, Wilson 95% CI [0.6441, 0.6942]

Sample-level:

- sample disagreement: 29/150 = 0.1933, Wilson 95% CI [0.1381, 0.2639]
- majority-vote sample accuracy: 102/150 = 0.6800, Wilson 95% CI [0.6017, 0.7494]
- majority-wrong samples: 48/150
- broader instability samples: 42/150
- unstable and majority-wrong: 20/150
- stable and majority-wrong: 28/150

Definitions:

- binary disagreement: at least one faithful and one unfaithful verdict appear for the same sample.
- broader instability: binary disagreement, prompt/order flip, insufficient verdict, or parse failure.
- stable majority-wrong: no broader instability, but majority verdict disagrees with the benchmark label.

## Breakdown By Dataset

Judgment-level:

| Dataset | Accuracy ignoring insufficient | Accuracy counting insufficient wrong | Insufficient rate |
|---|---:|---:|---:|
| RAGBench | 0.7407 | 0.7044 | 0.0489 |
| RAGTruth | 0.6786 | 0.6756 | 0.0044 |
| RAMDocs | 0.6612 | 0.6289 | 0.0489 |

Sample-level:

| Dataset | Samples | Binary disagreement | Broader instability | Majority wrong | Stable majority wrong |
|---|---:|---:|---:|---:|---:|
| RAGBench | 50 | 8 | 15 | 13 | 8 |
| RAGTruth | 50 | 2 | 3 | 16 | 15 |
| RAMDocs | 50 | 19 | 24 | 19 | 5 |

Interpretation:

- RAMDocs is the strongest instability source.
- RAGTruth is the strongest stable-error source.
- RAGBench has mixed behavior and useful insufficient cases.

## Breakdown By Evidence Order

| Evidence order | Accuracy ignoring insufficient | Accuracy counting insufficient wrong | Insufficient rate |
|---|---:|---:|---:|
| original | 0.7028 | 0.6778 | 0.0356 |
| reversed | 0.6982 | 0.6733 | 0.0356 |
| shuffle_seed_1 | 0.6789 | 0.6578 | 0.0311 |

Interpretation:

- Shuffled evidence order remains worse than original/reversed.
- The order effect is moderate but consistent with the 30-sample pilot.

## Breakdown By Prompt

| Prompt | Accuracy ignoring insufficient | Accuracy counting insufficient wrong | Insufficient rate |
|---|---:|---:|---:|
| `conflict_aware_v2` | 0.6637 | 0.6622 | 0.0022 |
| `minimal_binary_v2` | 0.7251 | 0.6622 | 0.0867 |
| `strict_faithfulness_v2` | 0.6937 | 0.6844 | 0.0133 |

Interpretation:

- Prompt choice affects both accuracy and abstention behavior.
- `minimal_binary_v2` is more accurate when it gives a binary verdict, but abstains more often.
- `conflict_aware_v2` is not automatically better; conflict-aware wording may make the judge stricter.

## Scientific Implication

The full v2 pilot strengthens the project rationale:

1. LLM-as-a-Judge is not reliable enough to use as an uncalibrated automatic RAG evaluator.
2. Prompt and evidence-order perturbations expose real instability, especially on conflict-heavy RAMDocs.
3. Instability alone is insufficient because many errors are stable and high-confidence.
4. Therefore the paper should propose a calibrated audit framework, not merely majority voting.

Refined core claim:

> RAG faithfulness judges fail through at least two modes: unstable verdicts under perturbation and stable high-confidence errors. A practical evaluator should estimate risk, allocate human audit to high-risk strata, and report calibrated scores with uncertainty.

## Decision

Proceed to reliability feature modeling and audit simulation.

Immediate next artifacts:

- per-sample reliability feature table,
- simple risk baselines,
- audit-stratification simulation,
- calibration/confidence interval prototype.

