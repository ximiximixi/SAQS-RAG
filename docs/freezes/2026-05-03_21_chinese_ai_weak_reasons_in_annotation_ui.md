# Freeze 21: Chinese Five-Model Weak Reasons in Annotation UI

Date: 2026-05-03

## Purpose

The annotation UI now shows the five weak-label models' labels, confidence scores, issue categories, and translated Chinese reasons for each audit item. These are provided as reference material for human review and are not written into the human annotation fields.

## Source

Input:

- `data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv`
- `data/audit/weak_label_comparison_5models/weak_label_comparison_summary.json`

Models:

- `qwen3.6-max-preview`
- `deepseek-v4-pro`
- `kimi-k2.6`
- `qwen3-max-2026-01-23`
- `qwen3.6-plus-2026-04-02`

## Translation

Script:

- `scripts/translate_ai_weak_reasons_zh.py`

Translation model:

- `qwen3.6-max-preview`

Settings:

- Thinking disabled (`enable_thinking=false`)
- Temperature `0.0`
- Batch size `50`
- JSON output mode

Generated outputs:

- `data/audit/ai_weak_reviews_5models_zh.json`
- `data/audit/ai_weak_reviews_5models_zh.csv`

Validation:

- 100 audit items.
- 5 model reviews per item.
- 500 reasons translated.
- 0 missing translations.

## UI Changes

Updated files:

- `annotation_ui/server.py`
- `annotation_ui/index.html`
- `annotation_ui/app.js`
- `annotation_ui/style.css`

Behavior:

- The server loads `data/audit/ai_weak_reviews_5models_zh.json` by default.
- Each item receives an `ai_weak_reviews` object.
- The UI displays an "AI 参考意见" panel before the human annotation form.
- Each model card shows:
  - model name,
  - model label and Chinese label,
  - confidence,
  - issue categories with Chinese explanations,
  - Chinese translated reason,
  - collapsible English original reason.

The human annotation form remains separate and empty unless the user manually saves a label.

## Validation

Validated:

- `annotation_ui/server.py` loads 100 items.
- `annotation_ui/server.py` loads 100 AI review objects.
- Current active human annotations remain 0.
- `scripts/translate_ai_weak_reasons_zh.py` passes Python compilation.
- `annotation_ui/server.py` passes Python compilation.
- `annotation_ui/app.js` passes `node --check`.

Example validation item:

- `AUDIT-003` has 5 model reviews.
- Qwen reason in Chinese: "证据识别出一首U2歌曲（Bono创作）、一首Jeremy Camp歌曲和一部Ava DuVernay电影的创作者。问题未指定引用的是哪一首“I Will Follow”。"

## Caveat

This makes the manual workflow explicitly LLM-assisted. For paper reporting, these annotations should be described as assisted audit unless we later create a separate independent audit subset without AI reference reasons.
