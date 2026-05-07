#!/usr/bin/env python3
"""Simulate audit-efficient calibration of majority-vote judge accuracy."""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Cannot parse bool: {value}")


def parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def read_features(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["majority_correct"] = parse_bool(row["majority_correct"])
        row["majority_wrong"] = parse_bool(row["majority_wrong"])
        row["risk_combined"] = parse_float(row["risk_combined"])
    risks = [row["risk_combined"] for row in rows]
    min_risk = min(risks)
    max_risk = max(risks)
    spread = max(max_risk - min_risk, 1e-12)
    for row in rows:
        normalized_risk = (row["risk_combined"] - min_risk) / spread
        row["predicted_correct_from_risk"] = max(0.0, min(1.0, 1.0 - normalized_risk))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def sample_variance(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.25
    return statistics.variance(values)


def ci_from_estimate(estimate: float, se: float) -> tuple[float, float, float]:
    half_width = 1.96 * se
    return max(0.0, estimate - half_width), min(1.0, estimate + half_width), half_width


def simple_random_estimator(rows: list[dict[str, Any]], sample: list[dict[str, Any]]) -> dict[str, float]:
    n_total = len(rows)
    n = len(sample)
    values = [1.0 if row["majority_correct"] else 0.0 for row in sample]
    estimate = mean(values)
    variance = sample_variance(values)
    fpc = max(0.0, 1.0 - n / n_total)
    se = math.sqrt(fpc * variance / n) if n else 0.0
    low, high, half_width = ci_from_estimate(estimate, se)
    return {
        "estimate": estimate,
        "ci_low": low,
        "ci_high": high,
        "ci_half_width": half_width,
    }


def ppi_random_estimator(rows: list[dict[str, Any]], sample: list[dict[str, Any]]) -> dict[str, float]:
    n_total = len(rows)
    n = len(sample)
    pred_population_mean = mean([float(row["predicted_correct_from_risk"]) for row in rows])
    residuals = [
        (1.0 if row["majority_correct"] else 0.0) - float(row["predicted_correct_from_risk"])
        for row in sample
    ]
    estimate = pred_population_mean + mean(residuals)
    variance = sample_variance(residuals)
    fpc = max(0.0, 1.0 - n / n_total)
    se = math.sqrt(fpc * variance / n) if n else 0.0
    low, high, half_width = ci_from_estimate(estimate, se)
    return {
        "estimate": max(0.0, min(1.0, estimate)),
        "ci_low": low,
        "ci_high": high,
        "ci_half_width": half_width,
    }


def build_risk_strata(rows: list[dict[str, Any]], n_strata: int = 3) -> dict[str, list[dict[str, Any]]]:
    ranked = sorted(rows, key=lambda row: row["risk_combined"])
    strata: dict[str, list[dict[str, Any]]] = {}
    names = ["low", "medium", "high"]
    for idx, name in enumerate(names[:n_strata]):
        start = round(idx * len(ranked) / n_strata)
        end = round((idx + 1) * len(ranked) / n_strata)
        strata[name] = ranked[start:end]
    return strata


def allocate_budget(
    strata: dict[str, list[dict[str, Any]]],
    budget: int,
    strategy: str,
) -> dict[str, int]:
    names = list(strata)
    if budget < len(names):
        raise ValueError("Budget must be at least the number of strata.")

    if strategy == "stratified_proportional":
        weights = {name: len(items) for name, items in strata.items()}
    elif strategy == "stratified_risk_oversample":
        weights = {"low": 0.2, "medium": 0.3, "high": 0.5}
    elif strategy == "stratified_oracle_neyman":
        weights = {}
        for name, items in strata.items():
            values = [1.0 if row["majority_correct"] else 0.0 for row in items]
            weights[name] = len(items) * math.sqrt(sample_variance(values))
    else:
        raise ValueError(f"Unknown stratified strategy: {strategy}")

    allocation = {name: 1 for name in names}
    remaining = budget - len(names)
    total_weight = sum(max(0.0, weights.get(name, 0.0)) for name in names)
    if total_weight == 0:
        total_weight = len(names)
        weights = {name: 1.0 for name in names}

    raw = {name: remaining * weights[name] / total_weight for name in names}
    for name in names:
        add = min(len(strata[name]) - allocation[name], int(math.floor(raw[name])))
        allocation[name] += max(0, add)

    while sum(allocation.values()) < budget:
        candidates = [
            name
            for name in names
            if allocation[name] < len(strata[name])
        ]
        if not candidates:
            break
        candidates.sort(key=lambda name: raw[name] - math.floor(raw[name]), reverse=True)
        allocation[candidates[0]] += 1

    return allocation


def stratified_estimator(
    rows: list[dict[str, Any]],
    strata: dict[str, list[dict[str, Any]]],
    samples: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    n_total = len(rows)
    estimate = 0.0
    variance = 0.0
    for name, stratum_rows in strata.items():
        n_h_total = len(stratum_rows)
        n_h = len(samples[name])
        weight = n_h_total / n_total
        values = [1.0 if row["majority_correct"] else 0.0 for row in samples[name]]
        mean_h = mean(values)
        var_h = sample_variance(values)
        fpc_h = max(0.0, 1.0 - n_h / n_h_total) if n_h_total else 0.0
        estimate += weight * mean_h
        variance += (weight**2) * fpc_h * var_h / max(1, n_h)
    se = math.sqrt(max(0.0, variance))
    low, high, half_width = ci_from_estimate(estimate, se)
    return {
        "estimate": estimate,
        "ci_low": low,
        "ci_high": high,
        "ci_half_width": half_width,
    }


def ppi_stratified_estimator(
    rows: list[dict[str, Any]],
    strata: dict[str, list[dict[str, Any]]],
    samples: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    n_total = len(rows)
    pred_population_mean = mean([float(row["predicted_correct_from_risk"]) for row in rows])
    residual_mean = 0.0
    variance = 0.0
    for name, stratum_rows in strata.items():
        n_h_total = len(stratum_rows)
        n_h = len(samples[name])
        weight = n_h_total / n_total
        residuals = [
            (1.0 if row["majority_correct"] else 0.0) - float(row["predicted_correct_from_risk"])
            for row in samples[name]
        ]
        residual_mean += weight * mean(residuals)
        var_h = sample_variance(residuals)
        fpc_h = max(0.0, 1.0 - n_h / n_h_total) if n_h_total else 0.0
        variance += (weight**2) * fpc_h * var_h / max(1, n_h)
    estimate = pred_population_mean + residual_mean
    se = math.sqrt(max(0.0, variance))
    low, high, half_width = ci_from_estimate(estimate, se)
    return {
        "estimate": max(0.0, min(1.0, estimate)),
        "ci_low": low,
        "ci_high": high,
        "ci_half_width": half_width,
    }


def simulate(rows: list[dict[str, Any]], budgets: list[int], repeats: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    true_accuracy = mean([1.0 if row["majority_correct"] else 0.0 for row in rows])
    strata = build_risk_strata(rows)
    result_rows: list[dict[str, Any]] = []

    for budget in budgets:
        for repeat in range(repeats):
            random_sample = rng.sample(rows, min(budget, len(rows)))
            estimate = simple_random_estimator(rows, random_sample)
            result_rows.append(
                {
                    "strategy": "simple_random",
                    "budget": budget,
                    "repeat": repeat,
                    "true_accuracy": true_accuracy,
                    **estimate,
                    "abs_error": abs(estimate["estimate"] - true_accuracy),
                    "covered": estimate["ci_low"] <= true_accuracy <= estimate["ci_high"],
                }
            )

            estimate = ppi_random_estimator(rows, random_sample)
            result_rows.append(
                {
                    "strategy": "ppi_random_risk_combined",
                    "budget": budget,
                    "repeat": repeat,
                    "true_accuracy": true_accuracy,
                    **estimate,
                    "abs_error": abs(estimate["estimate"] - true_accuracy),
                    "covered": estimate["ci_low"] <= true_accuracy <= estimate["ci_high"],
                }
            )

            for strategy in [
                "stratified_proportional",
                "stratified_risk_oversample",
                "stratified_oracle_neyman",
            ]:
                allocation = allocate_budget(strata, min(budget, len(rows)), strategy)
                sampled = {
                    name: rng.sample(items, min(allocation[name], len(items)))
                    for name, items in strata.items()
                }
                estimate = stratified_estimator(rows, strata, sampled)
                result_rows.append(
                    {
                        "strategy": strategy,
                        "budget": budget,
                        "repeat": repeat,
                        "true_accuracy": true_accuracy,
                        **estimate,
                        "abs_error": abs(estimate["estimate"] - true_accuracy),
                        "covered": estimate["ci_low"] <= true_accuracy <= estimate["ci_high"],
                    }
                )
                if strategy == "stratified_proportional":
                    estimate = ppi_stratified_estimator(rows, strata, sampled)
                    result_rows.append(
                        {
                            "strategy": "ppi_stratified_proportional",
                            "budget": budget,
                            "repeat": repeat,
                            "true_accuracy": true_accuracy,
                            **estimate,
                            "abs_error": abs(estimate["estimate"] - true_accuracy),
                            "covered": estimate["ci_low"] <= true_accuracy <= estimate["ci_high"],
                        }
                    )
    return result_rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(row["strategy"], int(row["budget"]))].append(row)

    summaries = []
    for (strategy, budget), items in sorted(buckets.items()):
        abs_errors = [float(row["abs_error"]) for row in items]
        widths = [2 * float(row["ci_half_width"]) for row in items]
        estimates = [float(row["estimate"]) for row in items]
        coverage = [bool(row["covered"]) for row in items]
        summaries.append(
            {
                "strategy": strategy,
                "budget": budget,
                "repeats": len(items),
                "true_accuracy": round(float(items[0]["true_accuracy"]), 6),
                "mean_estimate": round(mean(estimates), 6),
                "estimate_std": round(statistics.pstdev(estimates), 6),
                "mean_abs_error": round(mean(abs_errors), 6),
                "median_abs_error": round(statistics.median(abs_errors), 6),
                "mean_ci_width": round(mean(widths), 6),
                "coverage": round(mean([1.0 if value else 0.0 for value in coverage]), 6),
            }
        )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--budgets", default="15,30,45,60,75,100")
    parser.add_argument("--repeats", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260424)
    args = parser.parse_args()

    rows = read_features(args.features)
    budgets = [int(item.strip()) for item in args.budgets.split(",") if item.strip()]
    sim_rows = simulate(rows, budgets, args.repeats, args.seed)
    summary_rows = summarize(sim_rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "audit_calibration_trials.csv", sim_rows)
    write_csv(args.out_dir / "audit_calibration_summary.csv", summary_rows)

    print(f"Wrote audit calibration simulation to {args.out_dir}")
    for row in summary_rows:
        if row["budget"] in {30, 60, 100}:
            print(row)


if __name__ == "__main__":
    main()
