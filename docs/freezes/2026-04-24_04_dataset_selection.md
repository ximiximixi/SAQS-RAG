# Freeze 04: Dataset Selection

Date: 2026-04-24

## Frozen First-Round Dataset Scope

For the first pilot and main experiment design, we will use the following datasets only:

1. RAGTruth
   URL: https://github.com/ParticleMedia/RAGTruth
   Role: primary faithfulness / hallucination correctness dataset.
   Expected use: judge correctness, prompt perturbation, evidence-order perturbation.

2. RAGBench
   URL: https://huggingface.co/datasets/galileo-ai/ragbench
   Backup/integrated URL: https://huggingface.co/datasets/rayonlabs/ragbench-all
   Role: primary response-document support dataset with existing metric outputs.
   Expected use: compare raw LLM judge, RAGAS-like scores, support labels, perturbation reliability.

3. FRAMES
   URL: https://huggingface.co/datasets/google/frames-benchmark
   Role: multi-hop factuality / retrieval / reasoning dataset.
   Expected use: generate or evaluate RAG answers in a controlled multi-hop setting.

4. CONFLICTS / rag_conflicts
   URL: https://github.com/google-research-datasets/rag_conflicts
   Role: primary natural evidence-conflict dataset.
   Expected use: test whether conflict type increases judge flip rate and error rate.

5. RAMDocs
   URL: https://github.com/HanNight/RAMDocs
   Role: secondary conflict evidence dataset.
   Expected use: validate conflict-specific findings beyond CONFLICTS.

## Deferred Datasets

Face4RAG and CRAG are deferred. They are not part of the first-round pilot unless the above datasets fail to provide enough examples or label coverage.

Face4RAG URL: https://huggingface.co/datasets/yq27/Face4RAG
CRAG URL: https://github.com/facebookresearch/CRAG

## Local Directory Convention

Expected local paths:

```text
C:\Users\11816\Desktop\cikm\data\raw\RAGTruth
C:\Users\11816\Desktop\cikm\data\raw\ragbench
C:\Users\11816\Desktop\cikm\data\raw\frames
C:\Users\11816\Desktop\cikm\data\raw\rag_conflicts
C:\Users\11816\Desktop\cikm\data\raw\RAMDocs
```

## Download Completion Check

After downloading, we will inspect:

1. File formats and sizes.
2. Available splits.
3. Core fields: query/question, context/evidence, response/answer, labels.
4. Label semantics: hallucinated vs supported, conflict type, gold answer.
5. License and citation requirements.
6. Whether a 50-100 sample pilot can be built without additional generation.

## Decision

The first-round experimental design is constrained to these five datasets. We will not expand the dataset list until after the schema inspection and pilot signal check.

