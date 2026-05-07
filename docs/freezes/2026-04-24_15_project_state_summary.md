# Freeze 15 - Project State Summary

Date: 2026-04-24

## One-Sentence Status

The project is worth continuing. We have reproducible evidence that RAG LLM-as-a-Judge verdicts are unreliable across perturbations and judge models, and that interpretable reliability features can prioritize audit/deferral better than random baselines. The strongest current story is audit prioritization, not aggressive confidence-interval narrowing.

## Current Refined Thesis

Do not claim:

> More perturbations or more judges automatically fix evaluation.

Claim instead:

> RAG faithfulness judges fail through multiple modes, including perturbation-unstable verdicts and stable high-confidence errors. A low-cost diagnostic framework can combine prompt/order perturbations, confidence, abstention, and multi-judge disagreement to prioritize human audit and selective deferral, while reporting conservative calibrated uncertainty.

## Frozen Documents

All current progress is archived in:

- `docs/freezes/2026-04-24_00_project_charter.md`
- `docs/freezes/2026-04-24_01_literature_review.md`
- `docs/freezes/2026-04-24_02_experiment_plan.md`
- `docs/freezes/2026-04-24_03_decision_log.md`
- `docs/freezes/2026-04-24_04_dataset_selection.md`
- `docs/freezes/2026-04-24_05_dataset_schema_check.md`
- `docs/freezes/2026-04-24_06_pilot_pipeline.md`
- `docs/freezes/2026-04-24_07_dashscope_smoke_results.md`
- `docs/freezes/2026-04-24_08_balanced_pilot30_results.md`
- `docs/freezes/2026-04-24_09_full_v2_pilot_results.md`
- `docs/freezes/2026-04-24_10_reliability_baselines.md`
- `docs/freezes/2026-04-24_11_next_experiments_and_publication_criteria.md`
- `docs/freezes/2026-04-24_12_validation_and_audit_calibration_results.md`
- `docs/freezes/2026-04-24_13_multi_judge_glm51_results.md`
- `docs/freezes/2026-04-24_14_multi_judge_risk_baselines.md`
- `docs/freezes/2026-04-24_15_project_state_summary.md`

This file is the current entry point for future conversations.

## Data And Pipeline Status

Datasets inspected and used:

- RAGBench
- RAGTruth
- RAMDocs

Deferred for later:

- `rag_conflicts`
- FRAMES

Pilot data:

- 150 samples total.
- 50 per dataset.
- 75 faithful, 75 unfaithful.
- 3 prompt variants.
- 3 evidence-order variants.
- 9 judgments per sample per judge model.

Judge models completed:

- Qwen3.5-Plus, no-thinking mode.
- GLM-5.1, no-thinking mode.

Both full runs are clean:

- 1350/1350 parsed JSON for Qwen.
- 1350/1350 parsed JSON for GLM.
- 0 API errors.
- 0 truncations.

## Experiment Map

### Experiment A - Dataset And Schema Feasibility

Question:

> Can we build a low-GPU RAG judge reliability benchmark from available data?

Status:

- Done.

Evidence:

- RAGBench, RAGTruth, RAMDocs loaded successfully.
- Unified sample schema built.
- Balanced 150-sample pilot constructed.

Conclusion:

- Feasible.

### Experiment B - Judge Unreliability Under Perturbation

Question:

> Are LLM judge verdicts unreliable under prompt/order perturbations?

Status:

- Done for Qwen and GLM.

Main evidence:

- Qwen majority-vote sample accuracy: 102/150 = 0.6800.
- GLM majority-vote sample accuracy: 101/150 = 0.6733.
- Qwen sample disagreement: 29/150 = 0.1933.
- GLM sample disagreement: 29/150 = 0.1933.

Dataset pattern:

- RAMDocs is the strongest instability source.
- RAGTruth mainly produces stable errors.

Conclusion:

- Strongly supported.

### Experiment C - Stable High-Confidence Error Mode

Question:

> Does majority voting fail because some errors are stable across perturbations?

Status:

- Done for Qwen; replicated qualitatively with GLM.

Main evidence:

- Qwen majority-wrong samples: 48/150.
- Qwen broader instability samples: 42/150.
- Qwen stable majority-wrong samples: 28/150.
- RAGTruth has 16/50 majority-wrong samples, but only 3/50 broader instability samples.

Conclusion:

- Strongly supported.
- This is central to the paper because it shows disagreement-only methods are insufficient.

### Experiment D - Reliability Risk Scoring

Question:

> Can cheap features predict unreliable majority verdicts?

Status:

- Done for Qwen and GLM.

Qwen:

- In-sample `risk_combined` AUROC: 0.6965.
- Stratified CV AUROC: 0.6965.
- Leave-one-dataset-out AUROC: 0.7118.

GLM:

- In-sample `risk_combined` AUROC: 0.6751.
- Stratified CV AUROC: 0.6768.
- Leave-one-dataset-out AUROC: 0.6543.

Conclusion:

- Supported.
- Strong enough for Short/Resource.
- Promising for Full, but still benefits from larger scale or human audit.

### Experiment E - Selective Audit And Deferral

Question:

> Does risk scoring help prioritize audit or defer unreliable samples?

Status:

- Done for Qwen.

Qwen risk_combined:

- Stratified CV top 20% audit lift: 1.70x random.
- LODO top 20% audit lift: 1.54x random.
- LODO 30% deferral retained accuracy gain: +8.19 points.
- LODO 40% deferral retained accuracy gain: +10.89 points.

Conclusion:

- Strongly supported.
- This is currently the best main result.

### Experiment F - Audit Calibration / Confidence Intervals

Question:

> Can small audit sets estimate overall judge accuracy with narrower intervals?

Status:

- Proxy simulation done using benchmark labels.

Main evidence:

- Random audit already gives reasonable coverage.
- Risk-stratified proportional audit improves mean CI width only slightly, about 1-5%.
- Risk oversampling is good for finding errors but worse for estimating population accuracy.
- PPI/control-variate with current simple risk prediction does not materially reduce CI width.

Conclusion:

- Mixed/weak.
- Use conservative calibrated intervals.
- Do not make CI-width reduction the central claim yet.

### Experiment G - Multi-Judge Robustness

Question:

> Does the phenomenon hold for another judge model?

Status:

- Done with GLM-5.1.

Evidence:

- GLM reproduces similar majority accuracy and disagreement.
- Qwen majority accuracy: 0.6800.
- GLM majority accuracy: 0.6733.
- Both have sample disagreement: 0.1933.

Conclusion:

- Supported.
- This strengthens the full-paper case.

### Experiment H - Multi-Judge Voting And Multi-Judge Risk

Question:

> Does adding another judge fix the problem, or mainly add audit signals?

Status:

- Done for Qwen + GLM.

Evidence:

- Combined 18-judgment majority accuracy: 0.6667, worse than Qwen alone.
- Both models wrong on 42/150 samples.
- Model-majority disagreement appears in 13/150 samples.
- For target `any_model_wrong`, `risk_multi_combined` AUROC: 0.7423.
- Top 20% multi-judge risk audit precision for `any_model_wrong`: 0.8000.
- Top 20% lift over random: 2.18x.

Conclusion:

- Multi-judge voting is not a solution.
- Multi-judge disagreement is a useful audit feature.

## What Current Experiments Can Already Say

Supported claims:

1. LLM-as-a-Judge for RAG faithfulness is not reliable enough to use blindly.
2. Prompt/order perturbations expose a non-trivial unstable verdict mode.
3. Stable high-confidence errors also exist and cannot be solved by disagreement alone.
4. Conflict-heavy evidence appears to increase instability.
5. Simple majority voting across perturbations is insufficient.
6. Simple majority voting across judge models is also insufficient.
7. Interpretable risk features beat disagreement-only and random audit baselines.
8. Multi-judge signals are useful for audit prioritization.

Current best evidence for publication:

- Qwen LODO AUROC: 0.7118.
- Qwen top 20% LODO audit lift: 1.54x.
- Qwen 30-40% LODO deferral improves retained accuracy by about 8-11 points.
- Multi-judge risk AUROC for `any_model_wrong`: 0.7423.
- Multi-judge top 20% audit precision: 0.8000.

Claims not yet strong enough:

1. Risk stratification dramatically narrows confidence intervals.
2. The method generalizes to many more datasets.
3. Human annotators confirm all benchmark-based error conclusions.
4. Learned predictors are better than interpretable hand-crafted risk.

## Is It Worth Continuing?

Yes.

Reasons:

- The core phenomenon is real and replicated across two judge models.
- The strongest result, audit prioritization, is already above the short/resource threshold and approaching full-paper quality.
- The negative findings are scientifically useful: voting alone fails, and calibration requires careful sampling.
- The project remains low-GPU and API-token based.

Current paper potential:

- Short/Resource: already plausible if packaged well with toolkit and clear analysis.
- Full paper: plausible but needs at least one of:
  - human audit sanity check,
  - larger sample size,
  - conflict-specific expansion,
  - stronger cross-dataset/multi-model validation,
  - better calibrated audit estimator.

## Recommended Next Steps

Priority 1:

- Human/proxy audit preparation.
- Select 100 examples:
  - top multi-judge risk,
  - stable shared errors,
  - RAMDocs conflict instability,
  - random low-risk controls.

Priority 2:

- Expand sample size from 150 to 300 or 600, still balanced by dataset/label.

Priority 3:

- Add conflict-specific experiment:
  - use RAMDocs deeper analysis,
  - optionally construct candidate answers from `rag_conflicts`.

Priority 4:

- Test one more model only if needed:
  - `glm-5`,
  - `deepseek-v4-pro`,
  - or another cheaper judge.

Priority 5:

- Start paper skeleton:
  - Introduction,
  - Related Work,
  - Method,
  - Experimental Protocol,
  - Pilot Results.

