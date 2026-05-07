# Freeze 27: Canonical English Strict Independent Judge Results

Date: 2026-05-06

This freeze records the canonical strict independent judge experiment for the 100-item audit set.

Canonical setup:

- Batch: `data/audit/human_audit_batch_100_blind.jsonl`
- Human gold: `data/audit/human_audit_annotations_en.csv`
- Prompt policy: frozen strict RAG faithfulness policy
- Prior AI references: none
- Temperature: 0
- `enable_thinking=false`

Models:

- `qwen3.6-max-preview`
- `deepseek-v4-pro`
- `kimi-k2.6`
- `qwen3-max-2026-01-23`
- `qwen3.6-plus-2026-04-02`

## Frozen Artifacts

Strict independent model outputs:

- `data/audit/strict_independent_en_qwen36maxpreview.csv/jsonl`
- `data/audit/strict_independent_en_deepseekv4pro.csv/jsonl`
- `data/audit/strict_independent_en_kimik26.csv/jsonl`
- `data/audit/strict_independent_en_qwen3max20260123.csv/jsonl`
- `data/audit/strict_independent_en_qwen36plus20260402.csv/jsonl`

Five-model comparison outputs:

- `data/audit/strict_independent_en_comparison_5models/strict_independent_summary.json`
- `data/audit/strict_independent_en_comparison_5models/strict_independent_by_item.csv`
- `data/audit/strict_independent_en_comparison_5models/pairwise_agreement.csv`

Updated human-gold analysis outputs:

- `data/audit/human_gold_analysis/condition_summary_against_human_gold.csv`
- `data/audit/human_gold_analysis/per_item_key_condition_comparison.csv`
- `data/audit/human_gold_analysis/paired_correctness_tests_against_human.csv`
- `data/audit/human_gold_analysis/model_group_consensus_against_human_gold.csv`
- `data/audit/human_gold_analysis/summary.json`

Code changes:

- `scripts/run_strict_independent_judge_labels.py` now reads JSONL with `utf-8-sig` for robust file handling.
- `scripts/analyze_human_gold_against_models.py` now defaults to `data/audit/human_audit_annotations_en.csv` when available.

Validation:

- Each strict independent model CSV has 100 rows.
- Errors: 0/500
- `parsed_ok=false`: 0/500

## Main Results

Label distributions and human-gold accuracy:

| Model | Faithful | Unfaithful | Accuracy |
| --- | ---: | ---: | ---: |
| qwen3.6-max-preview | 21 | 79 | 95% |
| deepseek-v4-pro | 19 | 81 | 93% |
| kimi-k2.6 | 17 | 83 | 93% |
| qwen3-max-2026-01-23 | 26 | 74 | 92% |
| qwen3.6-plus-2026-04-02 | 23 | 77 | 93% |
| 5-model majority | 20 | 80 | 96% |

Majority confusion against `HumanGold-v1`:

| Human label | Pred faithful | Pred unfaithful |
| --- | ---: | ---: |
| faithful | 19 | 3 |
| unfaithful | 1 | 77 |

Majority metrics:

- Exact accuracy: 96%
- 95% Wilson CI: [90.2%, 98.4%]
- Macro F1: 0.940
- Cohen's kappa: 0.880

## Agreement and Reliability

Pairwise agreement:

- Agreement range: 90%-96%
- Cohen's kappa range: 0.699-0.865

Group consensus:

- Unanimous items: 86/100
- Unanimous accuracy against human gold: 97.7%
- Unanimous wrong items: 2/100

Interpretation:

- The strict independent protocol is a strong main judge condition on this audit set.
- Agreement is useful but still not a complete reliability guarantee.
- Even unanimous model decisions can be wrong, which supports the need for reliability prediction and audit.

## Dataset and Stratum Effects

Dataset-level accuracy:

| Dataset | n | Human unfaithful rate | Old weak majority | Strict independent majority |
| --- | ---: | ---: | ---: | ---: |
| RAGBench | 46 | 63.0% | 95.7% | 95.7% |
| RAGTruth | 16 | 81.3% | 100.0% | 93.8% |
| RAMDocs | 38 | 94.7% | 84.2% | 97.4% |

Stratum-level highlights:

- Low-risk control: 95%
- Stable shared error: 95.5%
- Top multi-risk: 100%
- RAMDocs instability: 87.5%

Interpretation:

- The strict independent protocol performs strongly across datasets but still has dataset-specific and stratum-specific error modes.
- RAMDocs conflict and ambiguity cases remain especially valuable for case studies.
- Low-risk controls are useful for measuring false alarms.

## Updated Scientific Interpretation

This result strengthens the project.

Current main claims:

1. RAG faithfulness judging is strongly affected by explicit evaluation policy.
2. Strict independent judging is strong on the audited English-input setting but still imperfect.
3. Multi-model agreement should be treated as a reliability signal, not as ground truth.
4. Human-gold audit remains essential for detecting false alarms, missed unfaithful answers, and benchmark-reference mismatch.

## Next Required Step

Build the final human-gold reliability predictor using:

- risk scores,
- model disagreement,
- model confidence,
- issue categories,
- original benchmark/reference labels,
- old weak five-model outputs,
- strict independent five-model outputs.

Targets to evaluate:

- any judge/condition wrong vs human,
- strict independent majority wrong vs human,
- high-confidence but wrong verdict,
- benchmark/reference mismatch vs human,
- human-unfaithful detection.
