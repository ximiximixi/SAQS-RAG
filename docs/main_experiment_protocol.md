# Main Experiment Protocol

This is the canonical protocol for the paper and all future analysis.

## Canonical Inputs

- Use the original English audit items as the model-judging input.
- Use `data/audit/human_audit_batch_100_blind.jsonl` for the 100-item audit set.
- Use `data/audit/human_audit_annotations_en.csv` as `HumanGold-v1`.
- Treat `data/audit/human_audit_annotations.csv` as a raw local annotation record, not as the reporting file.

## Human Gold

`HumanGold-v1` is a fully independent, double-blind, single-annotator human audit over 100 risk-enriched RAG evaluation items.

Canonical human-gold files:

- `data/audit/human_audit_annotations_en.csv`
- `data/audit/human_audit_annotations_en.jsonl`

Human label distribution:

| Label | Count |
| --- | ---: |
| faithful | 22 |
| unfaithful | 78 |

The `notes` field in the canonical human-gold files is in English and should be used for tables, case studies, and paper writing.

## Main Judge Conditions

The main experimental conditions should be reported on original English inputs:

1. Original benchmark/reference label.
2. Pilot Qwen majority from the original judge perturbation run.
3. Pilot GLM majority from the original judge perturbation run.
4. Old weak five-model majority on original inputs.
5. Strict independent five-model majority on original inputs.

Current main strict independent files:

- `data/audit/strict_independent_en_qwen36maxpreview.csv`
- `data/audit/strict_independent_en_deepseekv4pro.csv`
- `data/audit/strict_independent_en_kimik26.csv`
- `data/audit/strict_independent_en_qwen3max20260123.csv`
- `data/audit/strict_independent_en_qwen36plus20260402.csv`

Assisted adjudication should be treated as an internal pilot until rerun under the same canonical English-input protocol.

## Current Main Results

Main results against `HumanGold-v1`:

| Condition | Prediction distribution | Accuracy |
| --- | --- | ---: |
| Original benchmark/reference label | 56 faithful / 44 unfaithful | 60% |
| Pilot Qwen majority | 33 faithful / 67 unfaithful | 89% |
| Pilot GLM majority | 34 faithful / 66 unfaithful | 86% |
| Pilot Qwen+GLM combined majority | 30 faithful / 66 unfaithful / 4 tie | 86% |
| Old weak five-model majority | 23 faithful / 72 unfaithful / 3 tie / 2 insufficient | 92% |
| Strict independent five-model majority | 20 faithful / 80 unfaithful | 96% |

Strict independent majority confusion against `HumanGold-v1`:

| Human label | Pred faithful | Pred unfaithful |
| --- | ---: | ---: |
| faithful | 19 | 3 |
| unfaithful | 1 | 77 |

Strict independent majority metrics:

- Accuracy: 96%
- Macro F1: 0.940
- Cohen's kappa: 0.880
- 95% Wilson CI: [90.2%, 98.4%]

## Main Scientific Claims

The paper should not claim that stricter prompting always improves LLM-as-Judge. The current evidence supports a more careful claim:

1. RAG faithfulness verdicts are policy-dependent.
2. Explicit faithfulness definitions change verdicts and reduce some ambiguity-driven errors.
3. Evidence conflict, entity ambiguity, benchmark ambiguity, unsupported claims, and contradictions dominate human-unfaithful cases.
4. Multi-model agreement is useful but not sufficient as a reliability guarantee.
5. A low-cost audit and calibration layer can prioritize unreliable verdicts and make automatic RAG evaluation more transparent.

## Next Experiments

Future experiments should continue from the canonical English-input setup:

1. Rerun assisted adjudication on original English inputs if assisted adjudication remains part of the main paper.
2. Build a human-gold reliability predictor using model disagreement, confidence, risk scores, issue categories, and protocol outputs.
3. Evaluate calibration using reliability bins, top-k audit precision, confidence intervals, and high-confidence-wrong analysis.
4. Add a second small human adjudication subset if possible for inter-annotator agreement.
