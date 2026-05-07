# Freeze 08 - Balanced 30-Sample Pilot Results

Date: 2026-04-24

## Frozen Goal

Run a larger balanced pilot after the 12-sample smoke test to decide whether the paper idea should proceed to a full pilot.

This run uses:

- model: `qwen3.5-plus`
- endpoint: DashScope OpenAI-compatible chat completions
- thinking mode: disabled
- samples: 30
- judge tasks: 270

The API key is stored only in the local `.env` file and is not copied into this freeze.

## Files

Task file:

- `data/pilot/judge_tasks_balanced_pilot30.jsonl`

Judgment file:

- `data/pilot/judge_outputs_balanced_pilot30_qwen35plus_nothink.jsonl`

Analysis directory:

- `data/pilot/analysis_balanced_pilot30_qwen35plus_nothink/`

## Run Status

The run completed successfully:

- 270/270 tasks completed
- 0 API failures
- median latency: about 3.516 seconds
- mean latency: about 3.680 seconds
- max latency: about 8.704 seconds
- median prompt tokens: about 799
- max prompt tokens: 2807
- median completion tokens: about 148
- max completion tokens: 256
- reasoning tokens: 0 non-null entries

## Dataset Balance

The selected sample set is balanced:

| Dataset | Faithful samples | Unfaithful samples | Samples | Judge tasks |
|---|---:|---:|---:|---:|
| RAGBench | 5 | 5 | 10 | 90 |
| RAGTruth | 5 | 5 | 10 | 90 |
| RAMDocs | 5 | 5 | 10 | 90 |
| Total | 15 | 15 | 30 | 270 |

Each sample has:

- 3 prompt variants
- 3 evidence order variants
- 9 total judgments

## Headline Metrics

Judgment-level:

- verdict counts: 88 faithful, 178 unfaithful, 4 insufficient
- parsed rate: 0.9667
- accuracy ignoring insufficient: 0.7293
- accuracy counting insufficient as wrong: 0.7185

Sample-level:

- sample disagreement rate: 0.1667
- majority-vote sample accuracy: 0.7667
- binary disagreement samples: 5/30
- broader instability samples: 9/30
- majority-wrong samples: 7/30
- stable-and-majority-wrong samples: 6/30
- unstable-and-majority-wrong samples: 1/30

Definitions:

- binary disagreement: at least one faithful and one unfaithful verdict appear for the same sample.
- broader instability: binary disagreement, prompt/order flip, insufficient verdict, or parse failure.
- stable-and-majority-wrong: all variants are effectively consistent, but the majority verdict disagrees with the dataset label.

## Breakdown By Dataset

Judgment-level:

| Dataset | Accuracy ignoring insufficient | Accuracy counting insufficient wrong | Parsed rate | Insufficient rate |
|---|---:|---:|---:|---:|
| RAGBench | 0.6977 | 0.6667 | 0.9778 | 0.0444 |
| RAGTruth | 0.7000 | 0.7000 | 1.0000 | 0.0000 |
| RAMDocs | 0.7889 | 0.7889 | 0.9222 | 0.0000 |

Sample-level:

| Dataset | Samples | Binary disagreement | Broader instability | Majority wrong |
|---|---:|---:|---:|---:|
| RAGBench | 10 | 0 | 3 | 3 |
| RAGTruth | 10 | 0 | 0 | 3 |
| RAMDocs | 10 | 5 | 6 | 1 |

Interpretation:

- RAMDocs is the strongest source of prompt/order instability.
- RAGTruth is the strongest source of stable high-confidence judge errors.
- RAGBench shows both insufficient verdicts and stable majority errors.

## Breakdown By Evidence Order

| Evidence order | Accuracy ignoring insufficient | Accuracy counting insufficient wrong | Parsed rate |
|---|---:|---:|---:|
| original | 0.7528 | 0.7444 | 0.9889 |
| reversed | 0.7416 | 0.7333 | 0.9444 |
| shuffle_seed_1 | 0.6932 | 0.6778 | 0.9667 |

Interpretation:

- Shuffled evidence order is worse than original/reversed in this run.
- This supports keeping evidence-order perturbation as a diagnostic feature.

## Breakdown By Prompt

| Prompt | Accuracy ignoring insufficient | Accuracy counting insufficient wrong | Parsed rate | Insufficient rate |
|---|---:|---:|---:|---:|
| `conflict_aware` | 0.7222 | 0.7222 | 0.9667 | 0.0000 |
| `minimal_binary` | 0.7326 | 0.7000 | 0.9778 | 0.0444 |
| `strict_faithfulness` | 0.7333 | 0.7333 | 0.9556 | 0.0000 |

Interpretation:

- Prompt choice matters less than dataset and evidence order in this pilot.
- The minimal prompt produces all insufficient verdicts in this run.

## Important Scientific Takeaways

The idea remains viable, but the pilot refines the claim.

Supported:

1. Judge verdicts are not perfectly reliable even with a strong model and deterministic temperature.
2. Evidence order perturbation affects accuracy, especially shuffled order.
3. Conflict-heavy RAMDocs creates observable prompt/order flips.
4. RAGTruth exposes stable, high-confidence judge errors.
5. A single diagnostic is not enough; we need a calibrated and auditable reliability model.

Not yet supported:

1. Perturbation disagreement alone is not a strong predictor of majority-vote error in this small pilot.
2. Simple abstention on disagreement would not improve majority accuracy here, because many disagreement cases still have correct majority votes.

Refined paper framing:

> The framework should not claim that disagreement alone detects all judge failures. It should predict and audit multiple unreliability modes: unstable verdicts, insufficient/parse anomalies, and stable high-confidence errors that require calibrated human audit.

## Decision

Proceed to full pilot.

The threshold from Freeze 06 was sample disagreement above about 10%. This run has:

- binary sample disagreement: 16.67%
- broader instability: 30.00%
- majority-vote error: 23.33%

The next run should use all 150 pilot samples and 1350 judge tasks with the same Qwen3.5 Plus no-thinking configuration, written to a fresh output file.

