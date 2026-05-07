#!/usr/bin/env python3
"""Create judge prompt tasks with prompt and evidence-order perturbations."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


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


def load_prompts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        prompts = json.load(handle)
    required = {"prompt_id", "system", "user_template"}
    for item in prompts:
        missing = required - set(item)
        if missing:
            raise ValueError(f"Prompt item missing fields {missing}: {item}")
    return prompts


def truncate_text(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def ordered_evidence(
    evidence: list[dict[str, Any]],
    order: str,
    sample_id: str,
) -> list[dict[str, Any]]:
    items = list(evidence)
    if order == "original":
        return items
    if order == "reversed":
        return list(reversed(items))
    if order == "shuffle_seed_1":
        digest = hashlib.md5(sample_id.encode("utf-8")).hexdigest()
        seed = int(digest[:8], 16) + 1
        rng = random.Random(seed)
        rng.shuffle(items)
        return items
    raise ValueError(f"Unknown evidence order: {order}")


def render_evidence(
    evidence: list[dict[str, Any]],
    order: str,
    sample_id: str,
    max_docs: int,
    max_chars_per_doc: int,
) -> str:
    selected = ordered_evidence(evidence, order, sample_id)[:max_docs]
    parts = []
    for idx, doc in enumerate(selected, start=1):
        original_id = doc.get("doc_id", f"d{idx}")
        text = truncate_text(str(doc.get("text") or ""), max_chars_per_doc)
        parts.append(f"[{idx}] doc_id={original_id}\n{text}")
    return "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, default=Path("data/pilot/pilot_samples.jsonl"))
    parser.add_argument("--prompts", type=Path, default=Path("configs/prompts/judge_prompts.json"))
    parser.add_argument("--out", type=Path, default=Path("data/pilot/judge_tasks.jsonl"))
    parser.add_argument("--max-docs", type=int, default=8)
    parser.add_argument("--max-chars-per-doc", type=int, default=1500)
    args = parser.parse_args()

    samples = list(read_jsonl(args.samples))
    prompts = load_prompts(args.prompts)
    orders = ["original", "reversed", "shuffle_seed_1"]

    tasks = []
    for sample in samples:
        for prompt in prompts:
            for order in orders:
                evidence_text = render_evidence(
                    sample.get("evidence") or [],
                    order,
                    sample["sample_id"],
                    args.max_docs,
                    args.max_chars_per_doc,
                )
                user = prompt["user_template"].format(
                    question=sample.get("question", ""),
                    evidence=evidence_text,
                    answer=sample.get("answer", ""),
                )
                task_id = f"{sample['sample_id']}__{prompt['prompt_id']}__{order}"
                tasks.append(
                    {
                        "task_id": task_id,
                        "sample_id": sample["sample_id"],
                        "dataset": sample["dataset"],
                        "gold_label": sample["gold_label"],
                        "gold_label_binary": sample["gold_label_binary"],
                        "prompt_id": prompt["prompt_id"],
                        "evidence_order": order,
                        "judge_input": {
                            "system": prompt["system"],
                            "user": user,
                        },
                        "meta": {
                            "source_id": sample.get("source_id"),
                            "gold_label_source": sample.get("gold_label_source"),
                            "max_docs": args.max_docs,
                            "max_chars_per_doc": args.max_chars_per_doc,
                            "num_original_evidence_docs": len(sample.get("evidence") or []),
                        },
                    }
                )

    write_jsonl(args.out, tasks)

    print(f"Wrote {len(tasks)} judge tasks to {args.out}")
    print("Samples:", len(samples))
    print("Prompts:", [item["prompt_id"] for item in prompts])
    print("Orders:", orders)
    print("By dataset:", dict(sorted(Counter(task["dataset"] for task in tasks).items())))
    print("By prompt:", dict(sorted(Counter(task["prompt_id"] for task in tasks).items())))
    print("By order:", dict(sorted(Counter(task["evidence_order"] for task in tasks).items())))


if __name__ == "__main__":
    main()
