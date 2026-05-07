# Freeze 03: Decision Log

Date: 2026-04-24

## Decision 1: Keep the topic centered on evaluator reliability

Decision: The main paper is about reliability and calibration of LLM judges for RAG evaluation, not about improving RAG generation accuracy.

Reason: RAG system improvement is crowded and often requires heavier model experiments. Evaluator calibration is a better fit for low-GPU constraints and CIKM evaluation/trustworthy AI topics.

## Decision 2: Evidence conflict is the stress-test axis

Decision: Evidence conflict is not just a dataset detail; it is the core condition under which judge reliability should be tested.

Reason: Conflict-aware RAG work is active, but it mainly studies answer generation. Our differentiator is studying the evaluator under conflict.

## Decision 3: Use perturbation instability as signal, not just as failure report

Decision: Prompt/order/model flips should become features for predicting judge unreliability.

Reason: Prior LLM-as-judge papers show biases and instability. To be publishable, we need to convert that observation into an actionable calibration/audit method.

## Decision 4: Prefer small-audit statistical guarantees

Decision: The method should include selective risk and/or prediction-powered inference confidence intervals.

Reason: CIKM and IR audiences care about evaluation validity. Statistical guarantees make the work stronger than a benchmark-only empirical study.

## Decision 5: Initial dataset priority

Decision: Start with RAGTruth, RAGBench, and FRAMES. Add RAMDocs/CONFLICTS if accessible.

Reason: RAGTruth and RAGBench give immediate labeled RAG faithfulness-style data; FRAMES gives multi-hop RAG generation; RAMDocs/CONFLICTS directly cover conflict.

## Open Questions

1. Which judge APIs are available and affordable for repeated perturbation calls?
2. Is CONFLICTS publicly downloadable, and under what license?
3. Does RAGBench label quality suffice for gold evaluation, or should we treat it as weak labels?
4. How many human audit labels can we realistically produce before May 16?
5. Should Face4RAG be included to emphasize Chinese/multilingual value, or deferred to avoid scope creep?

## Next Work Package

WP1: Dataset feasibility check.

- Download or inspect RAGTruth schema.
- Inspect RAGBench schema and label definitions.
- Inspect FRAMES schema and decide generation protocol.
- Check RAMDocs and CONFLICTS availability.

WP2: Judge prompt design.

- Draft 3 faithful/groundedness judge prompts.
- Define JSON output format.
- Define evidence-order and prompt perturbation IDs.

WP3: Pilot experiment.

- Run 50-100 samples from RAGTruth and one conflict source.
- Compute flip rates and raw judge accuracy.
- Decide whether the main signal is strong enough for full-paper push.

