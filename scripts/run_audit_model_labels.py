#!/usr/bin/env python3
"""Run large-model weak labels for the blinded human audit batch."""

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


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


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
        "reason",
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
                    "reason": row.get("reason"),
                    "parsed_ok": row.get("parsed_ok"),
                    "finish_reason": row.get("finish_reason"),
                    "latency_sec": row.get("latency_sec"),
                    "error": row.get("error"),
                }
            )


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {row["audit_id"] for row in read_jsonl(path) if row.get("audit_id") and not row.get("error")}


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
    text = re.sub(r"[^a-z_\- ]+", "", text)
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
            "reason": None,
        }
    return {
        "parsed_ok": True,
        "label": normalize_label(parsed.get("label") or parsed.get("annotator_label") or parsed.get("verdict")),
        "confidence": parse_confidence(parsed.get("confidence") or parsed.get("annotator_confidence")),
        "issue_categories": parse_categories(parsed.get("issue_categories")),
        "reason": parsed.get("reason") or parsed.get("notes"),
    }


def render_evidence(item: dict[str, Any], max_docs: int, max_chars_per_doc: int) -> str:
    parts = []
    for idx, doc in enumerate((item.get("evidence") or [])[:max_docs], start=1):
        text = str(doc.get("text") or "").strip()
        if len(text) > max_chars_per_doc:
            text = text[:max_chars_per_doc].rstrip() + "..."
        parts.append(f"[{idx}]\n{text}")
    return "\n\n".join(parts)


def build_messages(item: dict[str, Any], max_docs: int, max_chars_per_doc: int) -> tuple[str, str]:
    system = (
        "You are an independent audit reviewer for RAG answer faithfulness. "
        "Use only the provided evidence. Return valid JSON only."
    )
    categories = ", ".join(ISSUE_CATEGORIES)
    user = f"""Audit whether the answer is faithful to the evidence.

Labels:
- faithful: every important answer claim is supported by the evidence.
- unfaithful: the answer contradicts evidence or adds important unsupported facts.
- insufficient: the evidence is not enough to judge support or contradiction.

Use only the evidence. Do not use outside knowledge.

Issue categories may include: {categories}

Audit ID:
{item["audit_id"]}

Question:
{item.get("question", "")}

Evidence:
{render_evidence(item, max_docs, max_chars_per_doc)}

Answer:
{item.get("answer", "")}

Return exactly one minified JSON object with keys:
audit_id, label, confidence, issue_categories, reason.
label must be faithful, unfaithful, or insufficient.
confidence must be 0 to 1.
issue_categories must be a JSON array.
reason must be at most 35 words.
"""
    return system, user


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
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return ""


def extract_finish_reason(response: dict[str, Any]) -> str | None:
    choices = response.get("choices") or []
    if not choices:
        return None
    return choices[0].get("finish_reason")


def main() -> None:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--env-file", type=Path, default=Path(".env"))
    pre_args, _ = pre_parser.parse_known_args()
    load_dotenv(pre_args.env_file)

    parser = argparse.ArgumentParser(parents=[pre_parser])
    parser.add_argument("--batch", type=Path, default=Path("data/audit/human_audit_batch_100_blind.jsonl"))
    parser.add_argument("--out-jsonl", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=384)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--enable-thinking", default=os.getenv("JUDGE_ENABLE_THINKING", "false"))
    parser.add_argument("--max-docs", type=int, default=8)
    parser.add_argument("--max-chars-per-doc", type=int, default=1200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv(args.api_key_env)
    if not api_key and not args.dry_run:
        print(f"Missing API key environment variable: {args.api_key_env}", file=sys.stderr)
        sys.exit(2)

    items = list(read_jsonl(args.batch))
    if args.limit is not None:
        items = items[: args.limit]
    done = completed_ids(args.out_jsonl)
    pending = [item for item in items if item["audit_id"] not in done]
    url = args.base_url.rstrip("/") + "/chat/completions"
    enable_thinking = parse_optional_bool(args.enable_thinking)

    print(f"Loaded {len(items)} items; {len(done)} completed; {len(pending)} pending.")
    print(f"Endpoint: {url}")
    print(f"Model: {args.model}")
    print(f"Enable thinking: {enable_thinking}")

    if args.dry_run:
        if pending:
            system, user = build_messages(pending[0], args.max_docs, args.max_chars_per_doc)
            print("First pending:", pending[0]["audit_id"])
            print("System chars:", len(system), "User chars:", len(user))
        return

    failures = 0
    for idx, item in enumerate(pending, start=1):
        system, user = build_messages(item, args.max_docs, args.max_chars_per_doc)
        row: dict[str, Any] | None = None
        last_error = None
        for attempt in range(1, args.retries + 1):
            try:
                started = time.time()
                response = post_chat_completion(
                    url=url,
                    api_key=api_key or "",
                    model=args.model,
                    system=system,
                    user=user,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    timeout=args.timeout,
                    enable_thinking=enable_thinking,
                )
                elapsed = time.time() - started
                content = extract_content(response)
                parsed = parse_model_text(content)
                row = {
                    "audit_id": item["audit_id"],
                    "model": args.model,
                    "label": parsed["label"],
                    "confidence": parsed["confidence"],
                    "issue_categories": parsed["issue_categories"],
                    "reason": parsed["reason"],
                    "parsed_ok": parsed["parsed_ok"],
                    "raw_text": content,
                    "finish_reason": extract_finish_reason(response),
                    "usage": response.get("usage"),
                    "latency_sec": round(elapsed, 3),
                    "error": None,
                }
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code}: {body[:1000]}"
            except Exception as exc:  # noqa: BLE001
                last_error = repr(exc)
            time.sleep(min(8.0, args.sleep * (2**attempt)))

        if row is None:
            failures += 1
            row = {
                "audit_id": item["audit_id"],
                "model": args.model,
                "label": None,
                "confidence": None,
                "issue_categories": [],
                "reason": None,
                "parsed_ok": False,
                "raw_text": None,
                "finish_reason": None,
                "usage": None,
                "latency_sec": None,
                "error": last_error,
            }
        append_jsonl(args.out_jsonl, row)
        if idx % 10 == 0 or row["error"]:
            print(f"Processed {idx}/{len(pending)}; failures={failures}")
        time.sleep(args.sleep)

    export_csv(args.out_jsonl, args.out_csv)
    print(f"Finished. Wrote {len(pending)} new rows. Failures: {failures}")
    print(f"CSV: {args.out_csv}")


if __name__ == "__main__":
    main()
