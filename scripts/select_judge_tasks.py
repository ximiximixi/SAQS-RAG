#!/usr/bin/env python3
"""Select a balanced subset of judge tasks for representative smoke tests."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, default=Path("data/pilot/pilot_samples.jsonl"))
    parser.add_argument("--tasks", type=Path, default=Path("data/pilot/judge_tasks.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/pilot/judge_tasks_balanced_smoke.jsonl"))
    parser.add_argument("--per-dataset-label", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260424)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    samples = list(read_jsonl(args.samples))
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        buckets[(sample["dataset"], sample["gold_label"])].append(sample)

    selected_ids: set[str] = set()
    selected_samples: list[dict[str, Any]] = []
    for key in sorted(buckets):
        items = list(buckets[key])
        rng.shuffle(items)
        take = min(args.per_dataset_label, len(items))
        selected_samples.extend(items[:take])
        selected_ids.update(sample["sample_id"] for sample in items[:take])
        if take < args.per_dataset_label:
            print(f"[warn] {key}: requested {args.per_dataset_label}, available {take}")

    tasks = [task for task in read_jsonl(args.tasks) if task["sample_id"] in selected_ids]
    write_jsonl(args.out, tasks)

    print(f"Selected {len(selected_samples)} samples and {len(tasks)} tasks.")
    print("Samples by dataset/label:", {str(k): v for k, v in sorted(Counter((s["dataset"], s["gold_label"]) for s in selected_samples).items())})
    print("Tasks by dataset:", dict(sorted(Counter(t["dataset"] for t in tasks).items())))
    print("Tasks by prompt:", dict(sorted(Counter(t["prompt_id"] for t in tasks).items())))
    print("Tasks by order:", dict(sorted(Counter(t["evidence_order"] for t in tasks).items())))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
