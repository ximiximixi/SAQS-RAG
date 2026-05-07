#!/usr/bin/env python3
"""Build a small unified pilot set for calibrated RAG judge experiments."""

from __future__ import annotations

import argparse
import ast
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


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


def clean_text(value: Any, max_chars: int = 8000) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def normalize_gold(is_faithful: bool) -> tuple[str, bool]:
    return ("faithful" if is_faithful else "unfaithful", bool(is_faithful))


def ragtruth_task_question(src: dict[str, Any]) -> str:
    task_type = src.get("task_type")
    prompt = str(src.get("prompt") or "")
    source_info = src.get("source_info")

    if task_type == "Summary":
        first_line = prompt.splitlines()[0].strip() if prompt else ""
        return first_line or "Summarize the provided evidence."

    if task_type == "Data2txt":
        instruction = prompt.split("Structured data:")[0].strip()
        return instruction or "Write an objective overview based only on the provided structured data."

    if task_type == "QA":
        if isinstance(source_info, str):
            try:
                parsed = ast.literal_eval(source_info)
            except (SyntaxError, ValueError):
                parsed = None
            if isinstance(parsed, dict) and parsed.get("question"):
                return f"Briefly answer the following question: {parsed['question']}"
        prefix = prompt.split("Bear in mind")[0].strip()
        return prefix or "Answer the question based only on the provided passages."

    return prompt[:1000].strip() or "Evaluate the answer against the provided evidence."


def sample_balanced(
    rows: list[dict[str, Any]],
    per_label: int,
    seed: int,
    dataset_name: str,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[row["gold_label"]].append(row)

    selected: list[dict[str, Any]] = []
    for label in ("faithful", "unfaithful"):
        items = buckets[label]
        rng.shuffle(items)
        take = min(per_label, len(items))
        selected.extend(items[:take])
        if take < per_label:
            print(
                f"[warn] {dataset_name}: requested {per_label} {label} rows, "
                f"available {take}."
            )

    rng.shuffle(selected)
    return selected


def load_ragbench(raw_root: Path, per_label: int, seed: int) -> list[dict[str, Any]]:
    base = raw_root / "ragbench"
    rows: list[dict[str, Any]] = []
    for parquet_path in sorted(base.glob("*/test-*.parquet")):
        dataset_name = parquet_path.parent.name
        table = pq.read_table(parquet_path)
        for idx, row in enumerate(table.to_pylist()):
            adherence = row.get("adherence_score")
            if adherence is None:
                continue
            label, label_binary = normalize_gold(bool(adherence))
            documents = row.get("documents") or []
            evidence = []
            for doc_idx, doc in enumerate(documents):
                if isinstance(doc, dict):
                    text = doc.get("text") or doc.get("document") or doc.get("content") or doc
                    meta = {k: v for k, v in doc.items() if k not in {"text", "document", "content"}}
                else:
                    text = doc
                    meta = {}
                evidence.append(
                    {
                        "doc_id": f"d{doc_idx}",
                        "text": clean_text(text),
                        "meta": meta,
                    }
                )
            rows.append(
                {
                    "sample_id": f"ragbench_{dataset_name}_{row.get('id', idx)}",
                    "dataset": "ragbench",
                    "source_id": str(row.get("id", idx)),
                    "question": clean_text(row.get("question")),
                    "answer": clean_text(row.get("response")),
                    "evidence": evidence,
                    "gold_label": label,
                    "gold_label_binary": label_binary,
                    "gold_label_source": "adherence_score",
                    "meta": {
                        "ragbench_dataset": dataset_name,
                        "generation_model_name": row.get("generation_model_name"),
                        "annotating_model_name": row.get("annotating_model_name"),
                        "adherence_score": adherence,
                    },
                }
            )
    return sample_balanced(rows, per_label, seed + 11, "ragbench")


def load_ragtruth(raw_root: Path, per_label: int, seed: int) -> list[dict[str, Any]]:
    base = raw_root / "RAGTruth" / "dataset"
    source_info_path = base / "source_info.jsonl"
    response_path = base / "response.jsonl"
    sources = {row["source_id"]: row for row in read_jsonl(source_info_path)}

    rows: list[dict[str, Any]] = []
    for row in read_jsonl(response_path):
        if row.get("split") != "test":
            continue
        quality = row.get("quality") or {}
        quality_flags = quality if isinstance(quality, dict) else {}
        if quality_flags.get("response_abstain") or quality_flags.get("response_truncated"):
            continue
        src = sources.get(row.get("source_id"), {})
        labels = row.get("labels") or []
        is_faithful = len(labels) == 0
        label, label_binary = normalize_gold(is_faithful)
        label_types = sorted(
            {
                item.get("label_type")
                for item in labels
                if isinstance(item, dict) and item.get("label_type")
            }
        )
        evidence_text = src.get("source_info") or src.get("source") or ""
        rows.append(
                {
                    "sample_id": f"ragtruth_{row.get('id')}",
                    "dataset": "ragtruth",
                    "source_id": str(row.get("source_id")),
                    "question": clean_text(ragtruth_task_question(src)),
                "answer": clean_text(row.get("response")),
                "evidence": [
                    {
                        "doc_id": "source",
                        "text": clean_text(evidence_text),
                        "meta": {
                            "task_type": src.get("task_type"),
                            "source": src.get("source"),
                        },
                    }
                ],
                "gold_label": label,
                "gold_label_binary": label_binary,
                "gold_label_source": "ragtruth_labels",
                "meta": {
                    "task_type": src.get("task_type"),
                    "model": row.get("model"),
                    "temperature": row.get("temperature"),
                    "quality": quality,
                    "label_count": len(labels),
                    "label_types": label_types,
                },
            }
        )
    return sample_balanced(rows, per_label, seed + 23, "ragtruth")


def load_ramdocs(raw_root: Path, per_label: int, seed: int) -> list[dict[str, Any]]:
    path = raw_root / "RAMDocs" / "RAMDocs_test.jsonl"
    rng = random.Random(seed + 37)
    faithful: list[dict[str, Any]] = []
    unfaithful: list[dict[str, Any]] = []

    for idx, row in enumerate(read_jsonl(path)):
        documents = row.get("documents") or []
        evidence = []
        for doc_idx, doc in enumerate(documents):
            if isinstance(doc, dict):
                text = doc.get("text") or doc.get("document") or doc.get("content") or ""
                meta = {k: v for k, v in doc.items() if k not in {"text", "document", "content"}}
            else:
                text = doc
                meta = {}
            evidence.append(
                {
                    "doc_id": f"d{doc_idx}",
                    "text": clean_text(text),
                    "meta": meta,
                }
            )

        common = {
            "dataset": "ramdocs",
            "source_id": str(idx),
            "question": clean_text(row.get("question")),
            "evidence": evidence,
            "meta": {
                "disambig_entity": row.get("disambig_entity"),
                "gold_answers": row.get("gold_answers"),
                "wrong_answers": row.get("wrong_answers"),
                "num_documents": len(evidence),
            },
        }

        gold_answers = [clean_text(x, 500) for x in (row.get("gold_answers") or []) if clean_text(x, 500)]
        wrong_answers = [clean_text(x, 500) for x in (row.get("wrong_answers") or []) if clean_text(x, 500)]

        if gold_answers:
            label, label_binary = normalize_gold(True)
            answer = f"The answer is {gold_answers[0]}."
            faithful.append(
                {
                    **common,
                    "sample_id": f"ramdocs_{idx}_gold",
                    "answer": answer,
                    "gold_label": label,
                    "gold_label_binary": label_binary,
                    "gold_label_source": "constructed_gold_answer",
                }
            )
        if wrong_answers:
            label, label_binary = normalize_gold(False)
            answer = f"The answer is {wrong_answers[0]}."
            unfaithful.append(
                {
                    **common,
                    "sample_id": f"ramdocs_{idx}_wrong",
                    "answer": answer,
                    "gold_label": label,
                    "gold_label_binary": label_binary,
                    "gold_label_source": "constructed_wrong_answer",
                }
            )

    rng.shuffle(faithful)
    rng.shuffle(unfaithful)
    selected = faithful[:per_label] + unfaithful[:per_label]
    rng.shuffle(selected)
    if len(faithful) < per_label:
        print(f"[warn] ramdocs: requested {per_label} faithful rows, available {len(faithful)}.")
    if len(unfaithful) < per_label:
        print(f"[warn] ramdocs: requested {per_label} unfaithful rows, available {len(unfaithful)}.")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("data/pilot/pilot_samples.jsonl"))
    parser.add_argument("--seed", type=int, default=20260424)
    parser.add_argument("--per-dataset-label", type=int, default=25)
    args = parser.parse_args()

    all_rows: list[dict[str, Any]] = []
    all_rows.extend(load_ragbench(args.raw_root, args.per_dataset_label, args.seed))
    all_rows.extend(load_ragtruth(args.raw_root, args.per_dataset_label, args.seed))
    all_rows.extend(load_ramdocs(args.raw_root, args.per_dataset_label, args.seed))

    # Stable final order after per-dataset sampling.
    rng = random.Random(args.seed)
    rng.shuffle(all_rows)
    write_jsonl(args.out, all_rows)

    by_dataset = Counter(row["dataset"] for row in all_rows)
    by_dataset_label = Counter((row["dataset"], row["gold_label"]) for row in all_rows)
    by_label = Counter(row["gold_label"] for row in all_rows)

    print(f"Wrote {len(all_rows)} samples to {args.out}")
    print("By dataset:", dict(sorted(by_dataset.items())))
    print("By label:", dict(sorted(by_label.items())))
    print("By dataset/label:", {str(k): v for k, v in sorted(by_dataset_label.items())})


if __name__ == "__main__":
    main()
