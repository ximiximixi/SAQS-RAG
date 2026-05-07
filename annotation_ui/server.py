#!/usr/bin/env python3
"""Tiny local annotation UI for the RAG judge audit batch."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
DEFAULT_BATCH_EN = WORKSPACE / "data" / "audit" / "human_audit_batch_100_blind.jsonl"
DEFAULT_BATCH_ZH = WORKSPACE / "data" / "audit" / "human_audit_batch_100_blind_zh.jsonl"
DEFAULT_BATCH = DEFAULT_BATCH_ZH if DEFAULT_BATCH_ZH.exists() else DEFAULT_BATCH_EN
DEFAULT_SUGGESTIONS = WORKSPACE / "data" / "audit" / "ai_issue_category_suggestions_5models.json"
DEFAULT_AI_REVIEWS = WORKSPACE / "data" / "audit" / "ai_weak_reviews_5models_zh.json"
DEFAULT_OUT = WORKSPACE / "data" / "audit" / "human_audit_annotations.jsonl"
DEFAULT_CSV = WORKSPACE / "data" / "audit" / "human_audit_annotations.csv"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_annotations(path: Path) -> dict[str, dict[str, Any]]:
    annotations = {}
    for row in read_jsonl(path):
        audit_id = row.get("audit_id")
        if audit_id:
            annotations[audit_id] = row
    return annotations


def load_suggestions(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    items = data.get("items", {})
    return items if isinstance(items, dict) else {}


def load_ai_reviews(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    items = data.get("items", {})
    return items if isinstance(items, dict) else {}


def export_csv(path: Path, annotations: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "audit_id",
        "annotator_label",
        "annotator_confidence",
        "issue_categories",
        "notes",
        "updated_at",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for audit_id in sorted(annotations):
            row = annotations[audit_id]
            writer.writerow(
                {
                    "audit_id": audit_id,
                    "annotator_label": row.get("annotator_label", ""),
                    "annotator_confidence": row.get("annotator_confidence", ""),
                    "issue_categories": "|".join(row.get("issue_categories", []))
                    if isinstance(row.get("issue_categories"), list)
                    else row.get("issue_categories", ""),
                    "notes": row.get("notes", ""),
                    "updated_at": row.get("updated_at", ""),
                }
            )


class AppState:
    def __init__(
        self,
        batch_path: Path,
        out_path: Path,
        csv_path: Path,
        suggestions_path: Path,
        ai_reviews_path: Path,
    ) -> None:
        self.batch_path = batch_path
        self.out_path = out_path
        self.csv_path = csv_path
        self.suggestions_path = suggestions_path
        self.ai_reviews_path = ai_reviews_path
        self.lock = threading.Lock()
        self.items = read_jsonl(batch_path)
        self.annotations = load_annotations(out_path)
        self.suggestions = load_suggestions(suggestions_path)
        self.ai_reviews = load_ai_reviews(ai_reviews_path)

    def merged_items(self) -> list[dict[str, Any]]:
        merged = []
        for item in self.items:
            audit_id = item["audit_id"]
            annotation = self.annotations.get(audit_id, {})
            suggestion = self.suggestions.get(audit_id, {})
            ai_review = self.ai_reviews.get(audit_id, {})
            merged.append(
                {
                    **item,
                    "ai_issue_suggestions": {
                        "suggested_issue_categories": suggestion.get("suggested_issue_categories", []),
                        "all_ai_issue_categories": suggestion.get("all_ai_issue_categories", []),
                        "issue_category_counts": suggestion.get("issue_category_counts", {}),
                        "ai_majority_label": suggestion.get("ai_majority_label", ""),
                        "ai_label_vote_counts": suggestion.get("ai_label_vote_counts", ""),
                        "ai_top_label_vote_fraction": suggestion.get("ai_top_label_vote_fraction", ""),
                    },
                    "ai_weak_reviews": {
                        "ai_majority_label": ai_review.get("ai_majority_label", ""),
                        "ai_majority_label_zh": ai_review.get("ai_majority_label_zh", ""),
                        "ai_label_vote_counts": ai_review.get("ai_label_vote_counts", ""),
                        "ai_top_label_vote_fraction": ai_review.get("ai_top_label_vote_fraction", ""),
                        "model_reviews": ai_review.get("model_reviews", []),
                    },
                    "saved_annotation": {
                        "annotator_label": annotation.get("annotator_label", ""),
                        "annotator_confidence": annotation.get("annotator_confidence", ""),
                        "issue_categories": annotation.get("issue_categories", []),
                        "notes": annotation.get("notes", ""),
                        "updated_at": annotation.get("updated_at", ""),
                    },
                }
            )
        return merged

    def save_annotation(self, payload: dict[str, Any]) -> dict[str, Any]:
        audit_id = str(payload.get("audit_id", "")).strip()
        if not audit_id:
            raise ValueError("Missing audit_id")
        valid_ids = {item["audit_id"] for item in self.items}
        if audit_id not in valid_ids:
            raise ValueError(f"Unknown audit_id: {audit_id}")

        label = str(payload.get("annotator_label", "")).strip()
        if label not in {"", "faithful", "unfaithful", "insufficient"}:
            raise ValueError("annotator_label must be faithful, unfaithful, insufficient, or empty")

        confidence = payload.get("annotator_confidence", "")
        if confidence != "":
            confidence = float(confidence)
            if confidence < 0 or confidence > 1:
                raise ValueError("annotator_confidence must be between 0 and 1")

        categories = payload.get("issue_categories", [])
        if isinstance(categories, str):
            categories = [item.strip() for item in categories.split("|") if item.strip()]
        if not isinstance(categories, list):
            categories = []

        row = {
            "audit_id": audit_id,
            "annotator_label": label,
            "annotator_confidence": confidence,
            "issue_categories": categories,
            "notes": str(payload.get("notes", "")).strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.lock:
            self.annotations[audit_id] = row
            write_jsonl(self.out_path, [self.annotations[key] for key in sorted(self.annotations)])
            export_csv(self.csv_path, self.annotations)
        return row


def make_handler(state: AppState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[server] {self.address_string()} - {fmt % args}")

        def send_json(self, data: Any, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_file(self, path: Path) -> None:
            if not path.exists() or not path.is_file():
                self.send_error(404)
                return
            body = path.read_bytes()
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            if path.suffix == ".js":
                content_type = "text/javascript; charset=utf-8"
            elif path.suffix in {".html", ".css"}:
                content_type = f"text/{path.suffix[1:]}; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/items":
                self.send_json(
                    {
                        "items": state.merged_items(),
                        "total": len(state.items),
                        "annotated": len([a for a in state.annotations.values() if a.get("annotator_label")]),
                    }
                )
                return
            if parsed.path == "/api/export":
                query = parse_qs(parsed.query)
                fmt = query.get("format", ["jsonl"])[0]
                if fmt == "csv":
                    self.send_file(state.csv_path)
                else:
                    self.send_file(state.out_path)
                return
            if parsed.path in {"/", "/index.html"}:
                self.send_file(ROOT / "index.html")
                return
            requested = (ROOT / parsed.path.lstrip("/")).resolve()
            if ROOT in requested.parents or requested == ROOT:
                self.send_file(requested)
            else:
                self.send_error(403)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/save":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                saved = state.save_annotation(payload)
                self.send_json({"ok": True, "annotation": saved})
            except Exception as exc:  # noqa: BLE001
                self.send_json({"ok": False, "error": str(exc)}, status=400)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--suggestions", type=Path, default=DEFAULT_SUGGESTIONS)
    parser.add_argument("--ai-reviews", type=Path, default=DEFAULT_AI_REVIEWS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    state = AppState(args.batch, args.out, args.csv, args.suggestions, args.ai_reviews)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"Annotation UI running at http://{args.host}:{args.port}")
    print(f"Batch: {args.batch}")
    print(f"Suggestions: {args.suggestions}")
    print(f"AI reviews: {args.ai_reviews}")
    print(f"Annotations JSONL: {args.out}")
    print(f"Annotations CSV: {args.csv}")
    server.serve_forever()


if __name__ == "__main__":
    main()
