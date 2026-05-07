# Human Audit Annotation Guidelines

Date: 2026-04-24

## Goal

Decide whether a candidate RAG answer is faithful to the provided evidence.

Use only the evidence shown in the audit item. Do not use outside knowledge, even if you know the answer.

## Files

Blind annotation file:

- `data/audit/human_audit_batch_100_blind.csv`

Full blind JSONL with evidence structure:

- `data/audit/human_audit_batch_100_blind.jsonl`

Hidden metadata for analysis only:

- `data/audit/human_audit_batch_100_metadata.csv`

Do not open the metadata file while annotating. It contains benchmark labels and model predictions.

## Label Set

Use exactly one label:

- `faithful`
- `unfaithful`
- `insufficient`

### faithful

Choose `faithful` if every important claim in the answer is supported by the provided evidence.

Minor wording differences are okay if the meaning is supported.

### unfaithful

Choose `unfaithful` if the answer:

- contradicts the evidence,
- adds important unsupported facts,
- selects one side of conflicting evidence without support,
- gives a wrong entity/date/number,
- presents uncertainty as certainty when evidence is conflicting or incomplete.

### insufficient

Choose `insufficient` if the evidence does not contain enough information to determine whether the answer is faithful or unfaithful.

Use this sparingly. If the answer makes unsupported claims, prefer `unfaithful`.

## Confidence

Use a number from 0 to 1:

- `1.0`: clear and easy decision.
- `0.8`: mostly clear, minor ambiguity.
- `0.6`: difficult but leaning one way.
- `0.5`: very uncertain.

## Issue Categories

Use one or more pipe-separated categories if helpful:

- `unsupported_claim`
- `contradiction`
- `evidence_conflict`
- `insufficient_evidence`
- `entity_ambiguity`
- `temporal_conflict`
- `numeric_error`
- `over_specific_answer`
- `answer_format_issue`
- `benchmark_ambiguous`
- `other`

Examples:

- `unsupported_claim|numeric_error`
- `evidence_conflict|temporal_conflict`

## Annotation Columns

Fill these columns in `human_audit_batch_100_blind.csv`:

- `annotator_label`
- `annotator_confidence`
- `issue_categories`
- `notes`

Do not edit:

- `audit_id`
- `question`
- `answer`
- `evidence`

## Decision Checklist

For each item:

1. Read the question.
2. Read the evidence.
3. Read the answer.
4. Identify the answer's key claims.
5. Check whether each key claim is supported.
6. If evidence conflicts, check whether the answer handles the conflict appropriately.
7. Assign label, confidence, categories, and short notes.

## Notes For This Project

This audit is used to validate whether benchmark labels and LLM judge verdicts agree with human judgment.

The audit batch intentionally mixes:

- high-risk examples,
- model-disagreement examples,
- stable shared-error examples,
- conflict-heavy examples,
- low-risk controls.

The file is intentionally blinded so annotation is not influenced by benchmark labels or model predictions.

