# Freeze 18: Additional Qwen Weak Labels and Five-Model Comparison

Date: 2026-04-25

## Purpose

We extended the audit weak-supervision pool with two additional Qwen-family models:

- `qwen3-max-2026-01-23`
- `qwen3.6-plus-2026-04-02`

They were run on the same 100-item blind human audit batch and with the same strict audit protocol used in Freeze 17. The goal was to test whether adding more strong judges, including same-family variants, reduces uncertainty or instead exposes additional systematic disagreement.

## Inputs

- Blind audit batch: `data/audit/human_audit_batch_100_blind.jsonl`
- Hidden research metadata: `data/audit/human_audit_batch_100_metadata.csv`
- API endpoint: existing OpenAI-compatible endpoint configured in `.env`
- Thinking: disabled (`enable_thinking=false`)
- Output schema: strict JSON with labels `faithful`, `unfaithful`, `insufficient`

The API key is intentionally not recorded in this document.

## Scripts

- Generation: `scripts/run_audit_model_labels.py`
- Comparison: `scripts/compare_audit_model_labels.py`

Important script update:

- `scripts/compare_audit_model_labels.py` was generalized from three-model-specific naming to multi-model statistics.
- The five-model summary now uses `multi_model`, `all_label_options_used`, `top_label_vote_fraction`, and `top_binary_vote_fraction`.

## New Generated Labels

Both new models completed 100/100 items with 0 API failures and 100% parse success.

New outputs:

- `data/audit/weak_labels_qwen3max20260123.csv`
- `data/audit/weak_labels_qwen3max20260123.jsonl`
- `data/audit/weak_labels_qwen36plus20260402.csv`
- `data/audit/weak_labels_qwen36plus20260402.jsonl`

Five-model comparison outputs:

- `data/audit/weak_label_comparison_5models/weak_label_comparison_summary.json`
- `data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv`
- `data/audit/weak_label_comparison_5models/weak_label_pairwise_agreement.csv`
- `data/audit/weak_label_comparison_5models/weak_label_disagreement_cases.csv`

## Label Distribution

| Model | Faithful | Unfaithful | Insufficient | Mean confidence |
|---|---:|---:|---:|---:|
| `qwen3.6-max-preview` | 21 | 65 | 14 | 0.970 |
| `deepseek-v4-pro` | 29 | 66 | 5 | 0.948 |
| `kimi-k2.6` | 21 | 77 | 2 | 0.915 |
| `qwen3-max-2026-01-23` | 36 | 61 | 3 | 0.967 |
| `qwen3.6-plus-2026-04-02` | 22 | 62 | 16 | 0.940 |

Interpretation:

- `qwen3-max-2026-01-23` is the most permissive among the five, with 36 `faithful` labels.
- `kimi-k2.6` remains the strictest, with 77 `unfaithful` labels.
- `qwen3.6-plus-2026-04-02` uses `insufficient` even more often than `qwen3.6-max-preview`.
- High confidence remains common across models and labels, so confidence alone is still not a reliable audit signal.

## Five-Model Agreement

Across 100 audit items:

- Exact unanimous agreement: 58/100.
- Non-unanimous items: 42/100.
- All three label options appeared among the five models: 6/100.
- Mean top exact-label vote fraction: 0.872.
- Mean top binary vote fraction: 0.940.

Five-model majority exact labels:

- `unfaithful`: 72
- `faithful`: 23
- `insufficient`: 2
- tie: 3

Five-model binary majority labels:

- `nonfaithful`: 77
- `faithful`: 23

Approximate five-model binary majority agreement with benchmark gold labels is 0.61. This is not a final accuracy estimate because the audit protocol includes `insufficient` and the audit batch is risk-enriched.

## Pairwise Agreement

| Pair | Exact agreement | Exact kappa | Binary agreement | Binary kappa |
|---|---:|---:|---:|---:|
| `qwen3.6-max-preview` vs `deepseek-v4-pro` | 0.80 | 0.602 | 0.90 | 0.736 |
| `qwen3.6-max-preview` vs `kimi-k2.6` | 0.80 | 0.558 | 0.92 | 0.759 |
| `qwen3.6-max-preview` vs `qwen3-max-2026-01-23` | 0.72 | 0.465 | 0.85 | 0.642 |
| `qwen3.6-max-preview` vs `qwen3.6-plus-2026-04-02` | 0.84 | 0.697 | 0.97 | 0.911 |
| `deepseek-v4-pro` vs `kimi-k2.6` | 0.85 | 0.651 | 0.92 | 0.788 |
| `deepseek-v4-pro` vs `qwen3-max-2026-01-23` | 0.78 | 0.552 | 0.85 | 0.660 |
| `deepseek-v4-pro` vs `qwen3.6-plus-2026-04-02` | 0.83 | 0.672 | 0.91 | 0.765 |
| `kimi-k2.6` vs `qwen3-max-2026-01-23` | 0.80 | 0.560 | 0.83 | 0.594 |
| `kimi-k2.6` vs `qwen3.6-plus-2026-04-02` | 0.76 | 0.493 | 0.93 | 0.793 |
| `qwen3-max-2026-01-23` vs `qwen3.6-plus-2026-04-02` | 0.67 | 0.386 | 0.84 | 0.620 |

Interpretation:

- Adding more judges does not remove disagreement.
- Same-family Qwen models are not interchangeable. In particular, `qwen3-max-2026-01-23` and `qwen3.6-plus-2026-04-02` have only 0.67 exact agreement.
- `qwen3.6-max-preview` and `qwen3.6-plus-2026-04-02` have very high binary agreement (0.97) but still differ on exact treatment of `unfaithful` versus `insufficient`.
- Binary agreement is generally higher than exact agreement, confirming that many disagreements are about the boundary between unsupported/contradictory answers and insufficient/conflicted evidence.

## Stratified Findings

By dataset:

| Dataset | n | Exact unanimous rate | All label options used | Mean top-label vote fraction | Majority-vs-benchmark binary agreement |
|---|---:|---:|---:|---:|---:|
| RAGBench | 46 | 0.652 | 0.022 | 0.909 | 0.717 |
| RAGTruth | 16 | 0.750 | 0.000 | 0.950 | 0.500 |
| RAMDocs | 38 | 0.421 | 0.132 | 0.795 | 0.526 |

By audit stratum:

| Primary stratum | n | Exact unanimous rate | All label options used | Mean top-label vote fraction | Majority-vs-benchmark binary agreement |
|---|---:|---:|---:|---:|---:|
| coverage_fill | 12 | 1.000 | 0.000 | 1.000 | 0.667 |
| low_risk_control | 20 | 0.800 | 0.000 | 0.960 | 0.950 |
| model_majority_disagreement | 13 | 0.462 | 0.077 | 0.831 | 0.462 |
| ramdocs_instability | 8 | 0.250 | 0.250 | 0.750 | 0.625 |
| stable_shared_error | 22 | 0.364 | 0.136 | 0.755 | 0.045 |
| top_multi_risk | 25 | 0.560 | 0.000 | 0.904 | 0.880 |

Interpretation:

- RAMDocs remains the hardest dataset: lowest exact unanimous rate and highest rate of all label options being used.
- `stable_shared_error` is still the strongest evidence that model consensus can be misleading. Five-model majority agrees with benchmark binary labels on only 0.045 of this intentionally selected stratum.
- `low_risk_control` behaves cleanly, with high agreement and high benchmark alignment.
- `ramdocs_instability` becomes even clearer with five judges: only 0.25 exact unanimous rate.

## Implications for the Paper

This extension strengthens, rather than weakens, the paper's main claim:

1. Stronger or additional judges do not automatically make RAG faithfulness evaluation reliable.
2. Multi-judge voting should be treated as an audit feature, not as ground truth.
3. Same-family model variants can still disagree substantially, so model-family effects should be measured rather than assumed.
4. Exact verdict disagreement and issue/rationale disagreement are both useful signals for identifying unreliable verdicts.
5. The strongest empirical story remains selective audit and reliability diagnosis, especially under evidence conflict and entity ambiguity.

## Next Required Step

Human blind annotation is still required before we can make final claims about correctness against human adjudication. Once the 100 manual labels are complete, the next analysis should compare:

- human label vs benchmark gold,
- human label vs each weak model,
- human label vs 3-model majority,
- human label vs 5-model majority,
- human label vs reliability-risk strata.

That will tell us whether the proposed reliability signals actually predict human-reviewed judge failure.

## Caveats

- The 100-item batch is risk-enriched, so agreement rates are not population estimates.
- Benchmark gold labels are imperfect and do not include the `insufficient` class.
- Model rationales are self-reported explanations and should be used as diagnostic artifacts, not proof of internal causal reasoning.
