# Freeze 17: Three-Model Weak Supervision for Human Audit Batch

Date: 2026-04-24

## Purpose

While the human audit UI is being used for blind annotation, we generated three independent large-model audit label files for the same 100-item blind audit batch. These labels are used only as weak supervision and pre-review signals, not as ground truth.

Models:

- `qwen3.6-max-preview`
- `deepseek-v4-pro`
- `kimi-k2.6`

All calls used the existing OpenAI-compatible DashScope endpoint configured in `.env`, with thinking disabled (`enable_thinking=false`). The API key is intentionally not recorded here.

## Inputs

- Blind audit batch: `data/audit/human_audit_batch_100_blind.jsonl`
- Hidden research metadata: `data/audit/human_audit_batch_100_metadata.csv`
- Audit protocol: strict JSON with labels `faithful`, `unfaithful`, `insufficient`

The hidden metadata was used only after model labeling for stratified research analysis. It was not injected into the model prompts.

## Scripts

- Generation script: `scripts/run_audit_model_labels.py`
- Comparison script: `scripts/compare_audit_model_labels.py`

## Generated Model Labels

All three models completed 100/100 items with 0 API failures and 100% JSON parse success.

Outputs:

- `data/audit/weak_labels_qwen36maxpreview.csv`
- `data/audit/weak_labels_qwen36maxpreview.jsonl`
- `data/audit/weak_labels_deepseekv4pro.csv`
- `data/audit/weak_labels_deepseekv4pro.jsonl`
- `data/audit/weak_labels_kimik26.csv`
- `data/audit/weak_labels_kimik26.jsonl`

## Comparison Outputs

- `data/audit/weak_label_comparison/weak_label_comparison_summary.json`
- `data/audit/weak_label_comparison/weak_label_comparison_by_item.csv`
- `data/audit/weak_label_comparison/weak_label_pairwise_agreement.csv`
- `data/audit/weak_label_comparison/weak_label_disagreement_cases.csv`

## Label Distribution

| Model | Faithful | Unfaithful | Insufficient | Mean confidence |
|---|---:|---:|---:|---:|
| `qwen3.6-max-preview` | 21 | 65 | 14 | 0.970 |
| `deepseek-v4-pro` | 29 | 66 | 5 | 0.948 |
| `kimi-k2.6` | 21 | 77 | 2 | 0.915 |

Interpretation:

- `deepseek-v4-pro` is the most permissive among the three, producing the most `faithful` labels.
- `kimi-k2.6` is the strictest, producing the most `unfaithful` labels.
- `qwen3.6-max-preview` uses `insufficient` much more often, especially when the evidence contains entity ambiguity.
- Confidence is high across models, so high model confidence alone is not a sufficient reliability signal.

## Pairwise Agreement

| Pair | Exact agreement | Exact Cohen kappa | Binary agreement | Binary Cohen kappa |
|---|---:|---:|---:|---:|
| Qwen vs DeepSeek | 0.80 | 0.602 | 0.90 | 0.736 |
| Qwen vs Kimi | 0.80 | 0.558 | 0.92 | 0.759 |
| DeepSeek vs Kimi | 0.85 | 0.651 | 0.92 | 0.788 |

Binary agreement maps `unfaithful` and `insufficient` into `nonfaithful`.

Interpretation:

- Exact agreement is moderate to strong but far from perfect.
- A large fraction of apparent disagreements are about whether to call a case `unfaithful` versus `insufficient`.
- Binary agreement is higher, but still leaves 8-10% model-pair disagreement on only 100 audit items.

## Three-Way Agreement

Across 100 audit items:

- 73 items: all three models gave the same exact label.
- 26 items: two models agreed and one model disagreed.
- 1 item: all three models gave different labels.

Three-model majority labels:

- `unfaithful`: 73
- `faithful`: 24
- `insufficient`: 2
- all-different/tie: 1

Binary majority labels:

- `nonfaithful`: 76
- `faithful`: 24

Approximate comparison to benchmark gold labels gives 0.62 binary agreement. This should not be treated as final accuracy because the audit protocol includes `insufficient`, while benchmark gold labels are only faithful/unfaithful and may contain their own noise.

## Reason and Issue Overlap

Top issue categories:

- Qwen: `unsupported_claim` 46, `contradiction` 22, `entity_ambiguity` 14, `evidence_conflict` 11
- DeepSeek: `unsupported_claim` 37, `evidence_conflict` 24, `contradiction` 15, `entity_ambiguity` 12, `numeric_error` 8
- Kimi: `unsupported_claim` 58, `contradiction` 29, `evidence_conflict` 23, `numeric_error` 11, `over_specific_answer` 10

Mean pairwise issue-category Jaccard is around 0.59-0.61. Mean pairwise reason-token Jaccard is around 0.29-0.33.

Interpretation:

- Models often agree on the final label while emphasizing different failure modes.
- Reason-level auditing is useful because label agreement alone hides different causal diagnoses.
- Kimi tends to frame more cases as unsupported/contradictory; Qwen is more likely to frame ambiguous evidence as insufficient.

## Stratified Findings

By dataset:

| Dataset | n | Unanimous exact rate | All-three-different rate | Majority-vs-benchmark binary agreement |
|---|---:|---:|---:|---:|
| RAGBench | 46 | 0.804 | 0.000 | 0.717 |
| RAGTruth | 16 | 0.875 | 0.000 | 0.500 |
| RAMDocs | 38 | 0.579 | 0.026 | 0.553 |

RAMDocs is again the most unstable source, consistent with the earlier perturbation and multi-judge analyses.

By audit stratum:

| Primary stratum | n | Unanimous exact rate | Majority-vs-benchmark binary agreement |
|---|---:|---:|---:|
| low_risk_control | 20 | 0.800 | 0.950 |
| top_multi_risk | 25 | 0.920 | 0.880 |
| model_majority_disagreement | 13 | 0.615 | 0.462 |
| ramdocs_instability | 8 | 0.500 | 0.625 |
| stable_shared_error | 22 | 0.455 | 0.091 |
| coverage_fill | 12 | 1.000 | 0.667 |

Interpretation:

- Low-risk controls behave as expected: high agreement and high alignment with benchmark labels.
- `model_majority_disagreement`, `ramdocs_instability`, and `stable_shared_error` expose the cases where judge behavior is least reliable.
- `stable_shared_error` remains especially important: multiple strong judges can confidently converge on labels that disagree with benchmark gold. This supports the paper's claim that multi-model voting is useful for diagnostics but not sufficient as ground truth.

## Example: All Three Models Disagree

`AUDIT-036`, dataset `ramdocs`, stratum `ramdocs_instability`, benchmark gold `faithful`.

- Qwen: `insufficient`, citing multiple Kevin Lewis entities/birth dates.
- DeepSeek: `faithful`, relying on one evidence passage that directly states the answer.
- Kimi: `unfaithful`, citing conflicting birth dates across evidence passages.

This is a strong paper example because it combines entity ambiguity, evidence conflict, and selective reliance on a single supporting passage. The same sample can be read as faithful, unfaithful, or insufficient depending on the judge's conflict-resolution policy.

## Implications for the Paper

This round strengthens the core hypothesis:

1. Judge unreliability is sample-dependent and concentrated in identifiable strata.
2. More capable judges do not eliminate disagreement under evidence conflict.
3. Multi-judge labels are valuable as reliability features and audit-prioritization signals, but they should not be treated as automatic ground truth.
4. The framework should explicitly model both verdict disagreement and rationale/issue disagreement.

The current evidence supports continuing. The next scientifically important step is to integrate the human audit labels after blind annotation finishes, then test whether the proposed reliability score predicts disagreement with human adjudication better than simple confidence, model voting, or raw benchmark labels.

## Caveats

- The 100-item audit batch is intentionally risk-enriched, so rates are not population estimates.
- Benchmark gold comparison is approximate because benchmark labels do not include `insufficient`.
- Model reasons are useful diagnostics but should be interpreted as self-reported rationales, not guaranteed causal explanations.
- Human labels are not yet integrated in this freeze.
