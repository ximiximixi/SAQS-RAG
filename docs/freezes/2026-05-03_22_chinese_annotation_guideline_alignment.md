# Freeze 22: Chinese Annotation Guideline Alignment

Date: 2026-05-03

## Purpose

Create a Chinese annotation guideline that translates and consolidates the most important parts of the already frozen audit documents.

This is not a new annotation standard. It is a Chinese reference version for easier manual annotation.

## New File

- `docs/audit_annotation_guidelines_zh.md`

## Source Documents

The Chinese guideline is based on:

- `docs/audit_annotation_guidelines.md`
- `docs/freezes/2026-04-24_16_human_audit_batch.md`
- `docs/freezes/2026-05-03_20_ai_issue_category_suggestions_for_ui.md`
- `docs/freezes/2026-05-03_21_chinese_ai_weak_reasons_in_annotation_ui.md`

## Key Alignment

The strict human annotation standard remains:

- `faithful`: every important claim in the answer is supported by the provided evidence, and the answer does not ignore important conflict or ambiguity.
- `unfaithful`: the answer contradicts evidence, adds unsupported facts, selects one side of conflicting evidence without support, gives a wrong entity/date/number, or presents uncertainty as certainty when evidence is conflicting or incomplete.
- `insufficient`: the evidence is not enough to determine whether the answer is faithful or unfaithful. Use sparingly; if the answer makes unsupported claims, prefer `unfaithful`.

## Practical Consequence

For ambiguity cases such as:

- question: "When was the People's University established?"
- answer: "1913"
- evidence: multiple People's Universities with different dates

The recommended strict annotation is:

- label: `unfaithful`
- issue categories: `entity_ambiguity`, `benchmark_ambiguous`

Reason:

The answer is supported by one evidence passage but ignores the fact that the question does not specify which entity is intended and the evidence contains multiple plausible entities.

## AI Reference Caveat

The five AI opinions shown in the UI are reference material only. They are not automatically written into human labels.

For paper reporting, annotations produced while viewing AI reasons should be described as LLM-assisted audit unless a separate independent subset is later collected without AI references.
