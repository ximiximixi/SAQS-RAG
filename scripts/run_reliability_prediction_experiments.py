#!/usr/bin/env python3
"""Run reliability prediction experiments on canonical feature tables."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import warnings
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
    from sklearn.model_selection import GroupKFold, LeaveOneOut
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
except ModuleNotFoundError as exc:  # pragma: no cover - user-facing environment hint
    raise SystemExit(
        "Missing sklearn/pandas/numpy. Run this script with the bundled workspace Python "
        "reported by load_workspace_dependencies, or install scikit-learn, pandas, and numpy."
    ) from exc


SEED = 20260506

warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")

ITEM_TARGETS = [
    "target_human_unfaithful",
    "target_benchmark_mismatch",
    "target_any_main_llm_wrong",
    "target_old_or_strict_wrong",
    "target_strict_en_majority_wrong",
]

VERDICT_TARGETS = [
    "target_verdict_unreliable_strict",
    "target_verdict_unreliable_covered",
    "target_verdict_high_confidence_wrong",
]

ID_COLUMNS = {
    "audit_id",
    "sample_id",
    "verdict_id",
    "human_label",
    "human_confidence",
    "human_issue_categories",
    "human_notes",
    "verdict_issue_categories",
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def to_numeric_or_nan(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace("", np.nan), errors="coerce")


def is_numeric_feature(df: pd.DataFrame, col: str) -> bool:
    series = to_numeric_or_nan(df[col])
    non_missing = df[col].replace("", np.nan).notna().sum()
    if non_missing == 0:
        return True
    return series.notna().sum() == non_missing


def clean_target(df: pd.DataFrame, target: str) -> pd.DataFrame:
    out = df.copy()
    out[target] = pd.to_numeric(out[target].replace("", np.nan), errors="coerce")
    out = out[out[target].notna()].copy()
    out[target] = out[target].astype(int)
    return out


def metric_or_blank(fn, y_true: np.ndarray, y_score: np.ndarray) -> float | str:
    if len(set(y_true.tolist())) < 2:
        return ""
    try:
        return float(fn(y_true, y_score))
    except Exception:
        return ""


def top_precision(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float | str:
    if len(y_true) == 0:
        return ""
    k = min(k, len(y_true))
    order = np.argsort(-y_score)[:k]
    return float(np.mean(y_true[order]))


def summarize_predictions(
    *,
    level: str,
    target: str,
    model_name: str,
    feature_set: str,
    y_true: np.ndarray,
    y_score: np.ndarray,
    groups: np.ndarray | None = None,
    n_bootstrap: int = 300,
) -> dict[str, Any]:
    n = len(y_true)
    positive_n = int(np.sum(y_true))
    base_rate = positive_n / n if n else 0.0
    top20_k = max(1, math.ceil(0.2 * n))
    summary: dict[str, Any] = {
        "level": level,
        "target": target,
        "model": model_name,
        "feature_set": feature_set,
        "n": n,
        "positive_n": positive_n,
        "base_rate": base_rate,
        "auroc": metric_or_blank(roc_auc_score, y_true, y_score),
        "auprc": metric_or_blank(average_precision_score, y_true, y_score),
        "brier": float(brier_score_loss(y_true, y_score)) if len(set(y_true.tolist())) >= 2 else "",
        "top5_precision": top_precision(y_true, y_score, 5),
        "top10_precision": top_precision(y_true, y_score, 10),
        "top20_precision": top_precision(y_true, y_score, 20),
        "top20pct_k": top20_k,
        "top20pct_precision": top_precision(y_true, y_score, top20_k),
    }
    for key in ["top5_precision", "top10_precision", "top20_precision", "top20pct_precision"]:
        value = summary[key]
        summary[key.replace("precision", "lift")] = float(value) / base_rate if value != "" and base_rate else ""

    boot_metrics = {"auroc": [], "auprc": [], "top20pct_precision": [], "brier": []}
    rng = random.Random(SEED + len(target) + len(model_name) + len(feature_set))
    if groups is None:
        index_units = list(range(n))
        for _ in range(n_bootstrap):
            sample_idx = [rng.choice(index_units) for _ in index_units]
            yt = y_true[sample_idx]
            ys = y_score[sample_idx]
            if len(set(yt.tolist())) < 2:
                continue
            boot_metrics["auroc"].append(float(roc_auc_score(yt, ys)))
            boot_metrics["auprc"].append(float(average_precision_score(yt, ys)))
            boot_metrics["brier"].append(float(brier_score_loss(yt, ys)))
            boot_metrics["top20pct_precision"].append(top_precision(yt, ys, max(1, math.ceil(0.2 * len(yt)))))
    else:
        group_values = sorted(set(groups.tolist()))
        group_to_idx = {group: np.where(groups == group)[0] for group in group_values}
        for _ in range(n_bootstrap):
            sampled_groups = [rng.choice(group_values) for _ in group_values]
            sample_idx = np.concatenate([group_to_idx[group] for group in sampled_groups])
            yt = y_true[sample_idx]
            ys = y_score[sample_idx]
            if len(set(yt.tolist())) < 2:
                continue
            boot_metrics["auroc"].append(float(roc_auc_score(yt, ys)))
            boot_metrics["auprc"].append(float(average_precision_score(yt, ys)))
            boot_metrics["brier"].append(float(brier_score_loss(yt, ys)))
            boot_metrics["top20pct_precision"].append(top_precision(yt, ys, max(1, math.ceil(0.2 * len(yt)))))

    for metric, values in boot_metrics.items():
        values = [value for value in values if value != ""]
        if values:
            summary[f"{metric}_ci95_low"] = float(np.quantile(values, 0.025))
            summary[f"{metric}_ci95_high"] = float(np.quantile(values, 0.975))
        else:
            summary[f"{metric}_ci95_low"] = ""
            summary[f"{metric}_ci95_high"] = ""
    return summary


def make_preprocessor(df: pd.DataFrame, feature_cols: list[str]) -> ColumnTransformer:
    numeric_cols = [col for col in feature_cols if is_numeric_feature(df, col)]
    categorical_cols = [col for col in feature_cols if col not in numeric_cols]
    for col in numeric_cols:
        df[col] = to_numeric_or_nan(df[col])
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, numeric_cols),
            ("categorical", categorical, categorical_cols),
        ],
        remainder="drop",
    )


def make_model(model_name: str):
    if model_name == "logistic_l2":
        return LogisticRegression(
            penalty="l2",
            C=1.0,
            class_weight="balanced",
            solver="liblinear",
            max_iter=2000,
            random_state=SEED,
        )
    if model_name == "logistic_l1":
        return LogisticRegression(
            penalty="l1",
            C=0.5,
            class_weight="balanced",
            solver="liblinear",
            max_iter=2000,
            random_state=SEED,
        )
    if model_name == "random_forest":
        return RandomForestClassifier(
            n_estimators=250,
            max_depth=4,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=SEED,
        )
    raise ValueError(f"Unknown model: {model_name}")


def cross_validated_scores(
    df: pd.DataFrame,
    target: str,
    feature_cols: list[str],
    *,
    level: str,
    model_name: str,
    groups: pd.Series | None = None,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    data = clean_target(df, target)
    if len(set(data[target].tolist())) < 2:
        raise ValueError(f"Target {target} has fewer than two classes")
    X = data[feature_cols].copy()
    y = data[target].to_numpy(dtype=int)
    scores = np.zeros(len(data), dtype=float)
    if level == "item":
        splitter = LeaveOneOut()
        splits = splitter.split(X, y)
    else:
        group_values = data[groups.name].to_numpy()
        splitter = GroupKFold(n_splits=5)
        splits = splitter.split(X, y, group_values)

    for train_idx, test_idx in splits:
        y_train = y[train_idx]
        if len(set(y_train.tolist())) < 2:
            scores[test_idx] = float(np.mean(y_train))
            continue
        train_df = X.iloc[train_idx].copy()
        test_df = X.iloc[test_idx].copy()
        preprocessor = make_preprocessor(train_df, feature_cols)
        pipeline = Pipeline(
            [
                ("preprocess", preprocessor),
                ("model", make_model(model_name)),
            ]
        )
        pipeline.fit(train_df, y_train)
        scores[test_idx] = pipeline.predict_proba(test_df)[:, 1]
    return y, scores, data


def candidate_feature_sets(df: pd.DataFrame, level: str) -> dict[str, list[str]]:
    all_cols = [
        col
        for col in df.columns
        if col not in ID_COLUMNS
        and not col.startswith("target_")
        and not col.startswith("human_")
        and col not in {"sample_id", "verdict_id"}
    ]

    risk = [
        col
        for col in all_cols
        if col
        in {
            "risk_multi_combined",
            "risk_qwen_combined",
            "risk_glm_combined",
            "per_task_binary_disagreement_rate",
            "model_majority_disagreement",
        }
    ]
    disagreement = [
        col
        for col in all_cols
        if col.startswith("disagree_")
        or "disagreement" in col
        or "vote_" in col
        or "unique_label_count" in col
        or "unanimous" in col
        or "top_vote" in col
        or "label_count_" in col
        or "label_fraction_" in col
        or col.startswith("agrees_with_")
        or col.endswith("_vote_margin")
        or col.endswith("_vote_entropy")
        or col.startswith("protocol_old_weak")
        or col.startswith("protocol_strict_en")
    ]
    confidence = [
        col
        for col in all_cols
        if "confidence" in col and not col.startswith("human_")
    ]
    issue = [
        col
        for col in all_cols
        if "_issue_" in col and not col.startswith("human_")
    ]
    text = [col for col in all_cols if col.startswith("text_")]
    label_protocol = [
        col
        for col in all_cols
        if col
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
        or col.endswith("_label")
        or "_is_" in col
    ]

    def uniq(cols: list[str]) -> list[str]:
        seen = set()
        out = []
        for col in cols:
            if col in all_cols and col not in seen:
                seen.add(col)
                out.append(col)
        return out

    return {
        "risk_only": uniq(risk),
        "disagreement_only": uniq(disagreement),
        "confidence_only": uniq(confidence),
        "issue_only": uniq(issue),
        "text_only": uniq(text),
        "label_protocol_only": uniq(label_protocol),
        "risk_disagreement": uniq(risk + disagreement),
        "risk_disagreement_confidence": uniq(risk + disagreement + confidence),
        "all_canonical": uniq(risk + disagreement + confidence + issue + text + label_protocol),
    }


def direct_score_columns(df: pd.DataFrame, level: str) -> dict[str, pd.Series]:
    scores: dict[str, pd.Series] = {}
    for col in [
        "risk_multi_combined",
        "risk_qwen_combined",
        "risk_glm_combined",
        "per_task_binary_disagreement_rate",
        "main_condition_pairwise_disagreement_count",
    ]:
        if col in df:
            scores[col] = to_numeric_or_nan(df[col]).fillna(0)
    if level == "item":
        for col in [
            "old_plus_strict_individual_vote_entropy",
            "old_plus_strict_individual_issue_total_count",
            "strict_en_vote_entropy",
            "old_weak_vote_entropy",
        ]:
            if col in df:
                scores[col] = to_numeric_or_nan(df[col]).fillna(0)
        if "old_plus_strict_individual_confidence_mean" in df:
            conf = to_numeric_or_nan(df["old_plus_strict_individual_confidence_mean"])
            scores["inverse_mean_confidence"] = 1 - conf.fillna(conf.median())
    else:
        for col in [
            "verdict_confidence",
            "verdict_issue_total_count",
            "protocol_old_weak_vote_entropy",
            "protocol_strict_en_vote_entropy",
        ]:
            if col in df and col != "verdict_confidence":
                scores[col] = to_numeric_or_nan(df[col]).fillna(0)
        if "verdict_confidence" in df:
            conf = to_numeric_or_nan(df["verdict_confidence"])
            scores["inverse_verdict_confidence"] = 1 - conf.fillna(conf.median())
    return scores


def evaluate_direct_scores(
    df: pd.DataFrame,
    targets: list[str],
    *,
    level: str,
    groups_col: str | None,
    n_bootstrap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries = []
    predictions = []
    score_map = direct_score_columns(df, level)
    for target in targets:
        data = clean_target(df, target)
        if len(data) == 0 or len(set(data[target].tolist())) < 2:
            continue
        y = data[target].to_numpy(dtype=int)
        groups = data[groups_col].to_numpy() if groups_col else None
        for score_name, score_series in score_map.items():
            score = score_series.loc[data.index].astype(float).to_numpy()
            if np.nanmax(score) > np.nanmin(score):
                score = (score - np.nanmin(score)) / (np.nanmax(score) - np.nanmin(score))
            else:
                score = np.zeros_like(score)
            summaries.append(
                summarize_predictions(
                    level=level,
                    target=target,
                    model_name="direct_score",
                    feature_set=score_name,
                    y_true=y,
                    y_score=score,
                    groups=groups,
                    n_bootstrap=n_bootstrap,
                )
            )
            for idx, (_, row) in enumerate(data.iterrows()):
                predictions.append(
                    {
                        "level": level,
                        "target": target,
                        "model": "direct_score",
                        "feature_set": score_name,
                        "audit_id": row.get("audit_id", ""),
                        "row_id": row.get("verdict_id", row.get("audit_id", "")),
                        "y_true": int(y[idx]),
                        "y_score": float(score[idx]),
                    }
                )
    return summaries, predictions


def evaluate_models(
    df: pd.DataFrame,
    targets: list[str],
    *,
    level: str,
    groups_col: str | None,
    n_bootstrap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    feature_sets = candidate_feature_sets(df, level)
    model_feature_plan: list[tuple[str, str]] = []
    for feature_set in [
        "risk_only",
        "disagreement_only",
        "confidence_only",
        "issue_only",
        "label_protocol_only",
        "risk_disagreement",
        "risk_disagreement_confidence",
        "all_canonical",
    ]:
        model_feature_plan.append(("logistic_l2", feature_set))
    model_feature_plan.extend(
        [
            ("logistic_l1", "all_canonical"),
            ("random_forest", "all_canonical"),
        ]
    )

    summaries = []
    predictions = []
    for target in targets:
        target_data = clean_target(df, target)
        if len(target_data) == 0 or len(set(target_data[target].tolist())) < 2:
            continue
        positive_n = int(target_data[target].sum())
        if level == "item" and positive_n < 5:
            # Too few positives for stable supervised item-level fitting. Direct scores still run.
            continue
        for model_name, feature_set in model_feature_plan:
            feature_cols = feature_sets[feature_set]
            if not feature_cols:
                continue
            try:
                y, score, used = cross_validated_scores(
                    df,
                    target,
                    feature_cols,
                    level=level,
                    model_name=model_name,
                    groups=df[groups_col] if groups_col else None,
                )
            except Exception as exc:
                summaries.append(
                    {
                        "level": level,
                        "target": target,
                        "model": model_name,
                        "feature_set": feature_set,
                        "n": len(target_data),
                        "positive_n": positive_n,
                        "error": repr(exc),
                    }
                )
                continue
            groups = used[groups_col].to_numpy() if groups_col else None
            summaries.append(
                summarize_predictions(
                    level=level,
                    target=target,
                    model_name=model_name,
                    feature_set=feature_set,
                    y_true=y,
                    y_score=score,
                    groups=groups,
                    n_bootstrap=n_bootstrap,
                )
            )
            for idx, (_, row) in enumerate(used.iterrows()):
                predictions.append(
                    {
                        "level": level,
                        "target": target,
                        "model": model_name,
                        "feature_set": feature_set,
                        "audit_id": row.get("audit_id", ""),
                        "row_id": row.get("verdict_id", row.get("audit_id", "")),
                        "y_true": int(y[idx]),
                        "y_score": float(score[idx]),
                    }
                )
    return summaries, predictions


def calibration_bins(predictions: list[dict[str, Any]], selected_keys: set[tuple[str, str, str, str]]) -> list[dict[str, Any]]:
    rows = []
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for pred in predictions:
        key = (pred["level"], pred["target"], pred["model"], pred["feature_set"])
        if key in selected_keys:
            grouped.setdefault(key, []).append(pred)
    for key, preds in grouped.items():
        preds = sorted(preds, key=lambda row: row["y_score"])
        n = len(preds)
        if n == 0:
            continue
        for bin_idx in range(5):
            start = math.floor(bin_idx * n / 5)
            end = math.floor((bin_idx + 1) * n / 5)
            chunk = preds[start:end]
            if not chunk:
                continue
            rows.append(
                {
                    "level": key[0],
                    "target": key[1],
                    "model": key[2],
                    "feature_set": key[3],
                    "bin": bin_idx + 1,
                    "n": len(chunk),
                    "score_min": min(row["y_score"] for row in chunk),
                    "score_max": max(row["y_score"] for row in chunk),
                    "mean_predicted_unreliability": sum(row["y_score"] for row in chunk) / len(chunk),
                    "empirical_unreliability": sum(row["y_true"] for row in chunk) / len(chunk),
                }
            )
    return rows


def top_cases(
    item_df: pd.DataFrame,
    verdict_df: pd.DataFrame,
    predictions: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # Pick the best AUPRC result for each target, then emit its top predictions.
    best_by_target: dict[tuple[str, str], dict[str, Any]] = {}
    for row in summaries:
        if row.get("model") == "direct_score" or row.get("error"):
            pass
        auprc = row.get("auprc", "")
        if auprc == "":
            continue
        key = (row["level"], row["target"])
        current = best_by_target.get(key)
        if current is None or float(auprc) > float(current.get("auprc", -1)):
            best_by_target[key] = row

    item_lookup = {row["audit_id"]: row for _, row in item_df.iterrows()}
    verdict_lookup = {row["verdict_id"]: row for _, row in verdict_df.iterrows()}
    out = []
    for key, best in best_by_target.items():
        matching = [
            pred
            for pred in predictions
            if pred["level"] == key[0]
            and pred["target"] == key[1]
            and pred["model"] == best["model"]
            and pred["feature_set"] == best["feature_set"]
        ]
        matching = sorted(matching, key=lambda row: row["y_score"], reverse=True)[:30]
        for rank, pred in enumerate(matching, start=1):
            item = item_lookup.get(pred["audit_id"], {})
            verdict = verdict_lookup.get(pred["row_id"], {})
            out.append(
                {
                    "level": key[0],
                    "target": key[1],
                    "rank": rank,
                    "model": best["model"],
                    "feature_set": best["feature_set"],
                    "audit_id": pred["audit_id"],
                    "row_id": pred["row_id"],
                    "score": pred["y_score"],
                    "y_true": pred["y_true"],
                    "dataset": item.get("dataset", ""),
                    "primary_stratum": item.get("primary_stratum", ""),
                    "human_label": item.get("human_label", ""),
                    "human_notes": item.get("human_notes", ""),
                    "condition": verdict.get("condition", ""),
                    "protocol": verdict.get("protocol", ""),
                    "verdict_label": verdict.get("verdict_label", ""),
                }
            )
    return out


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features-dir", type=Path, default=Path("data/audit/reliability"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/audit/reliability"))
    parser.add_argument("--bootstrap", type=int, default=300)
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    item_df = pd.read_csv(args.features_dir / "item_level_features.csv")
    verdict_df = pd.read_csv(args.features_dir / "verdict_level_features.csv")

    all_summaries: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []

    for level, df, targets, groups_col in [
        ("item", item_df, ITEM_TARGETS, None),
        ("verdict", verdict_df, VERDICT_TARGETS, "audit_id"),
    ]:
        direct_summaries, direct_predictions = evaluate_direct_scores(
            df,
            targets,
            level=level,
            groups_col=groups_col,
            n_bootstrap=args.bootstrap,
        )
        model_summaries, model_predictions = evaluate_models(
            df,
            targets,
            level=level,
            groups_col=groups_col,
            n_bootstrap=args.bootstrap,
        )
        all_summaries.extend(direct_summaries)
        all_summaries.extend(model_summaries)
        all_predictions.extend(direct_predictions)
        all_predictions.extend(model_predictions)

    write_csv(args.out_dir / "prediction_results.csv", all_summaries)
    write_csv(args.out_dir / "prediction_oof_scores.csv", all_predictions)

    selected = {
        ("item", "target_benchmark_mismatch", "logistic_l2", "all_canonical"),
        ("item", "target_any_main_llm_wrong", "logistic_l2", "all_canonical"),
        ("item", "target_human_unfaithful", "logistic_l2", "all_canonical"),
        ("verdict", "target_verdict_unreliable_strict", "logistic_l2", "all_canonical"),
        ("verdict", "target_verdict_unreliable_covered", "logistic_l2", "all_canonical"),
    }
    write_csv(args.out_dir / "calibration_bins.csv", calibration_bins(all_predictions, selected))
    write_csv(args.out_dir / "top_audit_cases.csv", top_cases(item_df, verdict_df, all_predictions, all_summaries))

    # Compact JSON summary for freezes.
    summary = {
        "n_item_rows": int(len(item_df)),
        "n_verdict_rows": int(len(verdict_df)),
        "n_result_rows": len(all_summaries),
        "n_prediction_rows": len(all_predictions),
        "targets": {
            target: int(pd.to_numeric(item_df[target], errors="coerce").fillna(0).sum())
            for target in ITEM_TARGETS
            if target in item_df
        }
        | {
            target: int(pd.to_numeric(verdict_df[target], errors="coerce").fillna(0).sum())
            for target in VERDICT_TARGETS
            if target in verdict_df
        },
    }
    with (args.out_dir / "prediction_experiment_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
