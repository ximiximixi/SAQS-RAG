#!/usr/bin/env python3
"""Translate the blind audit batch into Simplified Chinese via an API model.

The script keeps the original English fields and adds Chinese fields:

- question_zh
- answer_zh
- evidence[*].text_zh

It writes incrementally to a JSONL file and can resume safely.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable


DEFAULT_MODEL = "qwen3.6-max-preview"


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


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for row in read_jsonl(path):
        audit_id = row.get("audit_id")
        if audit_id and row.get("translation_status") == "ok":
            ids.add(audit_id)
    return ids


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


def truncate_text(text: str, max_chars: int) -> str:
    text = str(text or "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def build_messages(item: dict[str, Any], max_docs: int, max_chars_per_doc: int) -> tuple[str, str]:
    docs = []
    for doc in (item.get("evidence") or [])[:max_docs]:
        docs.append(
            {
                "doc_id": doc.get("doc_id", ""),
                "text": truncate_text(doc.get("text", ""), max_chars_per_doc),
            }
        )
    payload = {
        "audit_id": item.get("audit_id", ""),
        "question": item.get("question", ""),
        "answer": item.get("answer", ""),
        "evidence": docs,
    }
    system = (
        "You are a professional academic translator. Translate RAG audit items "
        "from English to Simplified Chinese. Do not answer the question and do "
        "not evaluate faithfulness. Return valid JSON only."
    )
    user = f"""Translate the following audit item into Simplified Chinese.

Requirements:
- Preserve audit_id and doc_id exactly.
- Translate question, answer, and every evidence text.
- Keep names, titles, dates, numbers, citations, and bracketed document markers accurate.
- Do not add explanations, judgments, or labels.
- If the source text is noisy, translate as literally as possible.
- Return exactly one minified JSON object with keys:
  audit_id, question_zh, answer_zh, evidence_zh.
- evidence_zh must be an array of objects with keys doc_id and text_zh.

Source JSON:
{json.dumps(payload, ensure_ascii=False)}
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


def validate_translation(item: dict[str, Any], translated: dict[str, Any]) -> None:
    if translated.get("audit_id") != item.get("audit_id"):
        raise ValueError("audit_id mismatch")
    if not translated.get("question_zh") or not translated.get("answer_zh"):
        raise ValueError("missing translated question or answer")
    evidence_zh = translated.get("evidence_zh")
    if not isinstance(evidence_zh, list):
        raise ValueError("evidence_zh must be a list")
    source_docs = (item.get("evidence") or [])
    if len(evidence_zh) != len(source_docs[: len(evidence_zh)]):
        # Do not require exact full length when input is max-doc limited, but each returned
        # doc must be structurally usable.
        pass
    source_ids = {str(doc.get("doc_id", "")) for doc in source_docs}
    for doc in evidence_zh:
        if not isinstance(doc, dict):
            raise ValueError("evidence_zh entries must be objects")
        if str(doc.get("doc_id", "")) not in source_ids:
            raise ValueError(f"unknown translated doc_id: {doc.get('doc_id')}")
        if not doc.get("text_zh"):
            raise ValueError(f"missing text_zh for doc_id: {doc.get('doc_id')}")


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

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
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


def merge_translation(item: dict[str, Any], translated: dict[str, Any], model: str) -> dict[str, Any]:
    evidence_by_id = {
        str(doc.get("doc_id", "")): doc.get("text_zh", "")
        for doc in translated.get("evidence_zh", [])
        if isinstance(doc, dict)
    }
    merged_evidence = []
    for doc in item.get("evidence") or []:
        doc_id = str(doc.get("doc_id", ""))
        new_doc = dict(doc)
        new_doc["text_zh"] = evidence_by_id.get(doc_id, "")
        merged_evidence.append(new_doc)

    merged = dict(item)
    merged["question_zh"] = translated.get("question_zh", "")
    merged["answer_zh"] = translated.get("answer_zh", "")
    merged["evidence"] = merged_evidence
    merged["translation_model"] = model
    merged["translation_status"] = "ok"
    merged["translated_at_unix"] = time.time()
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/audit/human_audit_batch_100_blind.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/audit/human_audit_batch_100_blind_zh.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-docs", type=int, default=8)
    parser.add_argument("--max-chars-per-doc", type=int, default=1200)
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
    items = list(read_jsonl(args.input))
    done = completed_ids(args.output)
    pending = [item for item in items if item.get("audit_id") not in done]
    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"Loaded {len(items)} items; {len(done)} completed; {len(pending)} pending.")
    print(f"Endpoint: {url}")
    print(f"Model: {args.model}")
    print(f"Enable thinking: {enable_thinking}")

    if args.dry_run:
        if pending:
            system, user = build_messages(pending[0], args.max_docs, args.max_chars_per_doc)
            print("First pending:", pending[0].get("audit_id"))
            print("System chars:", len(system), "User chars:", len(user))
        return

    failures = 0
    for index, item in enumerate(pending, start=1):
        audit_id = item.get("audit_id", "")
        system, user = build_messages(item, args.max_docs, args.max_chars_per_doc)
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
                content = extract_content(response)
                parsed = parse_json_object(content)
                validate_translation(item, parsed)
                row = merge_translation(item, parsed, args.model)
                row["translation_latency_sec"] = round(time.time() - started, 3)
                row["translation_usage"] = response.get("usage")
                append_jsonl(args.output, row)
                last_error = None
                break
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if attempt < args.retries:
                    time.sleep(min(2**attempt, 8))
        if last_error:
            failures += 1
            error_row = dict(item)
            error_row["translation_model"] = args.model
            error_row["translation_status"] = "error"
            error_row["translation_error"] = re.sub(r"\s+", " ", last_error)[:500]
            append_jsonl(args.output, error_row)
            print(f"ERROR {audit_id}: {last_error}", file=sys.stderr)

        if index % 10 == 0 or index == len(pending):
            print(f"Processed {index}/{len(pending)}; failures={failures}")
        time.sleep(args.sleep)

    print(f"Finished. Failures: {failures}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
