# Freeze 28: Canonical English Protocol and Human Notes

Date: 2026-05-06

This freeze records the reporting decision requested by the user:

- All future main experiments and paper-facing analysis use the original English audit items.
- `HumanGold-v1` is represented by the English-note files.
- Local annotation-support artifacts are not part of the main experimental protocol.

## Canonical Files

Main protocol:

- `docs/main_experiment_protocol.md`

Human gold:

- `data/audit/human_audit_annotations_en.csv`
- `data/audit/human_audit_annotations_en.jsonl`

Human-note conversion script:

- `scripts/build_human_gold_notes_en.py`

Updated analysis script:

- `scripts/analyze_human_gold_against_models.py`

## Human Notes

The human annotation notes have been converted into English for reporting and downstream analysis.

Validation:

- Rows: 100
- Non-empty notes: 84
- Empty notes: 16
- Non-ASCII characters in notes after cleanup: 0

The labels, confidence values, issue categories, and timestamps are preserved.

## Main Protocol Summary

Canonical input:

- `data/audit/human_audit_batch_100_blind.jsonl`

Canonical human gold:

- `data/audit/human_audit_annotations_en.csv`

Main judge conditions:

1. Original benchmark/reference label.
2. Pilot Qwen majority.
3. Pilot GLM majority.
4. Pilot Qwen+GLM combined majority.
5. Old weak five-model majority.
6. Strict independent five-model majority.

Assisted adjudication remains an internal pilot unless rerun under the same canonical protocol.

## Current Main Results

| Condition | Prediction distribution | Accuracy vs HumanGold-v1 |
| --- | --- | ---: |
| Original benchmark/reference label | 56 faithful / 44 unfaithful | 60% |
| Pilot Qwen majority | 33 faithful / 67 unfaithful | 89% |
| Pilot GLM majority | 34 faithful / 66 unfaithful | 86% |
| Pilot Qwen+GLM combined majority | 30 faithful / 66 unfaithful / 4 tie | 86% |
| Old weak five-model majority | 23 faithful / 72 unfaithful / 3 tie / 2 insufficient | 92% |
| Strict independent five-model majority | 20 faithful / 80 unfaithful | 96% |

Strict independent majority confusion:

| Human label | Pred faithful | Pred unfaithful |
| --- | ---: | ---: |
| faithful | 19 | 3 |
| unfaithful | 1 | 77 |

## Updated Writing Rule

For paper drafts, future freeze summaries, and experiment narratives:

- Describe the experiment as an English-input RAG faithfulness audit.
- Use English human notes from `human_audit_annotations_en.csv`.
- Do not describe local annotation-support materials as part of the main protocol.
- Clearly label assisted adjudication as internal pilot evidence until rerun under the canonical protocol.

## Next Work

The next experiment should build the final reliability predictor under this canonical setup.

Recommended targets:

- human-unfaithful detection,
- benchmark/reference mismatch vs human,
- strict independent majority wrong vs human,
- high-confidence wrong verdict detection,
- audit top-k precision and calibration.
