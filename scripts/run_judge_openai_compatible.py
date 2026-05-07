#!/usr/bin/env python3
"""Run judge tasks through an OpenAI-compatible chat completions endpoint."""

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


def completed_task_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for row in read_jsonl(path):
        task_id = row.get("task_id")
        if task_id:
            ids.add(task_id)
    return ids


def normalize_verdict(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z_\- ]+", "", text)
    if "unfaithful" in text or "unsupported" in text or "not supported" in text:
        return "unfaithful"
    if "insufficient" in text or "unknown" in text or "cannot" in text:
        return "insufficient"
    if "faithful" in text or "supported" in text:
        return "faithful"
    return None


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


def parse_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        match = re.search(r"(\d+(?:\.\d+)?)", str(value))
        if not match:
            return None
        confidence = float(match.group(1))
    if 1 < confidence <= 100:
        confidence = confidence / 100.0
    if confidence < 0 or confidence > 1:
        return None
    return confidence


def parse_judge_text(text: str) -> dict[str, Any]:
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
            "verdict": normalize_verdict(text),
            "confidence": None,
            "reason": None,
        }
    return {
        "parsed_ok": True,
        "verdict": normalize_verdict(parsed.get("verdict")),
        "confidence": parse_confidence(parsed.get("confidence")),
        "reason": parsed.get("reason"),
    }


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
    thinking_budget: int | None,
) -> dict[str, Any]:
    payload = {
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
    if thinking_budget is not None:
        payload["thinking_budget"] = thinking_budget
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
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
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts)
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
    parser.add_argument("--tasks", type=Path, default=Path("data/pilot/judge_tasks.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/pilot/judge_outputs.jsonl"))
    parser.add_argument("--model", default=os.getenv("JUDGE_MODEL", "gpt-4o-mini"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=384)
    parser.add_argument("--enable-thinking", default=os.getenv("JUDGE_ENABLE_THINKING", "auto"))
    parser.add_argument("--thinking-budget", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tasks = list(read_jsonl(args.tasks))
    if args.limit is not None:
        tasks = tasks[: args.limit]

    done = set() if args.no_resume else completed_task_ids(args.out)
    pending = [task for task in tasks if task["task_id"] not in done]
    url = args.base_url.rstrip("/") + "/chat/completions"
    enable_thinking = parse_optional_bool(args.enable_thinking)

    print(f"Loaded {len(tasks)} tasks; {len(done)} already completed; {len(pending)} pending.")
    print(f"Endpoint: {url}")
    print(f"Model: {args.model}")
    print(f"Enable thinking: {enable_thinking}")
    print(f"Output: {args.out}")

    if args.dry_run:
        if pending:
            first = pending[0]
            print("First pending task:", first["task_id"])
            print("First user prompt chars:", len(first["judge_input"]["user"]))
        return

    api_key = os.getenv(args.api_key_env)
    if not api_key:
        print(f"Missing API key environment variable: {args.api_key_env}", file=sys.stderr)
        sys.exit(2)

    failures = 0
    for idx, task in enumerate(pending, start=1):
        system = task["judge_input"]["system"]
        user = task["judge_input"]["user"]
        row: dict[str, Any] | None = None
        last_error = None

        for attempt in range(1, args.retries + 1):
            try:
                started = time.time()
                response = post_chat_completion(
                    url=url,
                    api_key=api_key,
                    model=args.model,
                    system=system,
                    user=user,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    timeout=args.timeout,
                    enable_thinking=enable_thinking,
                    thinking_budget=args.thinking_budget,
                )
                elapsed = time.time() - started
                content = extract_content(response)
                finish_reason = extract_finish_reason(response)
                parsed = parse_judge_text(content)
                row = {
                    "task_id": task["task_id"],
                    "sample_id": task["sample_id"],
                    "dataset": task["dataset"],
                    "gold_label": task["gold_label"],
                    "prompt_id": task["prompt_id"],
                    "evidence_order": task["evidence_order"],
                    "model": args.model,
                    "enable_thinking": enable_thinking,
                    "thinking_budget": args.thinking_budget,
                    "verdict": parsed["verdict"],
                    "confidence": parsed["confidence"],
                    "reason": parsed["reason"],
                    "parsed_ok": parsed["parsed_ok"],
                    "raw_text": content,
                    "finish_reason": finish_reason,
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
                "task_id": task["task_id"],
                "sample_id": task["sample_id"],
                "dataset": task["dataset"],
                "gold_label": task["gold_label"],
                "prompt_id": task["prompt_id"],
                "evidence_order": task["evidence_order"],
                "model": args.model,
                "enable_thinking": enable_thinking,
                "thinking_budget": args.thinking_budget,
                "verdict": None,
                "confidence": None,
                "reason": None,
                "parsed_ok": False,
                "raw_text": None,
                "usage": None,
                "latency_sec": None,
                "error": last_error,
            }

        append_jsonl(args.out, row)
        if idx % 25 == 0 or row["error"]:
            print(f"Processed {idx}/{len(pending)} pending; failures={failures}")
        time.sleep(args.sleep)

    print(f"Finished. Wrote {len(pending)} new rows. Failures: {failures}")


if __name__ == "__main__":
    main()
