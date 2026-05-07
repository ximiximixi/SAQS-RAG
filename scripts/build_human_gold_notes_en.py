#!/usr/bin/env python3
"""Build HumanGold-v1 annotation notes in English.

The output is a reporting-friendly human-gold file whose `notes` field is in
English. It preserves labels, confidence, issue categories, and timestamps.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "audit_id",
        "annotator_label",
        "annotator_confidence",
        "issue_categories",
        "notes",
        "updated_at",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def extract_json_array(text: str) -> list[dict[str, str]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[\s*\{.*\}\s*\]", text, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array")
    return parsed


def post_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
    enable_thinking: bool | None,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if enable_thinking is not None:
        payload["enable_thinking"] = enable_thinking
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices returned: {body}")
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def translate_batch(
    batch: list[dict[str, str]],
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float,
    retries: int,
    enable_thinking: bool | None,
) -> dict[str, str]:
    payload = [
        {
            "audit_id": row["audit_id"],
            "note": row.get("notes", ""),
        }
        for row in batch
        if row.get("notes", "").strip()
    ]
    if not payload:
        return {}

    system = (
        "You translate RAG audit annotation notes into concise academic English. "
        "Preserve factual meaning, entity names, issue distinctions, evidence indices, "
        "numbers, dates, and quoted titles. Do not add new judgments. Return valid JSON only."
    )
    user = f"""Translate the following human annotation notes into English.

Return exactly a JSON array of objects with keys:
- audit_id
- notes_en

Requirements:
- Keep each notes_en as 1-2 concise English sentences.
- Preserve labels implied by the note without strengthening or weakening the judgment.
- If the original note is empty, omit it from the array.

Input:
{json.dumps(payload, ensure_ascii=False)}
"""

    for attempt in range(retries + 1):
        try:
            text = post_chat_completion(
                base_url=base_url,
                api_key=api_key,
                model=model,
                system=system,
                user=user,
                temperature=0.0,
                max_tokens=4096,
                timeout=timeout,
                enable_thinking=enable_thinking,
            )
            parsed = extract_json_array(text)
            return {
                str(item["audit_id"]): str(item.get("notes_en", "")).strip()
                for item in parsed
                if item.get("audit_id")
            }
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(min(2**attempt, 8))
    return {}


def parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"", "auto", "none", "null"}:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Cannot parse boolean value: {value}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/audit/human_audit_annotations.csv"))
    parser.add_argument("--out-csv", type=Path, default=Path("data/audit/human_audit_annotations_en.csv"))
    parser.add_argument("--out-jsonl", type=Path, default=Path("data/audit/human_audit_annotations_en.jsonl"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--model", default="qwen3.6-max-preview")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--enable-thinking", default=os.environ.get("JUDGE_ENABLE_THINKING", "false"))
    args = parser.parse_args()

    load_dotenv(args.env_file)
    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL", "")
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    if not base_url or not api_key:
        raise SystemExit("Missing OPENAI_BASE_URL or OPENAI_API_KEY")
    enable_thinking = parse_optional_bool(args.enable_thinking)

    rows = read_csv(args.input)
    translations: dict[str, str] = {}
    for start in range(0, len(rows), args.batch_size):
        batch = rows[start : start + args.batch_size]
        translations.update(
            translate_batch(
                batch,
                base_url=base_url,
                api_key=api_key,
                model=args.model,
                timeout=args.timeout,
                retries=args.retries,
                enable_thinking=enable_thinking,
            )
        )
        print(f"Translated batch {start + 1}-{min(start + args.batch_size, len(rows))}")

    out_rows = []
    missing = []
    for row in rows:
        original_note = row.get("notes", "").strip()
        translated = translations.get(row["audit_id"], "").strip()
        if original_note and not translated:
            missing.append(row["audit_id"])
        out_rows.append(
            {
                "audit_id": row["audit_id"],
                "annotator_label": row["annotator_label"],
                "annotator_confidence": row["annotator_confidence"],
                "issue_categories": row["issue_categories"],
                "notes": translated,
                "updated_at": row["updated_at"],
            }
        )

    if missing:
        raise SystemExit(f"Missing translations for: {', '.join(missing)}")
    write_csv(args.out_csv, out_rows)
    write_jsonl(args.out_jsonl, out_rows)
    print(f"Wrote {len(out_rows)} rows to {args.out_csv} and {args.out_jsonl}")


if __name__ == "__main__":
    main()
