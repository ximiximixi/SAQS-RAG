# Freeze 07 - DashScope Smoke Run Results

Date: 2026-04-24

## Frozen Goal

Verify that the pilot judge pipeline can run through DashScope OpenAI-compatible chat completions and produce analyzable results.

This freeze supersedes ad hoc smoke output in `data/pilot/judge_outputs.jsonl`, which mixed a few thinking-on and thinking-off calls during debugging. The clean smoke result is:

- `data/pilot/judge_outputs_balanced_smoke_qwen35plus_nothink.jsonl`
- `data/pilot/analysis_balanced_smoke_qwen35plus_nothink/`

## Local API Configuration

The local `.env` file was created with:

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `JUDGE_MODEL=qwen3.5-plus`
- `JUDGE_ENABLE_THINKING=false`

The API key is intentionally not copied into this freeze document.

Rationale: Alibaba Cloud Model Studio documentation says Qwen3.5 Plus hybrid thinking is enabled by default, and `enable_thinking=false` disables thinking mode for lower latency/direct responses through the OpenAI-compatible API.

Reference:

- https://www.alibabacloud.com/help/en/model-studio/deep-thinking

## Clean Balanced Smoke Subset

Selection script:

- `scripts/select_judge_tasks.py`

Selected subset:

- 12 samples
- 108 judge tasks
- 2 samples for each `dataset x gold_label` bucket
- 3 datasets: RAGBench, RAGTruth, RAMDocs
- 2 labels: faithful, unfaithful
- 3 prompts x 3 evidence orders per sample

Generated task file:

- `data/pilot/judge_tasks_balanced_smoke.jsonl`

Run command:

```powershell
& 'C:\Users\11816\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\run_judge_openai_compatible.py --tasks data\pilot\judge_tasks_balanced_smoke.jsonl --out data\pilot\judge_outputs_balanced_smoke_qwen35plus_nothink.jsonl --sleep 0.1 --timeout 90
```

Run status:

- 108/108 tasks completed
- 0 API failures
- no reasoning tokens after `enable_thinking=false`
- median latency about 3.817 seconds
- mean latency about 3.994 seconds
- max latency about 6.82 seconds
- median prompt tokens about 786.5
- max prompt tokens 1536
- median completion tokens about 163
- max completion tokens 256

## Main Analysis Results

Analysis output directory:

- `data/pilot/analysis_balanced_smoke_qwen35plus_nothink/`

Headline metrics:

- Judgments: 108
- Samples with judgments: 12
- Verdicts: 45 faithful, 63 unfaithful
- Parsed rate: 0.9444
- Overall accuracy: 0.8611
- Majority-vote sample accuracy: 0.9167
- Sample disagreement rate: 0.25

By dataset:

| Dataset | Judgments | Accuracy | Parsed rate |
|---|---:|---:|---:|
| RAGBench | 36 | 1.0000 | 0.8889 |
| RAGTruth | 36 | 0.7500 | 1.0000 |
| RAMDocs | 36 | 0.8333 | 0.9444 |

By evidence order:

| Evidence order | Judgments | Accuracy | Parsed rate |
|---|---:|---:|---:|
| original | 36 | 0.8889 | 0.9722 |
| reversed | 36 | 0.8889 | 0.8889 |
| shuffle_seed_1 | 36 | 0.8056 | 0.9722 |

## Sample-Level Signals

Disagreement appeared in 3 of 12 samples:

- `ramdocs_242_wrong`: gold unfaithful, majority unfaithful, but some variants predicted faithful.
- `ramdocs_386_gold`: gold faithful, majority faithful, but some variants predicted unfaithful.
- `ramdocs_93_gold`: gold faithful, majority faithful, but some variants predicted unfaithful.

One stable-but-wrong sample appeared:

- `ragtruth_3607`: gold faithful, all 9 variants predicted unfaithful.

Interpretation:

- The idea has an early positive signal.
- RAMDocs appears useful for conflict/order/prompt instability.
- RAGTruth may expose a second failure mode: high-confidence, stable false positives where the judge is consistently stricter than the dataset label.
- The paper should model both categories:
  1. unstable unreliable verdicts, detected by perturbation disagreement;
  2. stable unreliable verdicts, detected by calibrated audit or dataset/model residuals.

## Immediate Next Decision

The clean smoke run is sufficient to proceed to a larger pilot.

Recommended next run:

- balanced `per-dataset-label=5`
- 30 samples
- 270 judge tasks

If that still shows sample disagreement above 10% and RAMDocs/RAGTruth weakness, run the full 150-sample pilot.

