# Freeze 12 - Validation And Audit Calibration Results

Date: 2026-04-24

## Purpose

This freeze records the first held-out validation and audit-calibration simulations after Freeze 11.

The goal was to test whether the full v2 pilot signal survives more rigorous evaluation:

1. held-out reliability prediction,
2. leave-one-dataset-out validation,
3. selective deferral/audit curves,
4. proxy audit calibration for estimating majority-vote accuracy.

## Inputs

Feature table:

- `data/pilot/reliability_full_v2_qwen35plus_nothink/sample_reliability_features.csv`

Scripts:

- `scripts/validate_reliability.py`
- `scripts/audit_calibration_simulation.py`

Outputs:

- `data/pilot/validation_full_v2_qwen35plus_nothink/`
- `data/pilot/audit_calibration_full_v2_qwen35plus_nothink/`

## Experiment 1 - Held-Out Reliability Prediction

Target:

- `majority_wrong`, i.e. whether the sample-level majority verdict is wrong.

Validation:

- 20 repeats of 5-fold stratified CV.
- Leave-one-dataset-out (LODO), holding out RAGBench, RAGTruth, or RAMDocs.

### Stratified CV Results

| Risk score | Mean AUROC | Std AUROC | Mean AUPRC |
|---|---:|---:|---:|
| `risk_combined` | 0.6965 | 0.0790 | 0.5881 |
| `risk_low_confidence` | 0.6797 | 0.0808 | 0.5225 |
| `logistic_features` | 0.6731 | 0.0856 | 0.5506 |
| `risk_instability` | 0.6560 | 0.0953 | 0.5699 |
| `risk_disagreement` | 0.5876 | 0.0726 | 0.4287 |

Interpretation:

- `risk_combined` is the strongest CV signal.
- It is just below the full-paper target AUROC of 0.70, but above the short/resource threshold of 0.65.
- The simple logistic baseline is not better than the interpretable hand-composed risk score at this sample size.

### Leave-One-Dataset-Out Results

Mean over held-out datasets:

| Risk score | Mean AUROC | Std AUROC | Mean AUPRC |
|---|---:|---:|---:|
| `risk_combined` | 0.7118 | 0.0466 | 0.5663 |
| `risk_low_confidence` | 0.6773 | 0.0642 | 0.5272 |
| `risk_instability` | 0.6553 | 0.0991 | 0.5198 |
| `logistic_features` | 0.5833 | 0.0311 | 0.4541 |
| `risk_disagreement` | 0.5781 | 0.0442 | 0.4618 |

Per held-out dataset for `risk_combined`:

| Held-out dataset | Error rate | AUROC | AUPRC |
|---|---:|---:|---:|
| RAGBench | 0.26 | 0.6767 | 0.4926 |
| RAGTruth | 0.32 | 0.6811 | 0.5264 |
| RAMDocs | 0.38 | 0.7776 | 0.6799 |

Interpretation:

- The signal generalizes best to RAMDocs, consistent with conflict-heavy instability.
- It remains above 0.67 AUROC for RAGBench and RAGTruth.
- This meets the Freeze 11 full-paper criterion of LODO AUROC >= 0.60 on most held-out datasets.

## Experiment 2 - Selective Deferral And Audit Curves

Risk score:

- `risk_combined`

### Stratified CV Deferral

| Audit/deferral fraction | Precision | Recall | Lift over random | Retained accuracy | Accuracy gain |
|---|---:|---:|---:|---:|---:|
| 20% | 0.5433 | 0.3627 | 1.7037 | 0.7412 | +0.0604 |
| 30% | 0.4676 | 0.4603 | 1.4665 | 0.7487 | +0.0678 |
| 40% | 0.4513 | 0.5839 | 1.4140 | 0.7738 | +0.0930 |

### Leave-One-Dataset-Out Deferral

| Audit/deferral fraction | Precision | Recall | Lift over random | Retained accuracy | Accuracy gain |
|---|---:|---:|---:|---:|---:|
| 20% | 0.5000 | 0.3087 | 1.5435 | 0.7250 | +0.0450 |
| 30% | 0.5111 | 0.4703 | 1.5677 | 0.7619 | +0.0819 |
| 40% | 0.4833 | 0.6064 | 1.5161 | 0.7889 | +0.1089 |

Interpretation:

- Risk-based audit beats random audit under both CV and LODO.
- At 20% audit, lift is above the Freeze 11 threshold of 1.4.
- At 30-40% deferral, retained accuracy improves by about 8-11 points in LODO, which reaches the stronger full-paper target range.
- At 20% LODO deferral, accuracy gain is +4.5 points, slightly below the minimum +5 point target.

## Experiment 3 - Proxy Audit Calibration

Goal:

- Estimate overall majority-vote accuracy using a small audited subset.

Proxy human labels:

- benchmark labels are treated as simulated audit labels.

True population accuracy in this full v2 pilot:

- 0.6800.

Strategies:

- simple random audit,
- risk-stratified proportional audit,
- risk-oversampled stratified audit,
- proxy Neyman allocation using full-data stratum variance as an optimistic upper bound,
- PPI/control-variate variants using `risk_combined` as an auxiliary prediction.

### Representative Results

Budget 30:

| Strategy | Mean abs error | Mean CI width | Coverage |
|---|---:|---:|---:|
| simple random | 0.0619 | 0.2990 | 0.9435 |
| stratified proportional | 0.0590 | 0.2931 | 0.9525 |
| PPI stratified proportional | 0.0589 | 0.2940 | 0.9365 |
| risk oversample | 0.0633 | 0.3045 | 0.9200 |

Budget 60:

| Strategy | Mean abs error | Mean CI width | Coverage |
|---|---:|---:|---:|
| simple random | 0.0371 | 0.1833 | 0.9385 |
| stratified proportional | 0.0369 | 0.1796 | 0.9450 |
| PPI stratified proportional | 0.0374 | 0.1799 | 0.9435 |
| risk oversample | 0.0397 | 0.1903 | 0.9285 |

Budget 100:

| Strategy | Mean abs error | Mean CI width | Coverage |
|---|---:|---:|---:|
| simple random | 0.0218 | 0.1059 | 0.9545 |
| stratified proportional | 0.0210 | 0.1041 | 0.9635 |
| PPI stratified proportional | 0.0209 | 0.1046 | 0.9550 |
| risk oversample | 0.0233 | 0.1149 | 0.9525 |

Interpretation:

- For estimating overall majority accuracy, representative sampling is more important than oversampling high-risk cases.
- Risk-stratified proportional audit slightly improves mean error and CI width, but only by about 1-5%, not the 25-40% strong full-paper target.
- Risk oversampling is useful for finding errors, but biased/inefficient for estimating the overall population mean unless corrected carefully.
- PPI/control-variate with the current simple risk predictor does not materially improve interval width.

## Publication Criteria Check

### Short/Resource Bar

Status: largely met.

Evidence:

- Reproducible toolkit exists.
- Three datasets are included.
- Judge unreliability is clearly demonstrated.
- Risk-based audit beats random audit.
- Held-out AUROC is around 0.70.
- Top 20% audit lift is above 1.4.
- Deferral improves retained accuracy by about 4.5-6.0 points at 20%, and more at 30-40%.
- Confidence intervals are reported.

Remaining needs:

- human audit sanity check,
- larger sample or second judge model for stronger claims,
- clearer calibration story.

### Full Paper Bar

Status: partially met, not fully secured.

Met or near-met:

- LODO mean AUROC is 0.7118.
- LODO AUROC is above 0.60 for all three datasets.
- Top-risk audit precision is consistently above random.
- Retained accuracy improves by 8-11 points at 30-40% deferral.
- RAMDocs shows stronger conflict-related risk signal.

Not yet met:

- Top 20% audit recall is about 30.9% LODO, below the 35% target.
- Calibration/CI-width reduction is small, far below 25-40%.
- Only one judge model has been tested.
- Human audit has not yet been performed.
- Current sample size is still small for learned predictors.

## Decision

Continue, but refine the paper positioning:

Strong supported story:

> Reliability features can prioritize audit and selective deferral of unreliable RAG judge verdicts.

Weaker current story:

> Risk stratification alone substantially improves estimation of overall judge accuracy.

Therefore, the next experiments should prioritize:

1. expanding sample size,
2. adding at least one second judge model,
3. human audit sanity check,
4. conflict-specific analysis,
5. conservative calibration intervals rather than aggressive CI-width claims.

Recommended next step:

- Run a larger sample or second judge model on the same 150 samples before attempting final paper-scale calibration claims.

