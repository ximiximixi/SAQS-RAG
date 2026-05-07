# Freeze 05: Dataset Schema and Pilot Feasibility Check

Date: 2026-04-24
Local root: `C:\Users\11816\Desktop\cikm\data\raw`

## Overall Status

All five first-round datasets are present locally and readable.

Directory summary:

| Dataset | Local path | Files | Approx. size | Status |
|---|---:|---:|---:|---|
| FRAMES | `data/raw/frames` | 8 | 0.49 MB | readable TSV |
| RAGBench | `data/raw/ragbench` | 78 | 451 MB | readable parquet after pyarrow install |
| RAGTruth | `data/raw/RAGTruth` | 12 | 36.9 MB | readable JSONL |
| CONFLICTS / rag_conflicts | `data/raw/rag_conflicts` | 3 | 46.7 MB | readable JSONL |
| RAMDocs | `data/raw/RAMDocs` | 5 | 1.94 MB | readable JSONL |

Note: default `rg` execution was denied on this Windows environment, so file enumeration used PowerShell. The bundled Python runtime lacked `pyarrow`; `pyarrow` was installed into the bundled Codex Python runtime for parquet inspection.

## RAGTruth

Files:

- `dataset/response.jsonl`
- `dataset/source_info.jsonl`

License: MIT.

Rows:

- `response.jsonl`: 17,790 responses.
- `source_info.jsonl`: 2,965 sources.

Fields in `response.jsonl`:

- `id`
- `source_id`
- `model`
- `temperature`
- `labels`
- `split`
- `quality`
- `response`

Fields in `source_info.jsonl`:

- `source_id`
- `task_type`
- `source`
- `source_info`
- `prompt`

Label statistics:

- Responses with non-empty hallucination labels: 7,664.
- Split: train 15,090; test 2,700.
- Task types by response: Data2txt 6,198; QA 5,934; Summary 5,658.
- Models: six models, each with 2,965 responses.
- Quality: good 17,617; incorrect_refusal 144; truncated 29.

Hallucination span label fields:

- `start`
- `end`
- `text`
- `meta`
- `label_type`
- `implicit_true`
- `due_to_null`

Observed `label_type` counts:

- Evident Baseless Info: 6,237
- Evident Conflict: 5,324
- Subtle Baseless Info: 2,527
- Subtle Conflict: 201

Pilot feasibility:

High. RAGTruth can directly support judge correctness experiments.

Proposed response-level label:

- `is_hallucinated = len(labels) > 0`
- `is_faithful = len(labels) == 0`

Pilot use:

- Join `response.jsonl` with `source_info.jsonl` by `source_id`.
- Evidence/context: `source_info`
- Candidate answer: `response`
- Gold label: `is_faithful`
- Additional labels: `task_type`, `model`, `quality`, span `label_type`

Important caveat:

Span labels enable richer claim-level evaluation, but the first pilot should start with response-level faithfulness.

## RAGBench

Files:

- 36 parquet files across 12 subsets and 3 splits.

License: CC-BY-4.0 according to local README.

Total rows: 95,381.

Rows by dataset:

- covidqa: 1,765
- cuad: 2,550
- delucionqa: 1,826
- emanual: 1,318
- expertqa: 2,027
- finqa: 16,562
- hagrid: 4,532
- hotpotqa: 2,697
- msmarco: 2,690
- pubmedqa: 24,500
- tatqa: 33,104
- techqa: 1,810

Rows by split:

- train: 73,286
- validation: 10,293
- test: 11,802

Schema fields:

- `id`
- `question`
- `documents`
- `response`
- `generation_model_name`
- `annotating_model_name`
- `dataset_name`
- `documents_sentences`
- `response_sentences`
- `sentence_support_information`
- `unsupported_response_sentence_keys`
- `adherence_score`
- `overall_supported_explanation`
- `relevance_explanation`
- `all_relevant_sentence_keys`
- `all_utilized_sentence_keys`
- `trulens_groundedness`
- `trulens_context_relevance`
- `ragas_faithfulness`
- `ragas_context_relevance`
- `gpt3_adherence`
- `gpt3_context_relevance`
- `gpt35_utilization`
- `relevance_score`
- `utilization_score`
- `completeness_score`

Label statistics:

- `adherence_score=True`: 82,530
- `adherence_score=False`: 12,848
- `adherence_score=None`: 3

Generation models:

- claude-3-haiku-20240307: 42,110
- gpt-3.5-turbo-0125: 39,560
- gpt-3.5-turbo-1106: 7,152
- HAGRID: 4,532
- ExpertQA: 2,027

Annotating models:

- gpt-4o: 53,182
- gpt-4-turbo-2024-04-09: 42,196
- None: 3

Pilot feasibility:

Very high. RAGBench is the strongest immediate dataset for paper-style metric comparison because it has documents, responses, sentence support, boolean adherence labels, explanations, and existing RAGAS/TruLens-like metric outputs.

Proposed pilot label:

- `is_faithful = adherence_score`

Pilot use:

- Use only test split initially.
- Balance positives/negatives because the full dataset is heavily faithful-skewed.
- Evidence/context: `documents`
- Candidate answer: `response`
- Gold label: `adherence_score`
- Baseline metrics: `ragas_faithfulness`, `trulens_groundedness`, `gpt3_adherence`, `relevance_score`, `utilization_score`, `completeness_score`

## FRAMES

File:

- `test.tsv`

License: Apache-2.0 according to local README.

Rows: 824.

Fields:

- unnamed index column
- `Prompt`
- `Answer`
- `wikipedia_link_1` ... `wikipedia_link_11+`
- `reasoning_types`
- `wiki_links`

Reasoning types: 30 unique combinations. Top categories include:

- Multiple constraints: 265
- Numerical reasoning: 58
- Temporal reasoning: 50
- Tabular reasoning + Multiple constraints: 50
- Multiple constraints + Temporal reasoning: 44

Wikipedia link count:

- min: 2
- median: 3
- max: 11

Pilot feasibility:

Medium. FRAMES is excellent for multi-hop RAG evaluation, but it does not include evidence text locally, only Wikipedia links. It requires fetching/parsing Wikipedia pages or generating RAG outputs before judge faithfulness experiments.

Proposed pilot use:

- Defer until after RAGTruth/RAGBench/RAMDocs pilot.
- Use as multi-hop extension if time permits.
- Build evidence by fetching linked Wikipedia pages or using their lead sections.

## CONFLICTS / rag_conflicts

File:

- `conflicts.jsonl`

License: Apache-2.0.

Rows: 458.

Fields:

- `source`
- `question`
- `search_results`
- `conflict_type`
- `correct_answer`

Conflict type distribution:

- No conflict: 161
- Complementary information: 115
- Conflicting opinions and research outcomes: 115
- Conflict due to outdated information: 62
- Conflict due to misinformation: 5

Source distribution:

- conflicting_qa: 162
- situated_qa_geo: 105
- freshqa: 95
- qacc: 55
- situated_qa_temp: 41

Search result count:

- min: 5
- median: 9
- max: 20

Blank `correct_answer`:

- 221 rows have blank or whitespace-only `correct_answer`.
- This mostly affects conflict types where a single answer is not necessarily expected, e.g. complementary information or conflicting opinions.

Pilot feasibility:

Medium-high for conflict analysis, medium for judge correctness. The dataset is ideal for conflict type analysis, but it does not provide a generated answer for every item. We need to construct or generate candidate answers before using it for answer faithfulness judging.

Proposed pilot use:

- First use it for conflict-feature and perturbation design.
- For rows with non-empty `correct_answer`, create simple candidate answers from the correct answer.
- For blank-answer conflict types, use later as an "appropriate response under conflict" task or generate model answers.

Important caveat:

This is not immediately a standard `context + answer + supported/unsupported` dataset. It is a conflict-stress-test source.

## RAMDocs

File:

- `RAMDocs_test.jsonl`

License: MIT.

Rows: 500.

Fields:

- `question`
- `documents`
- `disambig_entity`
- `gold_answers`
- `wrong_answers`

Document statistics:

- documents per instance: min 1; median 5; max 12.
- gold answer list length: 1, 2, or 3.
- wrong answer list length: 0, 1, or 2.

Document objects include text, type, and answer-like metadata. Example document types include `correct`; wrong/conflicting documents are present in the list.

Pilot feasibility:

High for conflict-specific judge stress testing.

Proposed pilot construction:

- Evidence/context: concatenate `documents[*].text`, preserving document order and document type for analysis only.
- Candidate faithful answer: "The answer is {gold_answers[0]}."
- Candidate unfaithful/conflicting answer: "The answer is {wrong_answers[0]}." when available.
- Gold label: faithful for gold answer; unfaithful for wrong answer.

This makes RAMDocs immediately useful for evidence-order perturbation:

- original order
- shuffled order
- correct-first
- wrong-first

## Recommended First Pilot

Pilot size: 50-100 evaluation instances.

Pilot datasets:

1. RAGBench test split
   - 25 faithful + 25 unfaithful examples.
   - Direct support labels.

2. RAGTruth test split
   - 25 faithful + 25 hallucinated examples.
   - Direct hallucination labels.

3. RAMDocs
   - 25 gold-answer examples + 25 wrong-answer examples.
   - Direct conflict evidence stress test.

Defer:

- FRAMES until we build Wikipedia evidence extraction.
- rag_conflicts until we either restrict to non-empty `correct_answer` or generate candidate answers.

## Current Decision

For the first actual judge perturbation run, use RAGBench + RAGTruth + RAMDocs. Keep FRAMES and rag_conflicts as second-stage datasets after the first reliability signal check.

