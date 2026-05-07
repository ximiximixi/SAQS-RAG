# Freeze 26: Human Gold Audit and Current Experiment Analysis

Date: 2026-05-06

This freeze records the first complete human-gold audit result for the 100-item blind audit batch.

Important protocol record:

- The user declares the 100 annotations to be fully independent, double-blind, single-annotator golden labels.
- For this project state, `human_audit_annotations.csv/jsonl` is frozen as `HumanGold-v1`.
- The audit batch is risk-enriched, not an iid sample of all benchmark items. Reported accuracies are therefore audit-set accuracies, not population judge accuracies.
- Canonical reporting uses original English audit items and `data/audit/human_audit_annotations_en.csv`.
- Assisted model runs are not independent gold labels. They are weak-supervision/adjudication signals and should remain internal pilots unless rerun under the canonical input protocol.

## Frozen Artifacts

Human annotations:

- `data/audit/human_audit_annotations_en.csv`
- `data/audit/human_audit_annotations_en.jsonl`

Human-gold analysis outputs:

- `data/audit/human_gold_analysis/summary.json`
- `data/audit/human_gold_analysis/condition_summary_against_human_gold.csv`
- `data/audit/human_gold_analysis/per_item_key_condition_comparison.csv`
- `data/audit/human_gold_analysis/high_value_disagreement_cases.csv`
- `data/audit/human_gold_analysis/human_issue_category_counts.csv`
- `data/audit/human_gold_analysis/issue_overlap_against_human_gold.csv`
- `data/audit/human_gold_analysis/model_group_consensus_against_human_gold.csv`
- `data/audit/human_gold_analysis/per_item_model_group_consensus.csv`
- `data/audit/human_gold_analysis/condition_transition_summary_against_human.csv`
- `data/audit/human_gold_analysis/condition_transition_detail_against_human.csv`
- `data/audit/human_gold_analysis/paired_correctness_tests_against_human.csv`
- `data/audit/human_gold_analysis/risk_score_analysis_against_human.csv`

Reproducible analysis script:

- `scripts/analyze_human_gold_against_models.py`

Command:

```powershell
python .\scripts\analyze_human_gold_against_models.py --audit-dir .\data\audit --out-dir .\data\audit\human_gold_analysis
```

## Human Gold Validation

Coverage:

- Human rows: 100
- Unique audit IDs: 100
- Duplicates: 0
- Missing from metadata: 0
- Metadata items missing human label: 0

Human label distribution:

| Label | Count | Rate |
| --- | ---: | ---: |
| faithful | 22 | 22% |
| unfaithful | 78 | 78% |

Human confidence:

- Overall average: 0.906
- Faithful average: 0.968
- Unfaithful average: 0.888

Human issue categories:

| Issue category | Count | Rate |
| --- | ---: | ---: |
| unsupported_claim | 45 | 45% |
| entity_ambiguity | 25 | 25% |
| evidence_conflict | 22 | 22% |
| benchmark_ambiguous | 20 | 20% |
| contradiction | 20 | 20% |
| insufficient_evidence | 13 | 13% |
| numeric_error | 6 | 6% |
| over_specific_answer | 5 | 5% |
| answer_format_issue | 5 | 5% |
| temporal_conflict | 2 | 2% |

Quality note:

- Two faithful rows contain issue categories:
  - `AUDIT-028`: `insufficient_evidence`, because the answer correctly says the evidence does not directly support the queried claim.
  - `AUDIT-070`: `answer_format_issue`, because the answer is factually supported but answers a shifted/formatted version of the question.
- This is acceptable for `HumanGold-v1` if issue categories are treated as diagnostic tags rather than label-determining errors. If the paper later requires issue categories only for unfaithful examples, these two rows should be recoded in an explicit `HumanGold-v2`.

## Main Label Results Against Human Gold

Exact accuracy treats `tie` and `insufficient` predictions as not matching the human binary gold label. Covered accuracy ignores abstain/tie predictions.

| Condition | Prediction distribution | Exact acc. | 95% CI | Covered acc. | Main error pattern |
| --- | --- | ---: | --- | ---: | --- |
| Original benchmark gold/reference | 56 F / 44 U | 60% | [50.2, 69.1] | 60% | Strong over-faithful relative to strict human policy: 37 human-unfaithful items marked faithful |
| Pilot Qwen majority | 33 F / 67 U | 89% | [81.4, 93.7] | 89% | 11 human-unfaithful items marked faithful |
| Pilot GLM majority | 34 F / 66 U | 86% | [77.9, 91.5] | 86% | 13 human-unfaithful items marked faithful, 1 false alarm |
| Pilot Qwen+GLM combined majority | 30 F / 66 U / 4 tie | 86% | [77.9, 91.5] | 89.6% | Ties plus 9 human-unfaithful items marked faithful |
| Old weak 5-model majority | 23 F / 72 U / 3 tie / 2 insufficient | 92% | [85.0, 95.9] | 96.8% | Good covered performance; remaining failures include abstain/tie and two human-unfaithful items marked faithful |
| Strict independent 5-model majority | 20 F / 80 U | 96% | [90.2, 98.4] | 96% | Main strict result on canonical inputs: 3 human-faithful false alarms and 1 missed unfaithful item |
| Assisted-v1 3-model majority from old weak refs | 19 F / 81 U | 97% | [91.5, 99.0] | 97% | Internal assisted pilot; 3 errors, all human-faithful false alarms |
| Assisted-v2 3-model majority from strict refs | 15 F / 85 U | 93% | [86.3, 96.6] | 93% | Internal assisted pilot; 7 errors, all human-faithful false alarms |

Interpretation:

- The original benchmark/reference labels align poorly with `HumanGold-v1` on this risk-enriched set. This supports the paper premise that benchmark labels and judge labels can embed different faithfulness policies.
- Old weak 5-model majority is surprisingly strong against human gold, especially when abstentions/ties are excluded.
- Strict independent prompting is strong under the canonical English-input protocol, but it still produces a small number of false alarms and one missed unfaithful item.
- Assisted adjudication with multiple prior opinions can be very strong, but it must be described as a separate assisted-review mechanism, not as independent judging.

## Individual Model Results

Old weak prompt, five models:

| Model | Exact acc. | Prediction distribution | Notes |
| --- | ---: | --- | --- |
| qwen3.6-max-preview | 86% | 21 F / 65 U / 14 insufficient | Binary covered predictions all matched human; cost is high abstention |
| deepseek-v4-pro | 86% | 29 F / 66 U / 5 insufficient | Moderate over-faithful tendency |
| kimi-k2.6 | 91% | 21 F / 77 U / 2 insufficient | Best old weak individual model |
| qwen3-max-2026-01-23 | 83% | 36 F / 61 U / 3 insufficient | Most over-faithful among old weak models |
| qwen3.6-plus-2026-04-02 | 82% | 22 F / 62 U / 16 insufficient | High abstention |

Strict independent prompt, five models:

| Model | Exact acc. | Prediction distribution |
| --- | ---: | --- |
| qwen3.6-max-preview | 88% | 18 F / 82 U |
| deepseek-v4-pro | 89% | 19 F / 81 U |
| kimi-k2.6 | 87% | 11 F / 89 U |
| qwen3-max-2026-01-23 | 86% | 24 F / 76 U |
| qwen3.6-plus-2026-04-02 | 91% | 23 F / 77 U |

Assisted-v1, three models using old weak references:

| Model | Exact acc. | Prediction distribution |
| --- | ---: | --- |
| deepseek-v4-pro | 96% | 18 F / 82 U |
| qwen3.5-plus-2026-04-20 | 96% | 18 F / 82 U |
| qwen3.6-max-preview | 97% | 19 F / 81 U |

Assisted-v2, three models using strict independent references:

| Model | Exact acc. | Prediction distribution |
| --- | ---: | --- |
| deepseek-v4-pro | 89% | 11 F / 89 U |
| qwen3.5-plus-2026-04-20 | 94% | 16 F / 84 U |
| qwen3.6-max-preview | 93% | 15 F / 85 U |

## Agreement Is Not Reliability

Group consensus against human gold:

| Group | Majority acc. | Unanimous items | Unanimous acc. | Unanimous wrong |
| --- | ---: | ---: | ---: | ---: |
| Old weak 5 models | 92% | 58 | 100% | 0 |
| Strict independent 5 models | 96% | 86 | 97.7% | 2 |
| Assisted-v1 3 models | 97% | 98 | 96.9% | 3 |
| Assisted-v2 3 models | 93% | 95 | 93.7% | 6 |

Interpretation:

- Agreement is useful but not sufficient.
- Old weak unanimity is very reliable on this batch, but strict/assisted unanimity can still be confidently wrong because the models share the same strict-policy bias.
- This directly supports the proposed paper claim that judge reliability should be calibrated/audited, not inferred from raw model agreement alone.

## Paired Condition Tests

Paired correctness comparisons use the same 100 audit items. The p-value is a two-sided exact McNemar/binomial test over items where exactly one condition is correct.

| Pair | A-only correct | B-only correct | Both correct | Both wrong/abstain | p |
| --- | ---: | ---: | ---: | ---: | ---: |
| Benchmark reference -> old weak majority | 1 | 33 | 59 | 7 | 4.07e-09 |
| Pilot Qwen majority -> old weak majority | 7 | 10 | 82 | 1 | 0.629 |
| Pilot GLM majority -> old weak majority | 5 | 11 | 81 | 3 | 0.210 |
| Old weak majority -> strict independent majority | 9 | 7 | 83 | 1 | 0.804 |
| Strict independent majority -> assisted-v1 majority | 1 | 8 | 89 | 2 | 0.039 |
| Strict independent majority -> assisted-v2 majority | 3 | 6 | 87 | 4 | 0.508 |
| Assisted-v1 majority -> assisted-v2 majority | 4 | 0 | 93 | 3 | 0.125 |

Interpretation:

- The benchmark reference is significantly misaligned with human strict audit on this risk-enriched batch.
- Old weak majority and strict independent majority have different error types; the strict independent majority is the current canonical main judge condition.
- Assisted-v1 improves over strict independent at nominal p < 0.05, but this result should be treated as pilot evidence because the audit set is small and risk-enriched.

## Dataset and Stratum Breakdown

Dataset breakdown:

| Dataset | n | Human unfaithful rate | Benchmark acc. | Old weak majority acc. | Strict independent acc. | Assisted-v1 acc. | Assisted-v2 acc. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RAGBench | 46 | 63.0% | 73.9% | 95.7% | 80.4% | 97.8% | 91.3% |
| RAGTruth | 16 | 81.3% | 50.0% | 100.0% | 100.0% | 93.8% | 87.5% |
| RAMDocs | 38 | 94.7% | 47.4% | 84.2% | 97.4% | 97.4% | 97.4% |

Primary stratum breakdown:

| Stratum | n | Human unfaithful rate | Benchmark acc. | Old weak majority acc. | Strict independent acc. | Assisted-v1 acc. | Assisted-v2 acc. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| coverage_fill | 12 | 91.7% | 66.7% | 100.0% | 100.0% | 100.0% | 91.7% |
| low_risk_control | 20 | 25.0% | 95.0% | 100.0% | 85.0% | 95.0% | 85.0% |
| model_majority_disagreement | 13 | 92.3% | 46.2% | 84.6% | 92.3% | 92.3% | 92.3% |
| ramdocs_instability | 8 | 87.5% | 62.5% | 87.5% | 87.5% | 87.5% | 87.5% |
| stable_shared_error | 22 | 90.9% | 0.0% | 77.3% | 81.8% | 100.0% | 95.5% |
| top_multi_risk | 25 | 92.0% | 88.0% | 100.0% | 96.0% | 100.0% | 100.0% |

Interpretation:

- The audit sampler successfully enriched difficult cases: all non-control strata have very high human-unfaithful rates.
- The low-risk control stratum behaves differently: most items remain faithful, and strict/assisted-v2 methods over-flag some of them.
- `stable_shared_error` is especially important: original benchmark/reference labels are 0% aligned with strict human gold in this stratum, which strongly motivates human audit and policy-aware relabeling. This should be described as policy misalignment under our strict audit standard, not automatically as benchmark error under the benchmark's original standard.

## Risk Score Analysis

Risk scores are evaluated on the selected audit batch, so these numbers are diagnostic rather than unbiased population estimates.

Key results:

| Target | Best/important score | AUROC | Top-20% precision | Lift |
| --- | --- | ---: | ---: | ---: |
| Human unfaithful | risk_qwen_combined | 0.876 | 0.95 | 1.22 |
| Human unfaithful | risk_multi_combined | 0.811 | 0.95 | 1.22 |
| Benchmark mismatch vs human | risk_qwen_combined | 0.751 | 0.80 | 2.00 |
| Pilot Qwen wrong vs human | per_task_binary_disagreement_rate | 0.794 | 0.35 | 3.18 |
| Pilot GLM wrong vs human | per_task_binary_disagreement_rate | 0.798 | 0.40 | 2.86 |
| Old weak majority wrong/abstain vs human | risk_multi_combined | 0.851 | 0.25 | 3.13 |
| Strict independent majority wrong vs human | per_task_binary_disagreement_rate | 0.546 | 0.10 | 1.00 |
| Assisted-v1 majority wrong vs human | per_task_binary_disagreement_rate | 0.646 | 0.05 | 1.67 |
| Assisted-v2 majority wrong vs human | per_task_binary_disagreement_rate | 0.504 | 0.05 | 0.71 |

Interpretation:

- Existing risk features are useful for finding human-unfaithful cases, benchmark-policy mismatches, and old/pilot judge failures.
- The same risk features do not predict strict/assisted false positives well. Those later errors are mostly over-strict faithful-to-unfaithful false alarms, especially in lower-risk/control-like items.
- This gives a better paper story than a single universal risk score: different judge protocols have different failure modes, so an auditable system should estimate protocol-specific unreliability.

## High-Value Case Studies

Representative cases already identified in `high_value_disagreement_cases.csv`:

- `AUDIT-001`: People’s University entity ambiguity. Human marks unfaithful because the answer picks 1913 while evidence contains multiple "People's University" entities.
- `AUDIT-003`: "I Will Follow" title/entity ambiguity. Human marks unfaithful because the answer picks Bono while evidence also contains other plausible works/entities.
- `AUDIT-036`: Kevin Lewis same-name/date conflict. Human marks unfaithful due multiple entities and conflicting birth dates.
- `AUDIT-050`: first transatlantic flight vs first nonstop transatlantic flight. Human marks unfaithful because the answer shifts the question and introduces a more specific unsupported claim.
- `AUDIT-009`: human faithful but most model conditions mark unfaithful. This is a valuable false-positive case for analyzing over-strict judge behavior.
- `AUDIT-029`, `AUDIT-040`, `AUDIT-070`, `AUDIT-073`, `AUDIT-081`, `AUDIT-095`: human faithful but strict/assisted-v2 tends to over-flag; these are useful for the "strictness can create false alarms" section.

## Current Scientific Takeaways

The idea remains viable and is now stronger, but the claim should be sharpened:

1. RAG judge labels are not only model-dependent; they are policy-dependent.
2. Explicit strict faithfulness definitions substantially change verdict distributions, but do not automatically improve agreement with human gold.
3. Multi-model agreement can be reliable in some settings and misleading in others due to correlated prompt-policy bias.
4. Evidence conflict, entity ambiguity, unsupported claims, and benchmark ambiguity dominate the human-unfaithful cases in the current audit set.
5. Existing risk features can prioritize high-yield human audits, especially for benchmark mismatch and old/pilot judge failure.
6. A publishable framework should calibrate per protocol and per failure mode rather than claiming one risk score solves all judge unreliability.

## Publication Readiness Assessment

Current status: promising pilot, not yet final-submission ready.

What is already strong:

- A complete 100-item independent human-gold audit exists.
- The human gold strongly supports the premise that conflict/ambiguity-sensitive RAG evaluation needs explicit policy and audit.
- There are multiple model protocols, multiple model families, and reproducible outputs.
- Risk-enriched sampling is clearly useful for finding problematic cases.
- We have concrete case studies and quantitative error-mode evidence.

What is still needed for a CIKM-level submission:

- Rerun assisted adjudication under the canonical English-input protocol if assisted adjudication remains in the main paper.
- Add at least a small second-annotator or adjudication subset if possible, even 30-50 examples, to report inter-annotator agreement. If not possible, call it a single-expert audit.
- Expand beyond 100 items or add a second 100-item confirmatory batch to reduce pilot-set uncertainty.
- Build the final reliability model using human gold targets, not only benchmark-derived wrongness.
- Evaluate calibration: reliability bins, confidence intervals, top-k audit precision, and possibly conformal/audit-based intervals.
- Decide final taxonomy treatment for faithful rows with issue tags.

Frozen conclusion:

The project should continue. The best paper angle is not "strict prompting improves LLM-as-judge", because current data does not support that as a universal claim. The best angle is "LLM-as-judge verdicts for RAG faithfulness are unstable under implicit evaluation policy; evidence conflict and ambiguity produce systematic failures; a low-cost audit/calibration layer can identify when verdicts are likely unreliable and when human review is most valuable."
