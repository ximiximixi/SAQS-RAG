# Freeze 11 - Next Experiments And Publication Criteria

Date: 2026-04-24

## Purpose

This document freezes the next experimental plan before we inspect more results.

The goal is to avoid post-hoc storytelling. We will treat the criteria below as the decision standard for whether the current idea is strong enough for a CIKM-style submission.

Working title:

> Calibrated LLM-as-a-Judge for RAG Evaluation: Predicting and Auditing Unreliable Verdicts under Evidence Conflict

Current baseline:

- Full v2 pilot has 150 samples and 1350 Qwen3.5-Plus judge calls.
- Run integrity is clean: 1350/1350 parsed, 0 API errors, 0 truncations.
- Majority-vote sample accuracy is 68.0%.
- Sample disagreement is 19.33%.
- Combined risk score AUC for majority-wrong prediction is 0.6965 on the same pilot.

The next phase must test whether this signal generalizes, improves audit efficiency, and supports calibrated evaluation.

## Core Claim To Validate

The paper should not claim that disagreement alone solves judge unreliability.

The refined claim is:

> LLM-as-a-Judge for RAG faithfulness fails through multiple modes, including perturbation-unstable verdicts and stable high-confidence errors. A low-cost reliability framework can combine perturbation, confidence, and abstention signals to prioritize human audit and report calibrated evaluation scores with uncertainty.

## Experiment 1 - Held-Out Reliability Prediction

Question:

> Can judge-output features predict which sample-level majority verdicts are wrong?

Data:

- Start with full v2 pilot: 150 samples.
- Then expand to a larger balanced set if token budget allows: recommended 300 or 600 samples.

Target labels:

- Primary: `majority_wrong`, whether the majority judge verdict disagrees with the benchmark label.
- Secondary: `judgment_wrong_rate`, fraction of the 9 perturbed judgments that are wrong.

Features:

- vote counts,
- binary vote entropy,
- majority margin,
- prompt flip count,
- order flip count,
- insufficient rate,
- confidence mean/min/std,
- dataset id as an optional analysis factor, not as the main deployable feature.

Validation protocols:

1. Random stratified split by dataset and gold label.
2. Leave-one-dataset-out validation:
   - train/tune on two datasets,
   - evaluate on the held-out dataset.
3. No threshold tuning on test folds.

Baselines:

- random audit,
- disagreement-only,
- confidence-only,
- majority-margin-only,
- vote entropy,
- hand-composed combined risk,
- simple learned model if sample size permits, e.g. logistic regression or shallow tree.

Metrics:

- AUROC for `majority_wrong`,
- AUPRC because majority errors are not 50/50 in all subsets,
- top-k audit precision/recall at 10%, 20%, 30%, 40% audit budgets,
- retained accuracy after deferring top-risk samples.

Minimum publishable signal:

- Combined or learned risk score AUROC >= 0.65 on held-out evaluation.
- Top 20% audit lift over random >= 1.4.
- Retained accuracy improves by at least 5 absolute points after deferring top 20-30% risk samples.

Strong full-paper signal:

- AUROC >= 0.70 overall and >= 0.60 on at least two of three leave-one-dataset-out tests.
- Top 20% audit captures at least 35% of majority errors.
- Retained accuracy improves by 8-12 absolute points at a practical deferral budget.

Failure interpretation:

- If AUROC collapses under leave-one-dataset-out, we should frame this as a limitation and pivot toward dataset-specific auditing or short/resource paper.
- If only confidence works, the novelty weakens; we need stronger conflict/order analysis.
- If disagreement alone matches combined risk, simplify the method and focus on perturbation diagnostics.

## Experiment 2 - Selective Evaluation And Deferral Curves

Question:

> If the framework abstains or routes high-risk samples to audit, does the remaining automatic evaluation become more trustworthy?

Procedure:

1. Rank samples by risk.
2. Defer top-risk k% samples.
3. Compute retained-sample majority accuracy and retained coverage.
4. Compare against random deferral and single-signal deferral.

Budgets:

- k = 5%, 10%, 20%, 30%, 40%.

Metrics:

- retained accuracy,
- coverage,
- error reduction,
- area under risk-coverage curve,
- audit precision.

Minimum publishable signal:

- Risk-based deferral beats random deferral at most budgets.
- At 20-30% deferral, retained accuracy improves by at least 5 absolute points.

Strong full-paper signal:

- Risk-based deferral consistently dominates all single-signal baselines.
- At 30-40% deferral, retained accuracy approaches or exceeds 80% on the current judge setup.

Failure interpretation:

- If retained accuracy does not improve, reliability prediction is too weak. The paper should pivot to empirical diagnosis rather than calibration framework.

## Experiment 3 - Audit-Efficient Calibration

Question:

> Can a small human audit set produce a calibrated estimate of judge accuracy or RAG system quality with useful uncertainty intervals?

Initial proxy:

- Use benchmark labels as simulated human audit labels.

Later human audit:

- Manually audit 100-300 examples if time permits.
- Prioritize high-risk strata plus a random control stratum.

Methods:

- random audit baseline,
- risk-stratified audit,
- Neyman allocation by risk strata,
- bootstrap confidence intervals,
- prediction-powered inference style estimator if we have enough audited labels,
- optional conformal risk control for selective evaluation.

Risk strata:

- low risk,
- medium risk,
- high risk,
- optionally stable-high-confidence-wrong candidate stratum.

Metrics:

- estimate bias against full benchmark labels,
- confidence interval width,
- empirical coverage in bootstrap simulations,
- number of audited samples required to reach a target interval width.

Minimum publishable signal:

- Risk-stratified audit has lower error or narrower intervals than random audit at the same budget.
- At audit budget 100-150, estimated majority accuracy is within about +/-5 percentage points of the full-label estimate in repeated simulations.

Strong full-paper signal:

- Risk-stratified or PPI-style estimator reduces CI width by 25-40% over random audit at the same budget.
- Bootstrap coverage is close to nominal 95%.
- The method gives actionable intervals for dataset-level RAG evaluation.

Failure interpretation:

- If stratification does not improve estimation, keep audit calibration as a conservative reporting layer and emphasize reliability prediction/diagnosis instead.

## Experiment 4 - Evidence Conflict Analysis

Question:

> Are conflict-heavy examples more likely to induce unreliable judge verdicts?

Data:

- RAMDocs as current conflict-heavy set.
- Later add `rag_conflicts` if we construct candidate answers and labels.
- Optionally add adversarial evidence insertion:
  - original evidence,
  - contradictory evidence inserted,
  - outdated evidence inserted,
  - irrelevant distractor inserted.

Metrics:

- disagreement rate,
- order flip rate,
- prompt flip rate,
- majority error rate,
- risk score distribution,
- qualitative error categories.

Minimum publishable signal:

- Conflict-heavy or conflict-injected examples have clearly higher instability or error than non-conflict examples.
- Difference should be visible with confidence intervals or bootstrap tests.

Strong full-paper signal:

- Conflict condition increases disagreement/error by at least 10 absolute points.
- Risk score identifies conflict-induced unreliable verdicts better than confidence-only or disagreement-only baselines.

Failure interpretation:

- If conflict is not a major driver, revise title to remove "under Evidence Conflict" and focus on general RAG judge calibration.

## Experiment 5 - Multi-Judge Robustness

Question:

> Does the reliability framework generalize beyond one judge model?

Current model:

- Qwen3.5-Plus through DashScope.

Add if budget permits:

- a cheaper Qwen model,
- one OpenAI-compatible alternative,
- one stronger model for a small subset.

Design:

- run the same v2 protocol on a shared subset,
- compare error modes,
- add model-disagreement as another reliability feature.

Minimum publishable signal:

- At least two judge models show non-trivial unreliability.
- Risk features remain useful for at least one held-out model or multi-model setting.

Strong full-paper signal:

- Cross-model disagreement improves audit prioritization.
- The same framework works across judge models without model-specific prompts.

Failure interpretation:

- If the phenomenon is model-specific, paper should explicitly limit claims to the tested judge class.

## Experiment 6 - Human Audit Sanity Check

Question:

> Are benchmark labels and our judge criteria aligned enough to support scientific conclusions?

Why needed:

- Some stable-wrong cases may be benchmark-label noise or stricter judge criteria.
- Human audit is important for credibility.

Plan:

- Audit 100 examples if time is tight.
- Audit 200-300 examples if feasible.
- Sample composition:
  - high-risk predicted errors,
  - stable-high-confidence majority errors,
  - random low-risk controls,
  - conflict-heavy RAMDocs examples.

Annotation output:

- faithful / unfaithful / insufficient,
- claim-level notes if feasible,
- reason category:
  - unsupported addition,
  - contradiction,
  - evidence conflict,
  - ambiguous benchmark label,
  - judge over-strictness,
  - answer formatting issue.

Minimum publishable signal:

- Human audit confirms that a meaningful fraction of predicted high-risk samples are genuinely problematic.
- Human audit identifies at least two recurring error mechanisms.

Strong full-paper signal:

- Human labels validate the risk score's top-k precision.
- Human audit resolves stable-wrong cases into clear categories and strengthens the discussion.

Failure interpretation:

- If many benchmark labels are questionable, reframe paper around "auditing benchmark and judge disagreement" rather than pure judge error prediction.

## Required Baselines For A Credible Submission

The final paper should include:

1. Single judge, no perturbation.
2. Majority vote across perturbations.
3. Disagreement-only risk.
4. Confidence-only risk.
5. Entropy/margin risk.
6. Combined interpretable risk.
7. Learned lightweight predictor if data size permits.
8. Random audit.
9. Risk-stratified audit.

## Required Statistical Reporting

The final paper should report:

- exact sample counts,
- dataset-level breakdowns,
- Wilson or bootstrap confidence intervals,
- held-out or leave-one-dataset-out validation,
- ablation of feature groups,
- sensitivity to prompt/order perturbation,
- cost in tokens and latency,
- failure cases and qualitative examples.

## Publication Bar

### Minimum For A Short Or Resource Paper

The work is likely defensible as a CIKM Short/Resource-style paper if:

- there is a clean reproducible toolkit,
- at least 2-3 datasets are evaluated,
- judge unreliability is clearly demonstrated,
- risk-based audit beats random audit,
- confidence intervals are reported,
- claims are modest and scoped.

Suggested target numbers:

- held-out AUROC >= 0.65,
- top 20% audit lift >= 1.4,
- retained accuracy improvement >= 5 absolute points,
- at least 100 human/proxy-audit examples,
- all scripts/prompts/results reproducible.

### Stronger Bar For A Full Research Paper

The work becomes more competitive as a full research paper if:

- at least 3-5 datasets are included,
- at least 2 judge models are tested,
- held-out or cross-dataset results remain positive,
- audit calibration gives useful uncertainty intervals,
- human audit validates key claims,
- method beats disagreement-only and confidence-only baselines.

Suggested target numbers:

- overall held-out AUROC >= 0.70,
- leave-one-dataset-out AUROC >= 0.60 on most held-out datasets,
- top 20% audit captures >= 35% of majority errors,
- top-risk audit precision is at least 1.5x random,
- retained accuracy improves by 8-12 absolute points,
- calibration/audit estimator reduces CI width by 25-40% vs random audit,
- conflict-heavy condition increases instability or error by >= 10 absolute points.

## Go / No-Go Rules

Go for Full Paper:

- reliability prediction generalizes,
- audit/calibration gives clear benefit,
- conflict or stable-error analysis yields a distinctive story,
- human audit supports benchmark-based findings.

Go for Short/Resource:

- toolkit and diagnostic analysis are solid,
- reliability prediction is moderate but useful,
- human audit is small or absent,
- cross-model experiments are limited.

Pivot:

- if held-out risk prediction falls near random,
- if human audit contradicts benchmark-based conclusions,
- if all benefits disappear outside one dataset.

In that case, pivot to:

- empirical study of RAG judge failure modes,
- benchmark-label auditing,
- resource/toolkit paper,
- conflict-specific judge stress-test benchmark.

