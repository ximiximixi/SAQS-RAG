# Freeze 01: Literature Review and Positioning

Date: 2026-04-24

## 1. Venue Fit

CIKM 2026 explicitly lists evaluation of generative/LLM-based systems, RAG, LLM-as-judge, trustworthy/responsible AI, resource-efficient AI, and agentic AI for information and knowledge tasks as relevant topics. The submission policy also emphasizes reproducibility and GenAI usage disclosure. This makes an evaluation/calibration paper a strong thematic fit.

Key venue sources:

- CIKM 2026 full research papers: https://cikm2026.diag.uniroma1.it/full-research-papers/
- CIKM 2026 important dates: https://cikm2026.diag.uniroma1.it/important-dates/
- CIKM 2026 submission policies: https://cikm2026.diag.uniroma1.it/submission-policies-and-information/
- CIKM 2026 short papers: https://cikm2026.diag.uniroma1.it/short-research-papers/
- CIKM 2026 resource papers: https://cikm2026.diag.uniroma1.it/resource-papers/

## 2. RAG and RAG Evaluation

Foundational RAG work frames retrieval as a way to add non-parametric memory and provenance to generation:

- Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (NeurIPS 2020), https://arxiv.org/abs/2005.11401
- Guu et al., "REALM: Retrieval-Augmented Language Model Pre-Training" (ICML 2020), https://arxiv.org/abs/2002.08909
- Karpukhin et al., "Dense Passage Retrieval for Open-Domain Question Answering" (EMNLP 2020), https://aclanthology.org/2020.emnlp-main.550/
- Izacard and Grave, "Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering" (EACL 2021), https://arxiv.org/abs/2007.01282
- Borgeaud et al., "Improving language models by retrieving from trillions of tokens" (ICML 2022), https://arxiv.org/abs/2112.04426
- Izacard et al., "Atlas: Few-shot Learning with Retrieval Augmented Language Models" (JMLR 2023), https://arxiv.org/abs/2208.03299
- Asai et al., "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection" (ICLR 2024), https://arxiv.org/abs/2310.11511

RAG evaluation has moved from end-task QA accuracy toward modular and faithfulness-oriented evaluation:

- RAGAS proposes reference-free metrics for retrieval and generation dimensions: https://arxiv.org/abs/2309.15217
- ARES evaluates context relevance, answer faithfulness, and answer relevance; importantly, it already uses prediction-powered inference with small human annotations: https://arxiv.org/abs/2311.09476
- RGB benchmarks RAG in English and Chinese: https://arxiv.org/abs/2309.01431
- RAGTruth provides 17,790 responses with word-level hallucination labels across QA, summarization, and data-to-text: https://aclanthology.org/2024.acl-long.585 and https://github.com/ParticleMedia/RAGTruth
- RAGBench provides explainable RAG labels and existing metric outputs: https://arxiv.org/abs/2407.11005 and https://huggingface.co/datasets/rayonlabs/ragbench-all
- RAGChecker decomposes long-form RAG evaluation into fine-grained retrieval/generation diagnostic metrics: https://arxiv.org/abs/2408.08067
- FRAMES targets factuality, retrieval, and reasoning in multi-hop RAG with 824 examples: https://arxiv.org/abs/2409.12941 and https://huggingface.co/datasets/google/frames-benchmark
- TREC RAG uses nugget/support/fluency/retrieval evaluation dimensions: https://trec-rag.github.io/annoucements/2024-track-guidelines/
- CRAG provides 4,409 QA pairs and mock APIs for factual RAG evaluation: https://arxiv.org/abs/2406.04744
- FACTS Grounding evaluates long-form grounded generation with 1,719 examples: https://deepmind.google/blog/facts-grounding-a-new-benchmark-for-evaluating-the-factuality-of-large-language-models/
- Face4RAG targets Chinese factual consistency evaluation for RAG: https://arxiv.org/abs/2407.01080
- RAGEval proposes scenario-specific RAG evaluation data generation: https://arxiv.org/abs/2408.01262

Takeaway for us: RAG evaluation is crowded. We should not claim novelty from another faithfulness metric alone. The paper must focus on reliability and calibration of the evaluator itself, especially under conflict.

## 3. LLM-as-a-Judge and Evaluator Bias

LLM-as-a-judge became popular because strong proprietary models can correlate with human judgments on open-ended text evaluation:

- G-Eval uses GPT-4 with chain-of-thought prompting for NLG evaluation: https://arxiv.org/abs/2303.16634
- MT-Bench/Chatbot Arena studies GPT-4 as judge and provides benchmark/evaluation protocol: https://arxiv.org/abs/2306.05685
- Prometheus trains an open judge model for fine-grained rubric-based evaluation: https://arxiv.org/abs/2310.08491
- LLM-Rubric proposes multidimensional calibrated rubric questions for automated evaluation: https://aclanthology.org/2024.acl-long.745
- Survey: "LLMs-as-Judges: A Comprehensive Survey on LLM-based Evaluation Methods": https://arxiv.org/abs/2412.05579

But evaluator reliability is fragile:

- "Large Language Models are not Fair Evaluators" reports position bias and proposes multiple-evidence, balanced-position, and human-in-the-loop calibration: https://arxiv.org/abs/2305.17926
- "Humans or LLMs as the Judge?" studies misinformation oversight, gender, authority, and beauty biases: https://arxiv.org/abs/2402.10669
- "Judging the Judges" systematically studies position bias in pairwise/listwise LLM judging: https://arxiv.org/abs/2406.07791
- "Large Language Models are Inconsistent and Biased Evaluators" reports familiarity bias, skewed rating distributions, anchoring, and prompt sensitivity: https://arxiv.org/abs/2405.01724
- ALLURE audits and improves LLM evaluation with annotated deviations and iterative in-context learning: https://arxiv.org/abs/2309.13701
- "Exploring the Reliability of LLMs as Customized Evaluators" studies fine-grained alignment with humans across tasks: https://arxiv.org/abs/2310.19740
- "Limits to scalable evaluation at the frontier" warns that LLM-as-judge has severe limitations when evaluating systems near or beyond the judge: https://arxiv.org/abs/2410.13341
- "Analyzing Uncertainty of LLM-as-a-Judge" uses conformal prediction to output intervals rather than brittle point scores: https://aclanthology.org/2025.emnlp-main.569.pdf

RAG-specific nuance:

- "LLMs are Biased Evaluators But Not Biased for Fact-Centric Retrieval Augmented Generation" suggests some judge biases may be less severe in fact-centric RAG than in general preference evaluation: https://aclanthology.org/2025.findings-acl.1369/

Takeaway for us: We need to test whether fact-centric RAG is genuinely robust, and whether evidence conflict breaks that robustness. Our novelty can be "bias/instability as a measurable reliability feature" rather than only "bias exists."

## 4. Conflict-Aware RAG

Recent RAG work increasingly studies retrieved evidence that is irrelevant, outdated, malicious, ambiguous, or mutually conflicting:

- Astute RAG studies imperfect retrieval and internal/external knowledge conflicts; it adaptively consolidates internal and external knowledge with source awareness: https://aclanthology.org/2025.acl-long.1476/
- DRAGged into Conflicts introduces a taxonomy of RAG source conflicts and CONFLICTS benchmark with expert annotations: https://arxiv.org/abs/2506.08500
- Retrieval-Augmented Generation with Conflicting Evidence introduces RAMDocs and MADAM-RAG for ambiguity, misinformation, and noise: https://arxiv.org/abs/2504.13079 and https://github.com/HanNight/RAMDocs
- BordaRAG, accepted at CIKM 2025, resolves knowledge conflict with Borda voting over candidates/documents: CIKM 2025 proceedings, https://cikm2025.org/program/proceedings
- FaithfulRAG models fact-level conflict between parametric and retrieved knowledge: https://arxiv.org/abs/2506.08938
- MAGIC benchmarks multi-hop and graph-based inter-context conflicts: https://arxiv.org/abs/2507.21544
- Resolving Conflicting Evidence in Automated Fact-Checking evaluates RAG under conflicting evidence in fact-checking: https://arxiv.org/abs/2505.17762

Takeaway for us: Conflict-aware generation is active, but evaluator reliability under conflict is less directly addressed. We should treat conflict as a stress test for judges, not only for answer generators.

## 5. Claim-Level and NLI-Based Faithfulness Signals

Claim-level verification can provide cheaper, more interpretable features than repeated strong judge calls:

- RefChecker uses claim triplets and reference-based hallucination checking: https://arxiv.org/abs/2405.14486 and https://github.com/amazon-science/RefChecker
- Lynx introduces HaluBench, a 15k hallucination evaluation benchmark for challenging RAG cases: https://arxiv.org/abs/2407.08488
- RAGChecker uses fine-grained diagnostic signals, including claim-level checking: https://arxiv.org/abs/2408.08067
- Query-conditioned NLI is emerging as a way to benchmark context-sensitive entailment for RAG-like tasks: https://assets.amazon.science/d9/e9/6e37fa824168af790f680cad9fc6/benchmarking-query-conditioned-natural-language-inference.pdf

Takeaway for us: NLI/claim features should be auxiliary reliability predictors, not the sole judge replacement. This avoids overclaiming from local entailment models.

## 6. Statistical Calibration, Auditing, and Selective Prediction

The calibration layer can borrow from statistical inference and selective prediction:

- Prediction-powered inference provides valid inference by combining a small labeled dataset with many ML predictions: https://arxiv.org/abs/2301.09633
- Conformal risk control controls risk functions beyond miscoverage: https://arxiv.org/abs/2208.02814
- Selective classification formalizes risk-coverage tradeoff and reject-option prediction: https://arxiv.org/abs/1705.08500
- SelectiveNet gives an integrated reject-option model: https://proceedings.mlr.press/v97/geifman19a.html
- Causal Judge Evaluation frames judge scores as calibrated surrogate metrics for LLM systems: https://arxiv.org/abs/2512.11150
- CIKM 2025 "A Cost-Effective Framework to Evaluate LLM-Generated Relevance Judgements" estimates LLM relevance-judgment quality with confidence and a small human budget; it reports that auditing 16% can estimate LLM performance with 95% confidence: https://cikm2025.org/program/proceedings

Takeaway for us: ARES and the CIKM 2025 relevance-judgment paper are closest statistically. Our differentiation must be RAG faithfulness, instance-level reliability prediction, perturbation features, and evidence conflict.

## 7. Closest Papers and Differentiation

Closest to our idea:

1. ARES: automated RAG evaluation plus PPI.
   Difference: ARES fine-tunes lightweight judges and evaluates RAG components; we audit and calibrate LLM judges under perturbation/conflict without requiring model training.

2. Large Language Models are not Fair Evaluators.
   Difference: general evaluator bias; we focus on RAG faithfulness and evidence conflict, and use perturbation instability as a predictor.

3. CIKM 2025 cost-effective relevance judgments.
   Difference: IR relevance judgments; we target RAG answer faithfulness with context conflicts and claim-level signals.

4. RAGChecker/RAGBench/RefChecker.
   Difference: they provide metrics/benchmarks; we study whether automated judges of those properties are reliable and how to calibrate them.

5. DRAGged into Conflicts / RAMDocs / BordaRAG / Astute RAG.
   Difference: these improve or evaluate RAG generation under conflict; we evaluate the evaluator under conflict.

## 8. Current Literature-Based Decision

The strongest paper shape is:

"A conflict-aware judge reliability and calibration framework for RAG evaluation."

The paper should make the following claim:

Raw LLM judge verdicts can be misleading at the instance level, especially when retrieved evidence conflicts. However, their failure is not random: prompt/order/model instability, disagreement, and claim-level support signals can predict unreliable verdicts. With a small audit set, we can selectively accept reliable judge decisions and produce calibrated aggregate estimates with fewer human labels.

