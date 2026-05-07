# Freeze 02: Experiment Plan

Date: 2026-04-24

## 1. Core Experimental Loop

For each RAG evaluation instance:

Input: query q, retrieved evidence/context C, generated answer a, gold or audited label y.

Base judge: LLM evaluator J returns a binary verdict or score for answer faithfulness/grounding.

Perturbation protocol:

1. Prompt variants: 3-5 semantically equivalent judge prompts.
2. Evidence order variants: original, reversed, random shuffle, support-first/conflict-first if labels allow.
3. Evidence subset variants: full context, top-k only, conflict-only, support-only, distractor-added.
4. Judge model variants: at least 2 API models plus one cheap/local or existing metric where feasible.

Reliability features:

- Vote entropy across perturbations.
- Flip rate across prompt variants.
- Flip rate across evidence-order variants.
- Flip rate across evidence-subset variants.
- Inter-judge disagreement.
- Score variance and margin.
- Claim-level support ratio, contradiction ratio, unknown ratio.
- Context conflict score: contradiction/semantic disagreement among retrieved evidence chunks.
- Answer length and lexical overlap controls.
- Retrieval support controls such as BM25/embedding overlap between answer claims and evidence.

Targets:

- Judge correctness: whether base judge verdict matches gold/human label.
- Judge uncertainty: whether perturbations produce inconsistent verdicts.
- Human audit need: whether an instance should be escalated.

## 2. Main Hypotheses

H1: Evidence conflict increases LLM judge instability more than non-conflict perturbations.

H2: Perturbation-derived features predict judge errors better than raw judge confidence, answer length, or lexical overlap.

H3: Selective acceptance based on calibrated reliability can reduce judge error at useful coverage levels.

H4: Small-audit calibration gives tighter and less biased dataset-level faithfulness estimates than naive LLM judge aggregation.

## 3. Candidate Datasets

Tier A: Start here.

1. RAGTruth
   Use: existing context/response labels for hallucination/faithfulness.
   Pros: direct hallucination labels, many responses, public.
   Cons: not all instances have explicit multi-source conflict.
   Source: https://github.com/ParticleMedia/RAGTruth

2. RAGBench
   Use: response/document/support labels plus existing metric outputs.
   Pros: already includes RAGAS/trulens/GPT-style metrics, good for meta-evaluation.
   Cons: labels partly generated/annotated by model pipelines; need inspect quality.
   Source: https://huggingface.co/datasets/rayonlabs/ragbench-all

3. FRAMES
   Use: generate RAG answers under oracle/BM25/multi-step retrieval and evaluate answer correctness/faithfulness.
   Pros: 824 multi-hop questions with gold answers and relevant Wikipedia links.
   Cons: requires us to generate answer outputs and fetch/source evidence.
   Source: https://huggingface.co/datasets/google/frames-benchmark

Tier B: Use if conflict experiments need more strength.

4. RAMDocs
   Use: conflict/ambiguity/misinformation scenarios.
   Pros: designed for conflicting evidence.
   Cons: must inspect exact labels and task format.
   Source: https://github.com/HanNight/RAMDocs

5. CONFLICTS from DRAGged into Conflicts
   Use: expert-labeled conflict types in realistic RAG setting.
   Pros: ideal match if data is accessible.
   Cons: availability and license must be checked.
   Source: https://arxiv.org/abs/2506.08500

6. HaluBench/Lynx
   Use: broader hallucination detection benchmark.
   Pros: 15k challenging samples.
   Cons: may be benchmark-oriented toward Lynx and less transparent on labels.
   Source: https://arxiv.org/abs/2407.08488

Tier C: Optional breadth.

7. Face4RAG
   Use: Chinese RAG factual consistency.
   Pros: gives multilingual/Chinese relevance; helpful if we want China-facing application value.
   Cons: adds translation/model variance; not needed for first submission.
   Source: https://arxiv.org/abs/2407.01080

8. CRAG / TREC RAG / FACTS Grounding
   Use: additional validation if time allows.
   Pros: well-known RAG evaluation benchmarks.
   Cons: may require substantial setup or unavailable model outputs.

## 4. Methods to Implement

Baseline B0: Single raw LLM judge.

Baseline B1: Majority vote over prompt variants.

Baseline B2: Majority vote over prompt + evidence-order variants.

Baseline B3: RAGAS/RAGChecker/RefChecker-style metric where feasible.

Baseline B4: Random audit or uncertainty by raw score margin.

Proposed M1: Perturbation Reliability Model.

- Train a lightweight logistic regression / random forest / gradient boosting model on a small audited calibration split.
- Input features are instability, disagreement, claim/NLI, and conflict features.
- Output probability that the base judge verdict is wrong.

Proposed M2: Selective Judge.

- Accept base judge verdict if predicted error is below threshold.
- Otherwise abstain or send to human audit.
- Evaluate selective risk vs coverage.

Proposed M3: PPI/Stratified Audit Estimator.

- Estimate aggregate RAG faithfulness rate by combining many judge predictions with a small audited set.
- Stratify audit sampling by predicted unreliability bins to reduce variance.
- Report confidence intervals and compare against naive judge averaging.

## 5. Metrics

Judge accuracy:

- Accuracy, macro F1, AUROC/AUPRC for judge correctness.
- False acceptance rate: unreliable verdicts accepted as reliable.

Calibration:

- Brier score.
- Expected calibration error.
- Reliability diagrams.

Selective prediction:

- Risk-coverage curve.
- Area under risk-coverage curve.
- Coverage at target risk: e.g., <= 5%, <= 10%.

Aggregate estimation:

- Absolute error of estimated dataset-level faithfulness.
- Confidence interval width.
- Empirical CI coverage via repeated subsampling.
- Human labels required to reach target error.

Conflict analysis:

- Judge flip rate by conflict type.
- Error rate by conflict type.
- Prompt/order/model sensitivity by conflict type.

Cost:

- API tokens per instance.
- Number of judge calls.
- Human audit percentage.

## 6. Experimental Tables and Figures

Table 1: Dataset statistics and label definitions.

Table 2: Judge models, prompts, perturbations, and cost.

Table 3: Raw judge accuracy/F1 across datasets and conflict slices.

Table 4: Predicting judge errors: feature ablation and AUROC/AUPRC.

Table 5: Dataset-level estimation: naive judge vs PPI/stratified audit confidence intervals.

Figure 1: Framework diagram.

Figure 2: Flip-rate heatmap by perturbation dimension and dataset.

Figure 3: Risk-coverage curves for selective judge.

Figure 4: Calibration/reliability diagram.

Figure 5: Cost vs error reduction curve.

## 7. Minimal Viable Experiment for Full Submission

Must complete:

1. RAGTruth + RAGBench or FRAMES.
2. At least 2 judge models and 3 prompt templates.
3. Evidence-order and prompt perturbations on all selected datasets.
4. Conflict subset from RAMDocs or synthetic conflict injection.
5. Logistic reliability model + selective risk evaluation.
6. PPI or stratified audit confidence interval experiment.

Stretch:

1. CONFLICTS benchmark if accessible.
2. Face4RAG as Chinese multilingual validation.
3. More judge models and cost-sensitive analysis.

## 8. Synthetic Conflict Injection Protocol

If natural conflict labels are insufficient:

1. Start with a gold-supported context-answer pair.
2. Create a conflicting evidence chunk by minimally editing a key entity, date, number, relation, or negation.
3. Insert the conflicting chunk at different positions in the evidence list.
4. Keep the original answer fixed and ask judges whether the answer is faithful to the full evidence.
5. Evaluate whether judges incorrectly mark the answer as faithful, become unstable, or follow the first/last evidence.

Controls:

- Add irrelevant distractors without contradiction.
- Add paraphrased supporting evidence.
- Normalize answer length.
- Randomize source labels or remove source labels.

## 9. Paper-Readiness Checklist

Submission is feasible when:

- All experiment scripts are deterministic and cache API outputs.
- Prompts are versioned.
- Data licenses are documented.
- Human/LLM audit protocol is written.
- GenAI Usage Disclosure is drafted.
- The paper has either a full-paper result or a short/resource fallback artifact.

