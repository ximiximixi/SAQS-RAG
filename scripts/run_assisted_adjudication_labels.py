#!/usr/bin/env python3
"""Run assisted adjudication labels with frozen audit definitions.

This script gives an adjudicator model:

- the audit item,
- the frozen label definitions,
- the five previous weak-model opinions and translated reasons,
- the five-model issue-category suggestions.

It writes separate JSONL/CSV outputs and never touches human annotation files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ISSUE_CATEGORIES = [
    "unsupported_claim",
    "contradiction",
    "evidence_conflict",
    "insufficient_evidence",
    "entity_ambiguity",
    "temporal_conflict",
    "numeric_error",
    "over_specific_answer",
    "answer_format_issue",
    "benchmark_ambiguous",
    "other",
]


ISSUE_ZH = {
    "unsupported_claim": "答案包含证据没有支持的重要内容",
    "contradiction": "答案与证据直接矛盾",
    "evidence_conflict": "证据内部互相冲突",
    "insufficient_evidence": "证据不足以判断答案",
    "entity_ambiguity": "同名实体、指代不清或多个可能对象",
    "temporal_conflict": "时间状态或不同时点信息冲突",
    "numeric_error": "年份、日期、数量、比例等错误",
    "over_specific_answer": "答案比证据更具体",
    "answer_format_issue": "答案格式不符合问题要求",
    "benchmark_ambiguous": "题目本身不清楚，可能有多个合理答案",
    "other": "其他问题",
}


LABELS = {"faithful", "unfaithful", "insufficient"}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key.startswith("export "):
                key = key[len("export ") :].strip()
            if key and key not in os.environ:
                os.environ[key] = value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def export_csv(jsonl_path: Path, csv_path: Path) -> None:
    rows = list(read_jsonl(jsonl_path)) if jsonl_path.exists() else []
    fieldnames = [
        "audit_id",
        "model",
        "label",
        "confidence",
        "issue_categories",
        "notes",
        "definition_applied",
        "parsed_ok",
        "finish_reason",
        "latency_sec",
        "error",
    ]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "audit_id": row.get("audit_id"),
                    "model": row.get("model"),
                    "label": row.get("label"),
                    "confidence": row.get("confidence"),
                    "issue_categories": "|".join(row.get("issue_categories") or []),
                    "notes": row.get("notes"),
                    "definition_applied": row.get("definition_applied"),
                    "parsed_ok": row.get("parsed_ok"),
                    "finish_reason": row.get("finish_reason"),
                    "latency_sec": row.get("latency_sec"),
                    "error": row.get("error"),
                }
            )


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        row["audit_id"]
        for row in read_jsonl(path)
        if row.get("audit_id") and not row.get("error")
    }


def parse_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"auto", "none", "null"}:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Cannot parse boolean value: {value}")


def normalize_label(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in LABELS:
        return text
    if "unfaithful" in text or "unsupported" in text or "contradict" in text:
        return "unfaithful"
    if "insufficient" in text or "not enough" in text or "inadequate" in text:
        return "insufficient"
    if "faithful" in text or "supported" in text:
        return "faithful"
    return None


def parse_confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        match = re.search(r"(\d+(?:\.\d+)?)", str(value))
        if not match:
            return None
        confidence = float(match.group(1))
    if 1 < confidence <= 100:
        confidence /= 100.0
    if confidence < 0 or confidence > 1:
        return None
    return confidence


def parse_categories(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[|,;]", value)
    elif isinstance(value, list):
        parts = value
    else:
        parts = []
    categories = []
    for item in parts:
        text = str(item).strip()
        if text in ISSUE_CATEGORIES and text not in categories:
            categories.append(text)
    return categories


def parse_model_text(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                parsed = None
    if not isinstance(parsed, dict):
        return {
            "parsed_ok": False,
            "label": normalize_label(text),
            "confidence": None,
            "issue_categories": [],
            "notes": None,
            "definition_applied": None,
        }
    return {
        "parsed_ok": True,
        "label": normalize_label(parsed.get("label") or parsed.get("annotator_label") or parsed.get("verdict")),
        "confidence": parse_confidence(parsed.get("confidence") or parsed.get("annotator_confidence")),
        "issue_categories": parse_categories(parsed.get("issue_categories")),
        "notes": parsed.get("notes") or parsed.get("reason") or parsed.get("rationale"),
        "definition_applied": parsed.get("definition_applied") or parsed.get("policy_note"),
    }


def truncate_text(text: Any, max_chars: int) -> str:
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def render_evidence(item: dict[str, Any], max_docs: int, max_chars_per_doc: int) -> list[dict[str, str]]:
    docs = []
    for idx, doc in enumerate((item.get("evidence") or [])[:max_docs], start=1):
        docs.append(
            {
                "idx": str(idx),
                "doc_id": str(doc.get("doc_id", "")),
                "text_zh": truncate_text(doc.get("text_zh") or doc.get("text"), max_chars_per_doc),
            }
        )
    return docs


def compact_reviews(reviews_obj: dict[str, Any], max_reason_chars: int) -> dict[str, Any]:
    out = {
        "ai_majority_label": reviews_obj.get("ai_majority_label", ""),
        "ai_label_vote_counts": reviews_obj.get("ai_label_vote_counts", ""),
        "ai_top_label_vote_fraction": reviews_obj.get("ai_top_label_vote_fraction", ""),
        "model_reviews": [],
    }
    for review in reviews_obj.get("model_reviews", []):
        out["model_reviews"].append(
            {
                "model": review.get("model", ""),
                "label": review.get("label", ""),
                "confidence": review.get("confidence", ""),
                "issues": review.get("issues", []),
                "reason_zh": truncate_text(review.get("reason_zh") or review.get("reason"), max_reason_chars),
            }
        )
    return out


def build_messages(
    item: dict[str, Any],
    reviews: dict[str, Any],
    suggestions: dict[str, Any],
    max_docs: int,
    max_chars_per_doc: int,
    max_reason_chars: int,
) -> tuple[str, str]:
    system = (
        "You are a strict RAG faithfulness audit adjudicator. Apply the frozen "
        "annotation policy exactly. Use only the provided evidence and provided "
        "AI reference opinions; do not use outside knowledge. Return valid JSON only."
    )
    issue_defs = {key: ISSUE_ZH[key] for key in ISSUE_CATEGORIES}
    payload = {
        "audit_id": item.get("audit_id", ""),
        "question_zh": item.get("question_zh") or item.get("question", ""),
        "answer_zh": item.get("answer_zh") or item.get("answer", ""),
        "evidence_zh": render_evidence(item, max_docs, max_chars_per_doc),
        "five_ai_reference": compact_reviews(reviews, max_reason_chars),
        "five_ai_suggested_issue_categories": {
            "suggested_issue_categories": suggestions.get("suggested_issue_categories", []),
            "issue_category_counts": suggestions.get("issue_category_counts", {}),
        },
    }
    user = f"""请按冻结版人工审计标准，给该 RAG 答案填写最终复审标注。

主标签只能三选一：
- faithful: 答案中的每个重要 claim 都被给定证据支持，并且答案没有忽略关键冲突或歧义。
- unfaithful: 答案与证据矛盾；添加证据不支持的重要事实；在冲突/歧义证据中无依据地选择一边；实体/日期/数字错误；或在证据冲突/不完整时把不确定内容说成确定答案。
- insufficient: 证据本身不够，无法判断答案是 faithful 还是 unfaithful。少用；如果答案提出证据不支持的说法，优先 unfaithful。

关键边界：
- 某一段证据支持答案，但其他证据显示明显实体歧义/多个候选答案/冲突时，不能机械标 faithful。
- 如果答案直接给确定结论而没有处理这种歧义或冲突，通常偏向 unfaithful，并选择相应 issue categories。
- AI 参考意见只能作为参考；你必须按上面的冻结定义重新裁决。

可选 issue_categories 及含义：
{json.dumps(issue_defs, ensure_ascii=False)}

输入数据：
{json.dumps(payload, ensure_ascii=False)}

只返回一个压缩 JSON 对象，键必须为：
audit_id, label, confidence, issue_categories, notes, definition_applied

要求：
- label 必须是 faithful/unfaithful/insufficient。
- confidence 是 0 到 1。
- issue_categories 是数组，只能使用给定类别。
- notes 用中文，1-2 句，说明关键证据、歧义或冲突。
- definition_applied 用中文，简短说明你用了哪条冻结边界规则。
"""
    return system, user


def extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def extract_finish_reason(response: dict[str, Any]) -> str | None:
    choices = response.get("choices") or []
    if not choices:
        return None
    return choices[0].get("finish_reason")


def post_chat_completion(
    url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
    enable_thinking: bool | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if enable_thinking is not None:
        payload["enable_thinking"] = enable_thinking

    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def normalize_base_url(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    return base_url + "/chat/completions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, default=Path("data/audit/human_audit_batch_100_blind_zh.jsonl"))
    parser.add_argument("--ai-reviews", type=Path, default=Path("data/audit/ai_weak_reviews_5models_zh.json"))
    parser.add_argument("--suggestions", type=Path, default=Path("data/audit/ai_issue_category_suggestions_5models.json"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--out-jsonl", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=768)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-docs", type=int, default=10)
    parser.add_argument("--max-chars-per-doc", type=int, default=1000)
    parser.add_argument("--max-reason-chars", type=int, default=260)
    parser.add_argument("--enable-thinking", default=os.environ.get("JUDGE_ENABLE_THINKING", "false"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(args.env_file)
    if not args.base_url:
        args.base_url = os.environ.get("OPENAI_BASE_URL", "")
    if not args.api_key:
        args.api_key = os.environ.get("OPENAI_API_KEY", "")
    if not args.base_url or not args.api_key:
        raise SystemExit("Missing OPENAI_BASE_URL or OPENAI_API_KEY")

    url = normalize_base_url(args.base_url)
    enable_thinking = parse_optional_bool(args.enable_thinking)
    items = list(read_jsonl(args.batch))
    reviews_all = load_json(args.ai_reviews).get("items", {})
    suggestions_all = load_json(args.suggestions).get("items", {})
    done = completed_ids(args.out_jsonl)
    pending = [item for item in items if item.get("audit_id") not in done]
    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"Loaded {len(items)} items; {len(done)} completed; {len(pending)} pending.")
    print(f"Endpoint: {url}")
    print(f"Model: {args.model}")
    print(f"Enable thinking: {enable_thinking}")

    if args.dry_run:
        if pending:
            audit_id = pending[0]["audit_id"]
            system, user = build_messages(
                pending[0],
                reviews_all.get(audit_id, {}),
                suggestions_all.get(audit_id, {}),
                args.max_docs,
                args.max_chars_per_doc,
                args.max_reason_chars,
            )
            print("First pending:", audit_id)
            print("System chars:", len(system), "User chars:", len(user))
            print(user[:2000])
        return

    failures = 0
    for idx, item in enumerate(pending, start=1):
        audit_id = item["audit_id"]
        system, user = build_messages(
            item,
            reviews_all.get(audit_id, {}),
            suggestions_all.get(audit_id, {}),
            args.max_docs,
            args.max_chars_per_doc,
            args.max_reason_chars,
        )
        row: dict[str, Any] | None = None
        last_error = None
        for attempt in range(1, args.retries + 1):
            try:
                started = time.time()
                response = post_chat_completion(
                    url=url,
                    api_key=args.api_key,
                    model=args.model,
                    system=system,
                    user=user,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    timeout=args.timeout,
                    enable_thinking=enable_thinking,
                )
                latency = time.time() - started
                content = extract_content(response)
                parsed = parse_model_text(content)
                row = {
                    "audit_id": audit_id,
                    "model": args.model,
                    "label": parsed["label"],
                    "confidence": parsed["confidence"],
                    "issue_categories": parsed["issue_categories"],
                    "notes": parsed["notes"],
                    "definition_applied": parsed["definition_applied"],
                    "parsed_ok": parsed["parsed_ok"],
                    "raw_text": content,
                    "finish_reason": extract_finish_reason(response),
                    "usage": response.get("usage"),
                    "latency_sec": round(latency, 3),
                    "error": None,
                }
                last_error = None
                break
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if attempt < args.retries:
                    time.sleep(min(2**attempt, 8))
        if row is None:
            failures += 1
            row = {
                "audit_id": audit_id,
                "model": args.model,
                "label": None,
                "confidence": None,
                "issue_categories": [],
                "notes": None,
                "definition_applied": None,
                "parsed_ok": False,
                "raw_text": None,
                "finish_reason": None,
                "usage": None,
                "latency_sec": None,
                "error": last_error,
            }
            print(f"ERROR {audit_id}: {last_error}", file=sys.stderr)
        append_jsonl(args.out_jsonl, row)
        export_csv(args.out_jsonl, args.out_csv)
        if idx % 10 == 0 or idx == len(pending):
            print(f"Processed {idx}/{len(pending)}; failures={failures}")
        time.sleep(args.sleep)

    print(f"Finished. Wrote {len(pending)} new rows. Failures: {failures}")
    print(f"CSV: {args.out_csv}")


if __name__ == "__main__":
    main()
