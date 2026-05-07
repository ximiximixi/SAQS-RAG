#!/usr/bin/env python3
"""Run strict independent judge labels with the frozen audit policy.

This is intentionally different from assisted adjudication:

- no previous AI labels,
- no previous AI reasons,
- no previous issue suggestions,
- only question, answer, evidence, and the frozen label policy.
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


ISSUE_DEFS = {
    "unsupported_claim": "the answer contains an important claim not supported by evidence",
    "contradiction": "the answer directly contradicts evidence",
    "evidence_conflict": "the evidence contains conflicting statements",
    "insufficient_evidence": "the evidence is not enough to decide",
    "entity_ambiguity": "the question/evidence contains ambiguous or multiple possible entities",
    "temporal_conflict": "time-sensitive statements conflict or use the wrong time frame",
    "numeric_error": "year, date, quantity, number, or ratio error",
    "over_specific_answer": "the answer is more specific than the evidence supports",
    "answer_format_issue": "the answer format does not match the question",
    "benchmark_ambiguous": "the question itself is ambiguous and may have multiple reasonable answers",
    "other": "other issue",
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
    with path.open("r", encoding="utf-8-sig") as handle:
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


def build_messages(
    item: dict[str, Any],
    max_docs: int,
    max_chars_per_doc: int,
) -> tuple[str, str]:
    system = (
        "You are a strict independent RAG faithfulness judge. Apply the frozen "
        "annotation policy exactly. Use only the provided question, answer, and evidence. "
        "Do not use outside knowledge. Return valid JSON only."
    )
    payload = {
        "audit_id": item.get("audit_id", ""),
        "question_zh": item.get("question_zh") or item.get("question", ""),
        "answer_zh": item.get("answer_zh") or item.get("answer", ""),
        "evidence_zh": render_evidence(item, max_docs, max_chars_per_doc),
    }
    user = f"""Strictly label whether the RAG answer is faithful to the provided evidence.

Frozen label definitions:
- faithful: every important claim in the answer is supported by the provided evidence, and the answer does not ignore important conflict or ambiguity.
- unfaithful: the answer contradicts evidence; adds important unsupported facts; selects one side of conflicting/ambiguous evidence without sufficient support; gives a wrong entity/date/number; or presents uncertainty as certainty when evidence is conflicting or incomplete.
- insufficient: the evidence itself is not enough to determine whether the answer is faithful or unfaithful. Use sparingly. If the answer makes an unsupported or over-certain claim, prefer unfaithful.

Critical boundary rules:
- Do not mark faithful only because one passage supports the answer if other evidence creates clear entity ambiguity, multiple plausible answers, or conflict.
- If the answer gives a definite conclusion without handling such ambiguity/conflict, usually mark unfaithful and choose the relevant issue categories.
- Use only the evidence below. Do not use outside knowledge.

Allowed issue_categories:
{json.dumps(ISSUE_DEFS, ensure_ascii=False)}

Audit item:
{json.dumps(payload, ensure_ascii=False)}

Return exactly one minified JSON object with keys:
audit_id, label, confidence, issue_categories, notes, definition_applied.

Requirements:
- label must be faithful, unfaithful, or insufficient.
- confidence must be 0 to 1.
- issue_categories must be a JSON array using only the allowed categories.
- notes must be in Chinese, 1-2 short sentences.
- definition_applied must be in Chinese, briefly naming the boundary rule used.
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
    items = list(read_jsonl(args.batch))
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
            system, user = build_messages(
                pending[0],
                args.max_docs,
                args.max_chars_per_doc,
            )
            print("First pending:", pending[0]["audit_id"])
            print("System chars:", len(system), "User chars:", len(user))
            print(user[:2000])
        return

    failures = 0
    for idx, item in enumerate(pending, start=1):
        audit_id = item["audit_id"]
        system, user = build_messages(item, args.max_docs, args.max_chars_per_doc)
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
