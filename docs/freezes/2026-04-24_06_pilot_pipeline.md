# Freeze 06 - Pilot Pipeline Construction

Date: 2026-04-24

## Frozen Goal

Test whether the core paper idea is empirically viable with a small, low-cost pilot:

> LLM-as-a-Judge verdicts for RAG faithfulness can become unreliable under prompt variation, evidence-order perturbation, and conflict-heavy evidence. These unreliable verdicts can be predicted and audited with cheap consistency features plus a small human audit set.

This freeze records the first executable pipeline. Later conversations should treat this as the baseline unless we explicitly revise it.

## Generated Artifacts

Code:

- `scripts/prepare_pilot_samples.py`
- `scripts/build_judge_tasks.py`
- `scripts/run_judge_openai_compatible.py`
- `scripts/analyze_judge_outputs.py`

Config:

- `configs/prompts/judge_prompts.json`

Data:

- `data/pilot/pilot_samples.jsonl`
- `data/pilot/judge_tasks.jsonl`

## Pilot Sample Construction

Unified schema:

- `sample_id`
- `dataset`
- `source_id`
- `question`
- `answer`
- `evidence`
- `gold_label`
- `gold_label_binary`
- `gold_label_source`
- `meta`

Included datasets:

| Dataset | Role | Faithful | Unfaithful | Total |
|---|---:|---:|---:|---:|
| RAGBench | General RAG adherence labels | 25 | 25 | 50 |
| RAGTruth | Human hallucination/faithfulness labels | 25 | 25 | 50 |
| RAMDocs | Conflict-heavy constructed gold/wrong answers | 25 | 25 | 50 |
| Total | Pilot | 75 | 75 | 150 |

Quality checks:

- Blank questions: 0
- Blank answers: 0
- Blank evidence: 0
- RAGTruth question text was cleaned so source documents remain in `evidence`, not duplicated inside `question`.

Prompt/evidence perturbations:

- Prompt variants: `strict_faithfulness`, `conflict_aware`, `minimal_binary`
- Evidence orders: `original`, `reversed`, `shuffle_seed_1`
- Judge tasks: `150 samples * 3 prompts * 3 orders = 1350`

Median rendered judge prompt length:

- About 3,189 characters.
- Max about 10,756 characters.

## Runner And Analysis Protocol

The runner uses an OpenAI-compatible chat completions endpoint, supports resume, and writes one JSONL row per judge task.

Dry-run command:

```powershell
& 'C:\Users\11816\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\run_judge_openai_compatible.py --tasks data\pilot\judge_tasks.jsonl --out data\pilot\judge_outputs.jsonl --limit 3 --dry-run
```

Full pilot command after setting an API key:

```powershell
$env:OPENAI_API_KEY = '<key>'
& 'C:\Users\11816\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\run_judge_openai_compatible.py --tasks data\pilot\judge_tasks.jsonl --out data\pilot\judge_outputs.jsonl --model gpt-4o-mini
```

Small smoke run before full pilot:

```powershell
& 'C:\Users\11816\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\run_judge_openai_compatible.py --tasks data\pilot\judge_tasks.jsonl --out data\pilot\judge_outputs.jsonl --model gpt-4o-mini --limit 30
```

Analysis command:

```powershell
& 'C:\Users\11816\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\analyze_judge_outputs.py --samples data\pilot\pilot_samples.jsonl --judgments data\pilot\judge_outputs.jsonl --out-dir data\pilot\analysis
```

Analysis outputs:

- `data/pilot/analysis/summary.json`
- `data/pilot/analysis/per_sample_reliability.csv`
- `data/pilot/analysis/metrics_by_dataset_prompt.csv`

## Feasibility Criteria

The idea is considered promising if the pilot shows at least two of the following:

1. Non-trivial sample-level disagreement across prompt/order variants, target threshold about 10% or higher.
2. Disagreement, order flips, prompt flips, insufficient verdicts, or confidence variance correlate with judge error.
3. RAMDocs conflict-heavy examples have higher disagreement or lower accuracy than general RAGBench examples.
4. A simple majority vote or selective abstention improves accuracy on retained samples.
5. Low-confidence/high-disagreement samples produce a meaningful audit set for manual review.

If disagreement is too low, the next pivot is not to abandon the topic. We should strengthen the stress test using:

- `rag_conflicts` for explicit conflict taxonomy,
- adversarial evidence insertion,
- additional judge models,
- harder answer pairs from RAMDocs wrong answers,
- more prompt styles, including rubric-heavy and terse binary judging.

## Current Status

Ready for first judge run once an API key is available.

Local environment check on 2026-04-24 found no API key in:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `DEEPSEEK_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `OPENROUTER_API_KEY`

Syntax checks passed for all four scripts.

