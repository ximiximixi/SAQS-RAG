#!/usr/bin/env python3
"""Translate five-model weak-label reasons into Simplified Chinese."""

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
from typing import Any


LABEL_ZH = {
    "faithful": "忠实",
    "unfaithful": "不忠实",
    "insufficient": "证据不足",
    "tie": "平票",
    "missing": "缺失",
}

ISSUE_ZH = {
    "answer_format_issue": "回答格式问题",
    "benchmark_ambiguous": "基准/题目歧义",
    "contradiction": "与证据矛盾",
    "entity_ambiguity": "实体歧义",
    "evidence_conflict": "证据冲突",
    "insufficient_evidence": "证据不足",
    "numeric_error": "数字错误",
    "other": "其他",
    "over_specific_answer": "回答过于具体",
    "temporal_conflict": "时间冲突",
    "unsupported_claim": "无证据支持",
}


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


def normalize_base_url(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    return base_url + "/chat/completions"


def model_slug(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


def parse_issues(value: str) -> list[str]:
    issues = []
    for part in (value or "").replace(",", "|").replace(";", "|").split("|"):
        issue = part.strip()
        if issue and issue not in issues:
            issues.append(issue)
    return issues


def read_models(summary_path: Path, fieldnames: list[str]) -> list[dict[str, str]]:
    if summary_path.exists():
        with summary_path.open("r", encoding="utf-8") as handle:
            summary = json.load(handle)
        models = []
        for model in summary.get("models", []):
            slug = model_slug(model)
            if f"{slug}_reason" in fieldnames:
                models.append({"model": model, "slug": slug})
        if models:
            return models

    models = []
    for field in fieldnames:
        if field.endswith("_reason"):
            slug = field[: -len("_reason")]
            models.append({"model": slug, "slug": slug})
    return models


def collect_reviews(rows: list[dict[str, str]], models: list[dict[str, str]]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    by_item: dict[str, Any] = {}
    flat_reviews: list[dict[str, str]] = []
    for row in rows:
        audit_id = row["audit_id"]
        item_reviews = []
        for model in models:
            slug = model["slug"]
            label = row.get(f"{slug}_label", "")
            confidence = row.get(f"{slug}_confidence", "")
            issues = parse_issues(row.get(f"{slug}_issues", ""))
            reason = row.get(f"{slug}_reason", "")
            review_id = f"{audit_id}::{slug}"
            review = {
                "review_id": review_id,
                "audit_id": audit_id,
                "model": model["model"],
                "model_slug": slug,
                "label": label,
                "label_zh": LABEL_ZH.get(label, label),
                "confidence": confidence,
                "issues": issues,
                "issues_zh": [ISSUE_ZH.get(issue, issue) for issue in issues],
                "reason": reason,
                "reason_zh": "",
            }
            item_reviews.append(review)
            if reason.strip():
                flat_reviews.append({"review_id": review_id, "reason": reason})
        by_item[audit_id] = {
            "audit_id": audit_id,
            "ai_majority_label": row.get("majority_label", ""),
            "ai_majority_label_zh": LABEL_ZH.get(row.get("majority_label", ""), row.get("majority_label", "")),
            "ai_label_vote_counts": row.get("label_vote_counts", ""),
            "ai_top_label_vote_fraction": row.get("top_label_vote_fraction", ""),
            "model_reviews": item_reviews,
        }
    return by_item, flat_reviews


def batched(items: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_messages(batch: list[dict[str, str]]) -> tuple[str, str]:
    system = (
        "You are a professional academic translator. Translate short LLM audit "
        "rationales from English to Simplified Chinese. Return valid JSON only."
    )
    user = f"""Translate each reason into Simplified Chinese.

Requirements:
- Preserve review_id exactly.
- Translate only the reason text.
- Do not add new judgments, explanations, labels, or citations.
- Keep entity names, dates, evidence indices such as [1], and quoted titles accurate.
- Return exactly one minified JSON object with key translations.
- translations must be an array of objects with keys review_id and reason_zh.

Source:
{json.dumps({"reviews": batch}, ensure_ascii=False)}
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


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("translation response is not a JSON object")
    return parsed


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


def export_csv(path: Path, by_item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "audit_id",
        "model",
        "label",
        "label_zh",
        "confidence",
        "issues",
        "issues_zh",
        "reason",
        "reason_zh",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for audit_id in sorted(by_item):
            for review in by_item[audit_id]["model_reviews"]:
                writer.writerow(
                    {
                        "audit_id": audit_id,
                        "model": review["model"],
                        "label": review["label"],
                        "label_zh": review["label_zh"],
                        "confidence": review["confidence"],
                        "issues": "|".join(review["issues"]),
                        "issues_zh": "|".join(review["issues_zh"]),
                        "reason": review["reason"],
                        "reason_zh": review["reason_zh"],
                    }
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/audit/weak_label_comparison_5models/weak_label_comparison_by_item.csv"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/audit/weak_label_comparison_5models/weak_label_comparison_summary.json"),
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("data/audit/ai_weak_reviews_5models_zh.json"),
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("data/audit/ai_weak_reviews_5models_zh.csv"),
    )
    parser.add_argument("--model", default="qwen3.6-max-preview")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--enable-thinking", default=os.environ.get("JUDGE_ENABLE_THINKING", "false"))
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

    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        models = read_models(args.summary, reader.fieldnames or [])

    by_item, flat_reviews = collect_reviews(rows, models)
    translated: dict[str, str] = {}
    url = normalize_base_url(args.base_url)
    enable_thinking = parse_optional_bool(args.enable_thinking)
    batches = batched(flat_reviews, args.batch_size)

    print(f"Loaded {len(rows)} items, {len(models)} models, {len(flat_reviews)} reasons.")
    print(f"Endpoint: {url}")
    print(f"Model: {args.model}")
    print(f"Enable thinking: {enable_thinking}")

    failures = 0
    for index, batch in enumerate(batches, start=1):
        system, user = build_messages(batch)
        last_error = None
        for attempt in range(1, args.retries + 1):
            try:
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
                parsed = parse_json_object(extract_content(response))
                translations = parsed.get("translations", [])
                if not isinstance(translations, list):
                    raise ValueError("translations must be a list")
                for item in translations:
                    if isinstance(item, dict) and item.get("review_id"):
                        translated[str(item["review_id"])] = str(item.get("reason_zh", "")).strip()
                last_error = None
                break
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if attempt < args.retries:
                    time.sleep(min(2**attempt, 8))
        if last_error:
            failures += 1
            print(f"ERROR batch {index}: {last_error}", file=sys.stderr)
        print(f"Processed batch {index}/{len(batches)}; translated={len(translated)}; failures={failures}")
        time.sleep(args.sleep)

    missing = []
    for item in by_item.values():
        for review in item["model_reviews"]:
            review_id = review["review_id"]
            if review["reason"].strip():
                review["reason_zh"] = translated.get(review_id, "")
                if not review["reason_zh"]:
                    missing.append(review_id)

    output = {
        "source": str(args.input),
        "translation_model": args.model,
        "n_items": len(by_item),
        "n_models": len(models),
        "n_reasons": len(flat_reviews),
        "n_missing_translations": len(missing),
        "missing_review_ids": missing,
        "items": by_item,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
    export_csv(args.out_csv, by_item)

    print(f"Finished. Missing translations: {len(missing)}")
    print(f"JSON: {args.out_json}")
    print(f"CSV: {args.out_csv}")
    if missing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
