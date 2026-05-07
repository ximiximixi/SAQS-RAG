# Freeze 19: Chinese Audit Batch and Annotation Reset

Date: 2026-05-03

## Purpose

The human audit UI previously showed English questions, answers, and evidence. To make manual review easier, the 100-item blind audit batch was translated into Simplified Chinese using `qwen3.6-max-preview`.

The previously saved 4 human annotations were cleared at the user's request so annotation can restart from a clean state.

## Translation Model

- Model: `qwen3.6-max-preview`
- API: existing OpenAI-compatible endpoint configured in `.env`
- Thinking: disabled (`enable_thinking=false`)
- Temperature: `0.0`
- Output format: JSON object

The API key is intentionally not recorded here.

## Translation Script

New script:

- `scripts/translate_audit_batch_zh.py`

The script preserves original English fields and adds:

- `question_zh`
- `answer_zh`
- `evidence[*].text_zh`
- `translation_model`
- `translation_status`

It writes incrementally and can resume from completed `audit_id`s.

## Generated Files

Primary translated batch:

- `data/audit/human_audit_batch_100_blind_zh.jsonl`

Repair/backups created during validation:

- `data/audit/human_audit_batch_100_blind_zh.before_repair.jsonl`
- `data/audit/human_audit_batch_zh_repair_subset.jsonl`
- `data/audit/human_audit_batch_zh_repair_translated.jsonl`
- `data/audit/human_audit_batch_100_blind_zh_smoke.jsonl`

Validation result:

- 100 rows loaded.
- 0 missing Chinese questions/answers.
- 0 missing `text_zh` fields in evidence after repair.

## UI Changes

Updated files:

- `annotation_ui/server.py`
- `annotation_ui/index.html`
- `annotation_ui/app.js`
- `annotation_ui/style.css`

Behavior:

- The server now defaults to `data/audit/human_audit_batch_100_blind_zh.jsonl` when it exists.
- The UI displays Chinese question, answer, and evidence by default.
- The English original is preserved under collapsible "英文原文" blocks.
- UI labels/buttons were localized to Chinese.
- The previous misleading `Clear` option was renamed to `清空选择`, making clear that it is not a fourth annotation label.
- Issue categories still preserve English machine-readable names, with Chinese explanations shown under each category.

## Annotation Reset

Previous human annotations:

- 4 saved annotations existed before reset.

Backups:

- `data/audit/human_audit_annotations.backup_20260503_173839.jsonl`
- `data/audit/human_audit_annotations.backup_20260503_173839.csv`

Current active annotation files:

- `data/audit/human_audit_annotations.jsonl`: removed
- `data/audit/human_audit_annotations.csv`: removed

When the UI is started again, annotation progress will begin at 0/100.

## Current Server Command

Use:

```powershell
python .\annotation_ui\server.py --host 127.0.0.1 --port 8765
```

URL:

```text
http://127.0.0.1:8765
```

## Caveats

- The Chinese translation is for annotation convenience. The original English evidence remains available in the UI and should be checked when a case seems ambiguous.
- The translated batch must not be treated as a new dataset version for benchmark statistics; it is an annotation interface artifact.
