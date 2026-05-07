# Freeze 20: AI Issue Category Suggestions for Annotation UI

Date: 2026-05-03

## Purpose

To reduce manual annotation burden, the annotation UI now prioritizes issue categories suggested by the five weak-label models. This is an interface aid only. The UI does not automatically select any issue category and does not overwrite human annotation.

## Source

Input file:

- `data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv`

The suggestions are aggregated from each model's `*_issues` fields.

Models included:

- `qwen3.6-max-preview`
- `deepseek-v4-pro`
- `kimi-k2.6`
- `qwen3-max-2026-01-23`
- `qwen3.6-plus-2026-04-02`

## Script

New script:

- `scripts/build_issue_category_suggestions.py`

Default outputs:

- `data/audit/ai_issue_category_suggestions_5models.json`
- `data/audit/ai_issue_category_suggestions_5models.csv`

Generation command:

```powershell
python .\scripts\build_issue_category_suggestions.py --min-votes 1
```

Result:

- 100 items processed.
- 84 items have at least one AI-suggested issue category.
- 16 items have no suggested issue category from the five models.

## UI Changes

Updated files:

- `annotation_ui/server.py`
- `annotation_ui/app.js`
- `annotation_ui/style.css`

Behavior:

- The server loads `data/audit/ai_issue_category_suggestions_5models.json` by default.
- Each audit item receives an `ai_issue_suggestions` object.
- The UI displays "AI 建议类别（仅供参考）" first.
- Suggested categories show vote counts such as `4/5`.
- Categories not suggested by AI are hidden under the collapsible "其他类别" section.
- No category is auto-selected. Human annotation remains the final decision.

## Example

For `AUDIT-001`, the five-model aggregation suggests:

- `entity_ambiguity`: 4 votes
- `unsupported_claim`: 1 vote

The UI therefore shows these two categories first and hides the remaining categories under "其他类别".

For `AUDIT-003`, the suggestion is:

- `entity_ambiguity`: 2 votes

This matches the known ambiguity in the "I Will Follow" example.

## Validation

Validated:

- Server loads 100 translated Chinese items.
- Server loads 100 suggestion objects.
- Current active human annotations remain 0.
- `scripts/build_issue_category_suggestions.py` passes Python compilation.
- `annotation_ui/server.py` passes Python compilation.
- `annotation_ui/app.js` passes `node --check`.

## Caveat

Using AI-suggested issue categories makes the workflow LLM-assisted. For the paper, this should be described as assisted audit. If we need a fully independent human audit subset, the UI should be launched without suggestions by passing a non-existent or empty suggestions file.
