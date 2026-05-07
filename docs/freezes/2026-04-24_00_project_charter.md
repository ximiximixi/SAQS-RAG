# Freeze 00: Project Charter

Date: 2026-04-24
Target venue: CIKM 2026
Working title: Calibrated LLM-as-a-Judge for RAG Evaluation: Predicting and Auditing Unreliable Verdicts under Evidence Conflict

## Submission Constraint

CIKM 2026 full/applied paper deadline is 2026-05-23 AoE. Short/resource paper deadline is 2026-06-06 AoE. We work toward a full-paper shaped contribution first, but maintain a controlled fallback to short/resource paper.

Full-paper target: 10 pages main content plus 2 pages references.
Fallback target: 4-page short/resource paper with code, prompts, cached judge outputs, and a small released benchmark slice or audit protocol.

## Core Thesis

LLM-as-a-judge is now widely used to evaluate whether RAG answers are faithful to retrieved evidence, but individual judge verdicts can become unreliable under irrelevant presentation changes and especially under conflicting retrieved evidence. Instead of replacing human evaluation or training a large judge model, we build a low-cost, auditable calibration layer that predicts when judge verdicts are unreliable and estimates RAG faithfulness with uncertainty.

## Research Gap

Existing RAG evaluation frameworks measure retrieval/generation quality, and existing LLM-as-judge studies expose bias. Recent conflict-aware RAG work studies how generators respond to conflicting sources. The missing bridge is:

1. A RAG-specific reliability diagnosis for LLM judges at the instance level.
2. A conflict-aware analysis of when judge verdicts flip under evidence order, prompt, and model perturbations.
3. A small-audit calibration procedure that reports confidence intervals or selective-risk guarantees rather than raw judge scores.

## Research Questions

RQ1: How often do LLM judges change faithfulness verdicts under prompt templates, evidence order, evidence subset, and judge-model perturbations?

RQ2: Are these instabilities amplified when retrieved evidence contains inter-source conflicts, outdated facts, or misleading distractors?

RQ3: Can cheap perturbation and claim/NLI features predict judge errors against gold or human-audited labels?

RQ4: Can a small audited slice calibrate dataset-level RAG faithfulness estimates and instance-level "accept vs audit" decisions with useful confidence/risk guarantees?

## Proposed Contribution

1. Judge reliability diagnosis framework for RAG evaluation.
2. Conflict-aware perturbation protocol covering prompt, evidence order, evidence subset, and model ensemble dimensions.
3. Calibration algorithm for instance-level selective acceptance and dataset-level confidence intervals.
4. Reproducible artifact: prompts, cached judge outputs, features, scripts, and paper-ready analysis notebooks.

## Non-Goals

We are not trying to train a new large judge model.
We are not trying to beat all RAG systems on QA accuracy.
We are not claiming LLM judges are useless; we study when they are usable, when they require audit, and how to quantify uncertainty.

## Minimum Publishable Result

A paper can be submitted if we produce all of the following:

1. At least two public datasets with gold or high-quality human labels.
2. At least three judge variants: prompt perturbation, evidence order perturbation, and model/prompt ensemble.
3. A measurable reliability signal that predicts judge errors better than raw confidence or random audit.
4. Selective risk/coverage curves and dataset-level confidence intervals showing lower error or lower human-audit cost than naive judging.
5. Clear positioning against RAGAS, ARES, RAGChecker/RAGBench, LLM-as-judge bias papers, and conflict-aware RAG papers.

## Fallback Route

If full-paper novelty or result strength is insufficient by 2026-05-16:

Short-paper fallback: present the diagnostic framework plus empirical findings on 2 datasets.
Resource-paper fallback: release a conflict-perturbed RAG judge audit benchmark plus reproducible prompts and cached outputs.

## Frozen Decision

Primary direction is evaluator reliability/calibration under evidence conflict. We should avoid drifting into generic RAG pipeline optimization unless an experiment directly improves judge reliability, audit cost, or uncertainty estimates.

