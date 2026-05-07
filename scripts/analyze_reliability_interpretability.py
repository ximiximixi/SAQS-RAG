#!/usr/bin/env python3
"""Interpret reliability predictors with coefficients, importances, and ablations."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.linear_model")

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_reliability_prediction_experiments import (  # noqa: E402
    candidate_feature_sets,
    clean_target,
    make_model,
    make_preprocessor,
)


SELECTED_TARGETS = [
    ("item", "target_benchmark_mismatch"),
    ("item", "target_any_main_llm_wrong"),
    ("item", "target_human_unfaithful"),
    ("item", "target_old_or_strict_wrong"),
    ("verdict", "target_verdict_unreliable_strict"),
    ("verdict", "target_verdict_unreliable_covered"),
    ("verdict", "target_verdict_high_confidence_wrong"),
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=2)


def raw_feature_from_expanded(name: str, raw_features: list[str]) -> str:
    if "__" in name:
        name = name.split("__", 1)[1]
    if name in raw_features:
        return name
    # OneHotEncoder names are usually feature_value. Use the longest matching feature prefix.
    candidates = [feature for feature in raw_features if name == feature or name.startswith(feature + "_")]
    if candidates:
        return max(candidates, key=len)
    return name


def feature_group(feature: str) -> str:
    if feature in {
        "risk_multi_combined",
        "risk_qwen_combined",
        "risk_glm_combined",
        "per_task_binary_disagreement_rate",
        "model_majority_disagreement",
    }:
        return "risk"
    if (
        feature.startswith("disagree_")
        or "disagreement" in feature
        or "vote_" in feature
        or "unique_label_count" in feature
        or "unanimous" in feature
        or "top_vote" in feature
        or "label_count_" in feature
        or "label_fraction_" in feature
        or feature.startswith("agrees_with_")
        or feature.startswith("protocol_old_weak")
        or feature.startswith("protocol_strict_en")
    ):
        return "disagreement"
    if "confidence" in feature:
        return "confidence"
    if "_issue_" in feature:
        return "issue"
    if feature.startswith("text_"):
        return "text"
    if (
        feature
        in {
            "dataset",
            "primary_stratum",
            "candidate_strata",
            "condition",
            "protocol",
            "condition_type",
            "model_name",
            "verdict_label",
            "cross_main_majority_label",
            "cross_llm_majority_label",
        }
        or feature.endswith("_label")
        or "_is_" in feature
    ):
        return "label_protocol"
    return "other"


def fit_pipeline(df: pd.DataFrame, target: str, model_name: str, feature_set: str) -> tuple[Pipeline, pd.DataFrame, np.ndarray, list[str]]:
    data = clean_target(df, target)
    features = candidate_feature_sets(data, "verdict" if target.startswith("target_verdict") else "item")[feature_set]
    X = data[features].copy()
    y = data[target].to_numpy(dtype=int)
    preprocessor = make_preprocessor(X, features)
    pipeline = Pipeline(
        [
            ("preprocess", preprocessor),
            ("model", make_model(model_name)),
        ]
    )
    pipeline.fit(X, y)
    return pipeline, X, y, features


def coefficient_rows(level: str, target: str, model_name: str, feature_set: str, df: pd.DataFrame) -> list[dict[str, Any]]:
    pipeline, X, y, raw_features = fit_pipeline(df, target, model_name, feature_set)
    transformed_names = pipeline.named_steps["preprocess"].get_feature_names_out()
    coefs = pipeline.named_steps["model"].coef_[0]
    rows = []
    for expanded, coef in zip(transformed_names, coefs):
        raw = raw_feature_from_expanded(str(expanded), raw_features)
        rows.append(
            {
                "level": level,
                "target": target,
                "model": model_name,
                "feature_set": feature_set,
                "n": len(y),
                "positive_n": int(np.sum(y)),
                "expanded_feature": str(expanded),
                "raw_feature": raw,
                "feature_group": feature_group(raw),
                "coefficient": float(coef),
                "abs_coefficient": float(abs(coef)),
                "odds_ratio": float(math.exp(max(min(coef, 20), -20))),
                "direction": "increases_unreliability" if coef > 0 else "decreases_unreliability",
            }
        )
    return sorted(rows, key=lambda row: row["abs_coefficient"], reverse=True)


def forest_importance_rows(level: str, target: str, feature_set: str, df: pd.DataFrame) -> list[dict[str, Any]]:
    pipeline, X, y, raw_features = fit_pipeline(df, target, "random_forest", feature_set)
    transformed_names = pipeline.named_steps["preprocess"].get_feature_names_out()
    importances = pipeline.named_steps["model"].feature_importances_
    rows = []
    for expanded, importance in zip(transformed_names, importances):
        raw = raw_feature_from_expanded(str(expanded), raw_features)
        rows.append(
            {
                "level": level,
                "target": target,
                "model": "random_forest",
                "feature_set": feature_set,
                "n": len(y),
                "positive_n": int(np.sum(y)),
                "expanded_feature": str(expanded),
                "raw_feature": raw,
                "feature_group": feature_group(raw),
                "importance": float(importance),
            }
        )
    return sorted(rows, key=lambda row: row["importance"], reverse=True)


def aggregate_rows(rows: list[dict[str, Any]], value_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_raw: dict[tuple[str, str, str, str, str, str], float] = defaultdict(float)
    by_group: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    meta: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        raw_key = (
            row["level"],
            row["target"],
            row["model"],
            row["feature_set"],
            row["raw_feature"],
            row["feature_group"],
        )
        group_key = (row["level"], row["target"], row["model"], row["feature_set"], row["feature_group"])
        value = float(row[value_key])
        by_raw[raw_key] += value
        by_group[group_key] += value
        meta[raw_key] = row
        meta[group_key] = row

    raw_rows = []
    for key, value in by_raw.items():
        raw_rows.append(
            {
                "level": key[0],
                "target": key[1],
                "model": key[2],
                "feature_set": key[3],
                "raw_feature": key[4],
                "feature_group": key[5],
                "importance_type": value_key,
                "importance_value": value,
            }
        )
    group_rows = []
    for key, value in by_group.items():
        group_rows.append(
            {
                "level": key[0],
                "target": key[1],
                "model": key[2],
                "feature_set": key[3],
                "feature_group": key[4],
                "importance_type": value_key,
                "importance_value": value,
            }
        )
    raw_rows.sort(key=lambda row: (row["level"], row["target"], -row["importance_value"]))
    group_rows.sort(key=lambda row: (row["level"], row["target"], -row["importance_value"]))
    return raw_rows, group_rows


def ablation_summary(results_path: Path) -> list[dict[str, Any]]:
    rows = list(csv.DictReader(results_path.open("r", encoding="utf-8-sig")))
    out = []
    for level, target in SELECTED_TARGETS:
        sub = [
            row
            for row in rows
            if row.get("level") == level
            and row.get("target") == target
            and row.get("model") != "direct_score"
            and row.get("auprc")
            and not row.get("error")
        ]
        by_feature_set: dict[str, dict[str, Any]] = {}
        for row in sub:
            fs = row["feature_set"]
            if fs not in by_feature_set or float(row["auprc"]) > float(by_feature_set[fs]["auprc"]):
                by_feature_set[fs] = row
        best_all = by_feature_set.get("all_canonical")
        best_disagreement = by_feature_set.get("disagreement_only")
        best_risk = by_feature_set.get("risk_only")
        for fs, row in sorted(by_feature_set.items()):
            out.append(
                {
                    "level": level,
                    "target": target,
                    "feature_set": fs,
                    "best_model": row["model"],
                    "auroc": row.get("auroc", ""),
                    "auprc": row.get("auprc", ""),
                    "top20pct_precision": row.get("top20pct_precision", ""),
                    "top20pct_lift": row.get("top20pct_lift", ""),
                    "brier": row.get("brier", ""),
                    "delta_auprc_vs_risk_only": float(row["auprc"]) - float(best_risk["auprc"])
                    if best_risk and row.get("auprc") and best_risk.get("auprc")
                    else "",
                    "delta_auprc_vs_disagreement_only": float(row["auprc"]) - float(best_disagreement["auprc"])
                    if best_disagreement and row.get("auprc") and best_disagreement.get("auprc")
                    else "",
                    "delta_auprc_vs_all_canonical": float(row["auprc"]) - float(best_all["auprc"])
                    if best_all and row.get("auprc") and best_all.get("auprc")
                    else "",
                }
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features-dir", type=Path, default=Path("data/audit/reliability"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/audit/reliability/interpretability"))
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    item_df = pd.read_csv(args.features_dir / "item_level_features.csv")
    verdict_df = pd.read_csv(args.features_dir / "verdict_level_features.csv")

    coef_rows = []
    forest_rows = []
    for level, target in SELECTED_TARGETS:
        df = item_df if level == "item" else verdict_df
        positive_n = int(pd.to_numeric(df[target], errors="coerce").fillna(0).sum())
        if positive_n < 5:
            continue
        for model_name in ["logistic_l2", "logistic_l1"]:
            coef_rows.extend(coefficient_rows(level, target, model_name, "all_canonical", df))
        forest_rows.extend(forest_importance_rows(level, target, "all_canonical", df))

    coef_raw, coef_group = aggregate_rows(coef_rows, "abs_coefficient")
    forest_raw, forest_group = aggregate_rows(forest_rows, "importance")
    ablation_rows = ablation_summary(args.features_dir / "prediction_results.csv")

    write_csv(args.out_dir / "logistic_coefficients_expanded.csv", coef_rows)
    write_csv(args.out_dir / "logistic_coefficients_by_raw_feature.csv", coef_raw)
    write_csv(args.out_dir / "logistic_coefficients_by_feature_group.csv", coef_group)
    write_csv(args.out_dir / "random_forest_importance_expanded.csv", forest_rows)
    write_csv(args.out_dir / "random_forest_importance_by_raw_feature.csv", forest_raw)
    write_csv(args.out_dir / "random_forest_importance_by_feature_group.csv", forest_group)
    write_csv(args.out_dir / "feature_group_ablation_summary.csv", ablation_rows)

    summary = {
        "selected_targets": SELECTED_TARGETS,
        "n_logistic_expanded_rows": len(coef_rows),
        "n_forest_expanded_rows": len(forest_rows),
        "n_ablation_rows": len(ablation_rows),
        "note": "Interpretability models are fitted on the full canonical feature tables for explanation only; predictive performance comes from grouped/LOO CV in prediction_results.csv.",
    }
    write_json(args.out_dir / "interpretability_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
