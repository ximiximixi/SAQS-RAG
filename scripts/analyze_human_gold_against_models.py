import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


BINARY_LABELS = {"faithful", "unfaithful"}
ABSTAIN_LABELS = {"insufficient", "tie", "missing", ""}


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_csv(path, rows, fieldnames=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def norm_label(value):
    if value is None:
        return "missing"
    value = str(value).strip().lower()
    if not value:
        return "missing"
    if value in {"support", "supported", "correct", "true"}:
        return "faithful"
    if value in {"unsupported", "incorrect", "false"}:
        return "unfaithful"
    return value


def parse_categories(value):
    if value is None:
        return set()
    if isinstance(value, list):
        return {str(x).strip() for x in value if str(x).strip()}
    value = str(value).strip()
    if not value:
        return set()
    if value.startswith("["):
        try:
            return {str(x).strip() for x in json.loads(value) if str(x).strip()}
        except Exception:
            pass
    return {x.strip() for x in value.replace(";", "|").replace(",", "|").split("|") if x.strip()}


def audit_sort_key(audit_id):
    try:
        return int(str(audit_id).split("-")[-1])
    except Exception:
        return str(audit_id)


def wilson_interval(k, n, z=1.96):
    if n <= 0:
        return (None, None)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n) / denom
    return (center - margin, center + margin)


def safe_div(a, b):
    return a / b if b else None


def f1(precision, recall):
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def majority_vote(labels):
    labels = [norm_label(x) for x in labels if norm_label(x) != "missing"]
    if not labels:
        return "missing"
    counts = Counter(labels)
    max_count = max(counts.values())
    winners = sorted([label for label, count in counts.items() if count == max_count])
    if len(winners) != 1:
        return "tie"
    return winners[0]


def condition_from_file(path, label_field="label", condition=None, group=None, kind="individual"):
    rows = read_csv(path)
    out = {}
    for row in rows:
        audit_id = row["audit_id"]
        out[audit_id] = {
            "label": norm_label(row.get(label_field)),
            "issue_categories": parse_categories(row.get("issue_categories")),
            "confidence": float(row["confidence"]) if row.get("confidence") not in (None, "") else None,
            "source": Path(path).name,
        }
    return {
        "condition": condition or Path(path).stem,
        "group": group or Path(path).stem,
        "kind": kind,
        "predictions": out,
    }


def majority_condition(name, group, conditions):
    audit_ids = sorted(
        {audit_id for condition in conditions for audit_id in condition["predictions"]},
        key=audit_sort_key,
    )
    preds = {}
    for audit_id in audit_ids:
        labels = [condition["predictions"].get(audit_id, {}).get("label", "missing") for condition in conditions]
        maj = majority_vote(labels)
        categories = set()
        confs = []
        if maj not in {"tie", "missing"}:
            selected = [
                condition
                for condition in conditions
                if condition["predictions"].get(audit_id, {}).get("label") == maj
            ]
        else:
            selected = conditions
        for condition in selected:
            pred = condition["predictions"].get(audit_id, {})
            categories.update(pred.get("issue_categories", set()))
            if pred.get("confidence") is not None:
                confs.append(pred["confidence"])
        preds[audit_id] = {
            "label": maj,
            "issue_categories": categories,
            "confidence": sum(confs) / len(confs) if confs else None,
            "votes": "|".join(labels),
            "vote_counts": json.dumps(Counter(labels), ensure_ascii=False, sort_keys=True),
        }
    return {"condition": name, "group": group, "kind": "majority", "predictions": preds}


def make_metadata_conditions(metadata_rows):
    metadata = {row["audit_id"]: row for row in metadata_rows}
    conditions = []
    benchmark = {}
    qwen = {}
    glm = {}
    combined = {}
    for audit_id, row in metadata.items():
        benchmark[audit_id] = {
            "label": norm_label(row.get("gold_label")),
            "issue_categories": set(),
            "confidence": None,
        }
        qwen[audit_id] = {
            "label": norm_label(row.get("qwen_majority")),
            "issue_categories": set(),
            "confidence": None,
        }
        glm[audit_id] = {
            "label": norm_label(row.get("glm_majority")),
            "issue_categories": set(),
            "confidence": None,
        }
        combined[audit_id] = {
            "label": norm_label(row.get("combined_majority")),
            "issue_categories": set(),
            "confidence": None,
        }
    conditions.append(
        {"condition": "benchmark_original_gold", "group": "dataset_reference", "kind": "reference", "predictions": benchmark}
    )
    conditions.append(
        {"condition": "pilot_qwen_majority", "group": "pilot_original_judges", "kind": "majority", "predictions": qwen}
    )
    conditions.append(
        {"condition": "pilot_glm_majority", "group": "pilot_original_judges", "kind": "majority", "predictions": glm}
    )
    conditions.append(
        {
            "condition": "pilot_qwen_glm_combined_majority",
            "group": "pilot_original_judges",
            "kind": "majority",
            "predictions": combined,
        }
    )
    return conditions, metadata


def summarize_condition(condition, human):
    preds = condition["predictions"]
    audit_ids = sorted(human, key=audit_sort_key)
    n = len(audit_ids)
    distribution = Counter(preds.get(audit_id, {}).get("label", "missing") for audit_id in audit_ids)
    exact_correct = 0
    covered_correct = 0
    covered = 0
    pred_abstain = 0
    confusion = Counter()
    confidences_correct = []
    confidences_wrong = []
    for audit_id in audit_ids:
        h = human[audit_id]["label"]
        p = preds.get(audit_id, {}).get("label", "missing")
        conf = preds.get(audit_id, {}).get("confidence")
        if p == h:
            exact_correct += 1
            if conf is not None:
                confidences_correct.append(conf)
        else:
            if conf is not None:
                confidences_wrong.append(conf)
        if p in BINARY_LABELS:
            covered += 1
            if p == h:
                covered_correct += 1
            confusion[(h, p)] += 1
        else:
            pred_abstain += 1
            confusion[(h, p)] += 1

    tp_u = confusion[("unfaithful", "unfaithful")]
    fp_u = confusion[("faithful", "unfaithful")]
    fn_u = confusion[("unfaithful", "faithful")]
    tn_u = confusion[("faithful", "faithful")]
    precision_u = safe_div(tp_u, tp_u + fp_u)
    recall_u = safe_div(tp_u, tp_u + fn_u)
    f1_u = f1(precision_u, recall_u)
    precision_f = safe_div(tn_u, tn_u + fn_u)
    recall_f = safe_div(tn_u, tn_u + fp_u)
    f1_f = f1(precision_f, recall_f)
    macro = None
    if f1_u is not None and f1_f is not None:
        macro = (f1_u + f1_f) / 2
    bal_acc = None
    if recall_u is not None and recall_f is not None:
        bal_acc = (recall_u + recall_f) / 2

    # Binary Cohen's kappa and MCC on covered predictions.
    kappa = None
    mcc = None
    if covered:
        po = covered_correct / covered
        h_counts = Counter()
        p_counts = Counter()
        for (h, p), count in confusion.items():
            if p in BINARY_LABELS:
                h_counts[h] += count
                p_counts[p] += count
        pe = sum((h_counts[label] / covered) * (p_counts[label] / covered) for label in BINARY_LABELS)
        if pe != 1:
            kappa = (po - pe) / (1 - pe)
        denom = math.sqrt((tp_u + fp_u) * (tp_u + fn_u) * (tn_u + fp_u) * (tn_u + fn_u))
        if denom:
            mcc = (tp_u * tn_u - fp_u * fn_u) / denom

    exact_ci = wilson_interval(exact_correct, n)
    covered_ci = wilson_interval(covered_correct, covered)
    return {
        "condition": condition["condition"],
        "group": condition["group"],
        "kind": condition["kind"],
        "n": n,
        "prediction_distribution": dict(distribution),
        "exact_accuracy_all": exact_correct / n if n else None,
        "exact_accuracy_all_ci95_low": exact_ci[0],
        "exact_accuracy_all_ci95_high": exact_ci[1],
        "exact_correct_all": exact_correct,
        "error_or_abstain_all": n - exact_correct,
        "coverage_binary": covered / n if n else None,
        "covered_binary_n": covered,
        "covered_binary_accuracy": covered_correct / covered if covered else None,
        "covered_binary_accuracy_ci95_low": covered_ci[0],
        "covered_binary_accuracy_ci95_high": covered_ci[1],
        "abstain_or_tie_n": pred_abstain,
        "human_faithful_pred_faithful": tn_u,
        "human_faithful_pred_unfaithful": fp_u,
        "human_unfaithful_pred_faithful": fn_u,
        "human_unfaithful_pred_unfaithful": tp_u,
        "unfaithful_precision": precision_u,
        "unfaithful_recall": recall_u,
        "unfaithful_f1": f1_u,
        "faithful_precision": precision_f,
        "faithful_recall": recall_f,
        "faithful_f1": f1_f,
        "macro_f1_binary": macro,
        "balanced_accuracy_binary": bal_acc,
        "cohen_kappa_binary": kappa,
        "mcc_binary": mcc,
        "avg_confidence_correct": sum(confidences_correct) / len(confidences_correct)
        if confidences_correct
        else None,
        "avg_confidence_wrong": sum(confidences_wrong) / len(confidences_wrong) if confidences_wrong else None,
    }


def issue_overlap_summary(condition, human):
    rows = []
    jaccards = []
    jaccards_nonempty = []
    any_overlap = 0
    exact = 0
    recall_values = []
    precision_values = []
    for audit_id, hrow in human.items():
        hcats = hrow["issue_categories"]
        pcats = condition["predictions"].get(audit_id, {}).get("issue_categories", set())
        union = hcats | pcats
        inter = hcats & pcats
        jaccard = len(inter) / len(union) if union else 1.0
        jaccards.append(jaccard)
        if hcats:
            jaccards_nonempty.append(jaccard)
            recall_values.append(len(inter) / len(hcats))
        if pcats:
            precision_values.append(len(inter) / len(pcats))
        if inter:
            any_overlap += 1
        if hcats == pcats:
            exact += 1
    rows.append(
        {
            "condition": condition["condition"],
            "group": condition["group"],
            "kind": condition["kind"],
            "mean_issue_jaccard_all": sum(jaccards) / len(jaccards) if jaccards else None,
            "mean_issue_jaccard_human_nonempty": sum(jaccards_nonempty) / len(jaccards_nonempty)
            if jaccards_nonempty
            else None,
            "issue_any_overlap_rate": any_overlap / len(human) if human else None,
            "issue_exact_match_rate": exact / len(human) if human else None,
            "mean_human_issue_recall": sum(recall_values) / len(recall_values) if recall_values else None,
            "mean_model_issue_precision": sum(precision_values) / len(precision_values) if precision_values else None,
        }
    )
    return rows[0]


def consensus_summary(group_name, conditions, majority, human):
    audit_ids = sorted(human, key=audit_sort_key)
    n = len(audit_ids)
    unanimous = 0
    unanimous_correct = 0
    unanimous_wrong = 0
    no_model_correct = 0
    all_models_correct = 0
    majority_correct = 0
    vote_margins = []
    correct_vote_counts = []
    rows = []
    for audit_id in audit_ids:
        h = human[audit_id]["label"]
        labels = [condition["predictions"].get(audit_id, {}).get("label", "missing") for condition in conditions]
        counts = Counter(labels)
        top = counts.most_common()
        margin = top[0][1] - top[1][1] if len(top) > 1 else top[0][1]
        vote_margins.append(margin)
        correct_votes = sum(1 for label in labels if label == h)
        correct_vote_counts.append(correct_votes)
        maj_label = majority["predictions"].get(audit_id, {}).get("label", "missing")
        if maj_label == h:
            majority_correct += 1
        if len(set(labels)) == 1:
            unanimous += 1
            if labels[0] == h:
                unanimous_correct += 1
            else:
                unanimous_wrong += 1
        if correct_votes == 0:
            no_model_correct += 1
        if correct_votes == len(conditions):
            all_models_correct += 1
        rows.append(
            {
                "audit_id": audit_id,
                "group": group_name,
                "human_label": h,
                "majority_label": maj_label,
                "majority_correct": maj_label == h,
                "labels": "|".join(labels),
                "correct_vote_count": correct_votes,
                "vote_margin": margin,
                "unanimous": len(set(labels)) == 1,
            }
        )
    return (
        {
            "group": group_name,
            "n_items": n,
            "n_models": len(conditions),
            "majority_accuracy": majority_correct / n if n else None,
            "unanimous_n": unanimous,
            "unanimous_rate": unanimous / n if n else None,
            "unanimous_accuracy": unanimous_correct / unanimous if unanimous else None,
            "unanimous_wrong_n": unanimous_wrong,
            "all_models_correct_n": all_models_correct,
            "no_model_correct_n": no_model_correct,
            "avg_vote_margin": sum(vote_margins) / len(vote_margins) if vote_margins else None,
            "avg_correct_vote_count": sum(correct_vote_counts) / len(correct_vote_counts)
            if correct_vote_counts
            else None,
        },
        rows,
    )


def pairwise_transition(name_a, cond_a, name_b, cond_b, human):
    rows = []
    counts = Counter()
    for audit_id in sorted(human, key=audit_sort_key):
        h = human[audit_id]["label"]
        a = cond_a["predictions"].get(audit_id, {}).get("label", "missing")
        b = cond_b["predictions"].get(audit_id, {}).get("label", "missing")
        if a == b:
            relation = "unchanged"
        elif a != h and b == h:
            relation = "changed_toward_human"
        elif a == h and b != h:
            relation = "changed_away_from_human"
        else:
            relation = "changed_other"
        counts[relation] += 1
        rows.append(
            {
                "audit_id": audit_id,
                "pair": f"{name_a} -> {name_b}",
                "human_label": h,
                "from_label": a,
                "to_label": b,
                "relation_to_human": relation,
            }
        )
    return counts, rows


def exact_mcnemar_pvalue(a_only_correct, b_only_correct):
    n = a_only_correct + b_only_correct
    if n == 0:
        return 1.0
    k = min(a_only_correct, b_only_correct)
    p = 2 * sum(math.comb(n, i) * (0.5**n) for i in range(k + 1))
    return min(1.0, p)


def pairwise_correctness_summary(condition_a, condition_b, human):
    both_correct = 0
    a_only_correct = 0
    b_only_correct = 0
    both_wrong = 0
    for audit_id, hrow in human.items():
        h = hrow["label"]
        a_correct = condition_a["predictions"].get(audit_id, {}).get("label", "missing") == h
        b_correct = condition_b["predictions"].get(audit_id, {}).get("label", "missing") == h
        if a_correct and b_correct:
            both_correct += 1
        elif a_correct and not b_correct:
            a_only_correct += 1
        elif not a_correct and b_correct:
            b_only_correct += 1
        else:
            both_wrong += 1
    return {
        "condition_a": condition_a["condition"],
        "condition_b": condition_b["condition"],
        "both_correct": both_correct,
        "a_only_correct": a_only_correct,
        "b_only_correct": b_only_correct,
        "both_wrong_or_abstain": both_wrong,
        "exact_mcnemar_p_two_sided": exact_mcnemar_pvalue(a_only_correct, b_only_correct),
    }


def condition_language_shift_summary(condition_zh, condition_en, human):
    ids = sorted(
        set(condition_zh["predictions"]) & set(condition_en["predictions"]) & set(human),
        key=audit_sort_key,
    )
    zh_dist = Counter()
    en_dist = Counter()
    changed = 0
    changed_toward_human = 0
    changed_away_from_human = 0
    changed_other = 0
    for audit_id in ids:
        human_label = human[audit_id]["label"]
        zh_label = condition_zh["predictions"].get(audit_id, {}).get("label", "missing")
        en_label = condition_en["predictions"].get(audit_id, {}).get("label", "missing")
        zh_dist[zh_label] += 1
        en_dist[en_label] += 1
        if zh_label == en_label:
            continue
        changed += 1
        if zh_label != human_label and en_label == human_label:
            changed_toward_human += 1
        elif zh_label == human_label and en_label != human_label:
            changed_away_from_human += 1
        else:
            changed_other += 1
    zh_accuracy = sum(
        condition_zh["predictions"].get(audit_id, {}).get("label", "missing") == human[audit_id]["label"]
        for audit_id in ids
    ) / len(ids)
    en_accuracy = sum(
        condition_en["predictions"].get(audit_id, {}).get("label", "missing") == human[audit_id]["label"]
        for audit_id in ids
    ) / len(ids)
    return {
        "condition_zh": condition_zh["condition"],
        "condition_en": condition_en["condition"],
        "n": len(ids),
        "zh_distribution": dict(zh_dist),
        "en_distribution": dict(en_dist),
        "zh_accuracy": zh_accuracy,
        "en_accuracy": en_accuracy,
        "changed_n": changed,
        "changed_rate": changed / len(ids) if ids else None,
        "changed_toward_human": changed_toward_human,
        "changed_away_from_human": changed_away_from_human,
        "changed_other": changed_other,
    }


def rank_auc(scores, labels):
    pairs = sorted(zip(scores, labels), key=lambda x: x[0])
    n_pos = sum(1 for label in labels if label)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    rank_sum = 0.0
    rank = 1
    i = 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (rank + rank + (j - i) - 1) / 2
        for k in range(i, j):
            if pairs[k][1]:
                rank_sum += avg_rank
        rank += j - i
        i = j
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def top_fraction_precision_lift(scores, labels, fraction=0.2):
    n = len(labels)
    if n == 0:
        return (None, None, None)
    k = max(1, round(n * fraction))
    selected = sorted(range(n), key=lambda i: scores[i], reverse=True)[:k]
    base_rate = sum(labels) / n
    precision = sum(1 for i in selected if labels[i]) / k
    lift = precision / base_rate if base_rate else None
    return (precision, lift, k)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", default="data/audit")
    parser.add_argument("--out-dir", default="data/audit/human_gold_analysis")
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    human_path = audit_dir / "human_audit_annotations_en.csv"
    if not human_path.exists():
        human_path = audit_dir / "human_audit_annotations.csv"
    human_rows = read_csv(human_path)
    human = {}
    duplicates = []
    for row in human_rows:
        audit_id = row["audit_id"]
        if audit_id in human:
            duplicates.append(audit_id)
        human[audit_id] = {
            "label": norm_label(row["annotator_label"]),
            "confidence": float(row["annotator_confidence"]) if row.get("annotator_confidence") else None,
            "issue_categories": parse_categories(row.get("issue_categories")),
            "notes": row.get("notes", ""),
            "updated_at": row.get("updated_at", ""),
        }

    metadata_rows = read_csv(audit_dir / "human_audit_batch_100_metadata.csv")
    metadata_conditions, metadata = make_metadata_conditions(metadata_rows)

    weak_files = [
        ("qwen3.6-max-preview", "weak_labels_qwen36maxpreview.csv"),
        ("deepseek-v4-pro", "weak_labels_deepseekv4pro.csv"),
        ("kimi-k2.6", "weak_labels_kimik26.csv"),
        ("qwen3-max-2026-01-23", "weak_labels_qwen3max20260123.csv"),
        ("qwen3.6-plus-2026-04-02", "weak_labels_qwen36plus20260402.csv"),
    ]
    strict_files = [
        ("qwen3.6-max-preview", "strict_independent_qwen36maxpreview.csv"),
        ("deepseek-v4-pro", "strict_independent_deepseekv4pro.csv"),
        ("kimi-k2.6", "strict_independent_kimik26.csv"),
        ("qwen3-max-2026-01-23", "strict_independent_qwen3max20260123.csv"),
        ("qwen3.6-plus-2026-04-02", "strict_independent_qwen36plus20260402.csv"),
    ]
    strict_en_files = [
        ("qwen3.6-max-preview", "strict_independent_en_qwen36maxpreview.csv"),
        ("deepseek-v4-pro", "strict_independent_en_deepseekv4pro.csv"),
        ("kimi-k2.6", "strict_independent_en_kimik26.csv"),
        ("qwen3-max-2026-01-23", "strict_independent_en_qwen3max20260123.csv"),
        ("qwen3.6-plus-2026-04-02", "strict_independent_en_qwen36plus20260402.csv"),
    ]
    assisted_v1_files = [
        ("deepseek-v4-pro", "assisted_adjudication_deepseekv4pro.csv"),
        ("qwen3.5-plus-2026-04-20", "assisted_adjudication_qwen35plus20260420.csv"),
        ("qwen3.6-max-preview", "assisted_adjudication_qwen36maxpreview.csv"),
    ]
    assisted_v2_files = [
        ("deepseek-v4-pro", "strict_assisted_v2_deepseekv4pro.csv"),
        ("qwen3.5-plus-2026-04-20", "strict_assisted_v2_qwen35plus20260420.csv"),
        ("qwen3.6-max-preview", "strict_assisted_v2_qwen36maxpreview.csv"),
    ]

    weak_conditions = [
        condition_from_file(audit_dir / filename, condition=f"old_weak_{name}", group="old_weak_5models")
        for name, filename in weak_files
    ]
    strict_conditions = [
        condition_from_file(audit_dir / filename, condition=f"strict_independent_{name}", group="strict_independent_5models")
        for name, filename in strict_files
    ]
    strict_en_conditions = []
    if all((audit_dir / filename).exists() for _, filename in strict_en_files):
        strict_en_conditions = [
            condition_from_file(
                audit_dir / filename,
                condition=f"strict_independent_en_{name}",
                group="strict_independent_en_5models",
            )
            for name, filename in strict_en_files
        ]
    assisted_v1_conditions = [
        condition_from_file(audit_dir / filename, condition=f"assisted_v1_{name}", group="assisted_v1_3models")
        for name, filename in assisted_v1_files
    ]
    assisted_v2_conditions = [
        condition_from_file(audit_dir / filename, condition=f"assisted_v2_{name}", group="assisted_v2_3models")
        for name, filename in assisted_v2_files
    ]

    weak_majority = majority_condition("old_weak_5model_majority", "old_weak_5models", weak_conditions)
    strict_majority = majority_condition("strict_independent_5model_majority", "strict_independent_5models", strict_conditions)
    strict_en_majority = (
        majority_condition(
            "strict_independent_en_5model_majority",
            "strict_independent_en_5models",
            strict_en_conditions,
        )
        if strict_en_conditions
        else None
    )
    assisted_v1_majority = majority_condition("assisted_v1_3model_majority", "assisted_v1_3models", assisted_v1_conditions)
    assisted_v2_majority = majority_condition("assisted_v2_3model_majority", "assisted_v2_3models", assisted_v2_conditions)

    all_conditions = (
        metadata_conditions
        + weak_conditions
        + [weak_majority]
        + strict_conditions
        + [strict_majority]
        + strict_en_conditions
        + ([strict_en_majority] if strict_en_majority is not None else [])
        + assisted_v1_conditions
        + [assisted_v1_majority]
        + assisted_v2_conditions
        + [assisted_v2_majority]
    )

    summaries = [summarize_condition(condition, human) for condition in all_conditions]
    write_csv(
        out_dir / "condition_summary_against_human_gold.csv",
        summaries,
        fieldnames=[
            "condition",
            "group",
            "kind",
            "n",
            "prediction_distribution",
            "exact_accuracy_all",
            "exact_accuracy_all_ci95_low",
            "exact_accuracy_all_ci95_high",
            "exact_correct_all",
            "error_or_abstain_all",
            "coverage_binary",
            "covered_binary_n",
            "covered_binary_accuracy",
            "covered_binary_accuracy_ci95_low",
            "covered_binary_accuracy_ci95_high",
            "abstain_or_tie_n",
            "human_faithful_pred_faithful",
            "human_faithful_pred_unfaithful",
            "human_unfaithful_pred_faithful",
            "human_unfaithful_pred_unfaithful",
            "unfaithful_precision",
            "unfaithful_recall",
            "unfaithful_f1",
            "faithful_precision",
            "faithful_recall",
            "faithful_f1",
            "macro_f1_binary",
            "balanced_accuracy_binary",
            "cohen_kappa_binary",
            "mcc_binary",
            "avg_confidence_correct",
            "avg_confidence_wrong",
        ],
    )

    issue_counts = Counter()
    for row in human.values():
        issue_counts.update(row["issue_categories"])
    issue_rows = [
        {"issue_category": cat, "count": count, "rate": count / len(human)}
        for cat, count in issue_counts.most_common()
    ]
    write_csv(out_dir / "human_issue_category_counts.csv", issue_rows)

    issue_overlap_rows = [issue_overlap_summary(condition, human) for condition in all_conditions]
    write_csv(out_dir / "issue_overlap_against_human_gold.csv", issue_overlap_rows)

    key_conditions = {
        condition["condition"]: condition
        for condition in [
            metadata_conditions[0],
            metadata_conditions[1],
            metadata_conditions[2],
            metadata_conditions[3],
            weak_majority,
            strict_majority,
            *([strict_en_majority] if strict_en_majority is not None else []),
            assisted_v1_majority,
            assisted_v2_majority,
        ]
    }
    per_item_rows = []
    for audit_id in sorted(human, key=audit_sort_key):
        row = {
            "audit_id": audit_id,
            "dataset": metadata.get(audit_id, {}).get("dataset", ""),
            "primary_stratum": metadata.get(audit_id, {}).get("primary_stratum", ""),
            "candidate_strata": metadata.get(audit_id, {}).get("candidate_strata", ""),
            "human_label": human[audit_id]["label"],
            "human_confidence": human[audit_id]["confidence"],
            "human_issue_categories": "|".join(sorted(human[audit_id]["issue_categories"])),
            "human_notes": human[audit_id]["notes"],
        }
        disagreement_count = 0
        for name, condition in key_conditions.items():
            pred = condition["predictions"].get(audit_id, {}).get("label", "missing")
            row[name] = pred
            row[f"{name}_correct"] = pred == human[audit_id]["label"]
            if pred != human[audit_id]["label"]:
                disagreement_count += 1
        row["key_condition_disagreement_count"] = disagreement_count
        per_item_rows.append(row)
    write_csv(out_dir / "per_item_key_condition_comparison.csv", per_item_rows)

    high_value = sorted(
        per_item_rows,
        key=lambda row: (-row["key_condition_disagreement_count"], audit_sort_key(row["audit_id"])),
    )
    write_csv(out_dir / "high_value_disagreement_cases.csv", high_value[:40])

    # Dataset and sampling-stratum breakdowns for key majority/reference conditions.
    breakdown_rows = []
    for field in ["dataset", "primary_stratum"]:
        values = sorted({metadata.get(aid, {}).get(field, "") for aid in human})
        for value in values:
            ids = [aid for aid in human if metadata.get(aid, {}).get(field, "") == value]
            if not ids:
                continue
            human_dist = Counter(human[aid]["label"] for aid in ids)
            base = {
                "breakdown_field": field,
                "breakdown_value": value,
                "n": len(ids),
                "human_faithful": human_dist.get("faithful", 0),
                "human_unfaithful": human_dist.get("unfaithful", 0),
                "human_unfaithful_rate": human_dist.get("unfaithful", 0) / len(ids),
            }
            for name, condition in key_conditions.items():
                correct = sum(
                    condition["predictions"].get(aid, {}).get("label", "missing") == human[aid]["label"]
                    for aid in ids
                )
                base[f"{name}_accuracy"] = correct / len(ids)
            breakdown_rows.append(base)
    write_csv(out_dir / "dataset_and_stratum_breakdown.csv", breakdown_rows)

    consensus_rows = []
    consensus_item_rows = []
    for name, conditions, majority in [
        ("old_weak_5models", weak_conditions, weak_majority),
        ("strict_independent_5models", strict_conditions, strict_majority),
        *(
            [("strict_independent_en_5models", strict_en_conditions, strict_en_majority)]
            if strict_en_majority is not None
            else []
        ),
        ("assisted_v1_3models", assisted_v1_conditions, assisted_v1_majority),
        ("assisted_v2_3models", assisted_v2_conditions, assisted_v2_majority),
    ]:
        summary, rows = consensus_summary(name, conditions, majority, human)
        consensus_rows.append(summary)
        consensus_item_rows.extend(rows)
    write_csv(out_dir / "model_group_consensus_against_human_gold.csv", consensus_rows)
    write_csv(out_dir / "per_item_model_group_consensus.csv", consensus_item_rows)

    transition_pairs = [
        ("benchmark_original_gold", key_conditions["benchmark_original_gold"], "old_weak_5model_majority", weak_majority),
        ("old_weak_5model_majority", weak_majority, "strict_independent_5model_majority", strict_majority),
        *(
            [
                (
                    "old_weak_5model_majority",
                    weak_majority,
                    "strict_independent_en_5model_majority",
                    strict_en_majority,
                ),
                (
                    "strict_independent_5model_majority",
                    strict_majority,
                    "strict_independent_en_5model_majority",
                    strict_en_majority,
                ),
            ]
            if strict_en_majority is not None
            else []
        ),
        ("strict_independent_5model_majority", strict_majority, "assisted_v2_3model_majority", assisted_v2_majority),
        ("assisted_v1_3model_majority", assisted_v1_majority, "assisted_v2_3model_majority", assisted_v2_majority),
    ]
    transition_summary = []
    transition_detail = []
    for name_a, cond_a, name_b, cond_b in transition_pairs:
        counts, rows = pairwise_transition(name_a, cond_a, name_b, cond_b, human)
        total_changed = sum(count for key, count in counts.items() if key != "unchanged")
        transition_summary.append(
            {
                "pair": f"{name_a} -> {name_b}",
                "unchanged": counts["unchanged"],
                "changed_total": total_changed,
                "changed_toward_human": counts["changed_toward_human"],
                "changed_away_from_human": counts["changed_away_from_human"],
                "changed_other": counts["changed_other"],
            }
        )
        transition_detail.extend(rows)
    write_csv(out_dir / "condition_transition_summary_against_human.csv", transition_summary)
    write_csv(out_dir / "condition_transition_detail_against_human.csv", transition_detail)

    language_shift_rows = []
    if strict_en_majority is not None:
        for zh_condition, en_condition in zip(strict_conditions, strict_en_conditions):
            language_shift_rows.append(condition_language_shift_summary(zh_condition, en_condition, human))
        language_shift_rows.append(condition_language_shift_summary(strict_majority, strict_en_majority, human))
    write_csv(out_dir / "strict_language_control_shift_summary.csv", language_shift_rows)

    pairwise_stats = []
    for cond_a, cond_b in [
        (key_conditions["benchmark_original_gold"], weak_majority),
        (metadata_conditions[1], weak_majority),
        (metadata_conditions[2], weak_majority),
        (weak_majority, strict_majority),
        *(
            [
                (weak_majority, strict_en_majority),
                (strict_majority, strict_en_majority),
            ]
            if strict_en_majority is not None
            else []
        ),
        (strict_majority, assisted_v1_majority),
        (strict_majority, assisted_v2_majority),
        (assisted_v1_majority, assisted_v2_majority),
    ]:
        pairwise_stats.append(pairwise_correctness_summary(cond_a, cond_b, human))
    write_csv(out_dir / "paired_correctness_tests_against_human.csv", pairwise_stats)

    risk_score_names = [
        "risk_multi_combined",
        "risk_qwen_combined",
        "risk_glm_combined",
        "per_task_binary_disagreement_rate",
        "model_majority_disagreement",
    ]
    risk_targets = {
        "human_unfaithful": {
            audit_id: human[audit_id]["label"] == "unfaithful" for audit_id in human
        },
        "benchmark_mismatch_vs_human": {
            audit_id: key_conditions["benchmark_original_gold"]["predictions"].get(audit_id, {}).get("label")
            != human[audit_id]["label"]
            for audit_id in human
        },
        "pilot_qwen_wrong_vs_human": {
            audit_id: key_conditions["pilot_qwen_majority"]["predictions"].get(audit_id, {}).get("label")
            != human[audit_id]["label"]
            for audit_id in human
        },
        "pilot_glm_wrong_vs_human": {
            audit_id: key_conditions["pilot_glm_majority"]["predictions"].get(audit_id, {}).get("label")
            != human[audit_id]["label"]
            for audit_id in human
        },
        "old_weak_majority_wrong_or_abstain_vs_human": {
            audit_id: weak_majority["predictions"].get(audit_id, {}).get("label") != human[audit_id]["label"]
            for audit_id in human
        },
        "strict_independent_majority_wrong_vs_human": {
            audit_id: strict_majority["predictions"].get(audit_id, {}).get("label")
            != human[audit_id]["label"]
            for audit_id in human
        },
        **(
            {
                "strict_independent_en_majority_wrong_vs_human": {
                    audit_id: strict_en_majority["predictions"].get(audit_id, {}).get("label")
                    != human[audit_id]["label"]
                    for audit_id in human
                }
            }
            if strict_en_majority is not None
            else {}
        ),
        "assisted_v1_majority_wrong_vs_human": {
            audit_id: assisted_v1_majority["predictions"].get(audit_id, {}).get("label")
            != human[audit_id]["label"]
            for audit_id in human
        },
        "assisted_v2_majority_wrong_vs_human": {
            audit_id: assisted_v2_majority["predictions"].get(audit_id, {}).get("label")
            != human[audit_id]["label"]
            for audit_id in human
        },
    }
    risk_rows = []
    audit_ids = sorted(human, key=audit_sort_key)
    for target_name, target_map in risk_targets.items():
        labels = [bool(target_map[audit_id]) for audit_id in audit_ids]
        for score_name in risk_score_names:
            scores = []
            for audit_id in audit_ids:
                raw = metadata[audit_id].get(score_name, "")
                if score_name == "model_majority_disagreement":
                    score = 1.0 if str(raw).lower() == "true" else 0.0
                else:
                    score = float(raw) if raw != "" else 0.0
                scores.append(score)
            top_precision, top_lift, top_k = top_fraction_precision_lift(scores, labels, 0.2)
            risk_rows.append(
                {
                    "target": target_name,
                    "score": score_name,
                    "n": len(labels),
                    "positive_n": sum(labels),
                    "base_rate": sum(labels) / len(labels) if labels else None,
                    "auroc": rank_auc(scores, labels),
                    "top20_k": top_k,
                    "top20_precision": top_precision,
                    "top20_lift": top_lift,
                }
            )
    write_csv(out_dir / "risk_score_analysis_against_human.csv", risk_rows)

    validation = {
        "human_rows": len(human_rows),
        "unique_human_audit_ids": len(human),
        "duplicate_human_audit_ids": duplicates,
        "missing_from_metadata": sorted(set(human) - set(metadata), key=audit_sort_key),
        "metadata_missing_human": sorted(set(metadata) - set(human), key=audit_sort_key),
        "human_label_distribution": dict(Counter(row["label"] for row in human.values())),
        "human_confidence_avg": sum(row["confidence"] for row in human.values() if row["confidence"] is not None)
        / sum(1 for row in human.values() if row["confidence"] is not None),
        "human_issue_category_counts": dict(issue_counts),
        "human_annotation_file": str(human_path),
        "faithful_rows_with_issue_categories": [
            {
                "audit_id": audit_id,
                "issue_categories": sorted(row["issue_categories"]),
                "notes": row["notes"],
            }
            for audit_id, row in sorted(human.items(), key=lambda x: audit_sort_key(x[0]))
            if row["label"] == "faithful" and row["issue_categories"]
        ],
    }

    summary_obj = {
        "validation": validation,
        "condition_summary": summaries,
        "issue_category_counts": issue_rows,
        "consensus_summary": consensus_rows,
        "transition_summary": transition_summary,
        "paired_correctness_tests": pairwise_stats,
        "risk_score_analysis": risk_rows,
        "strict_language_control_shift_summary": language_shift_rows,
        "key_files": {
            "condition_summary": str(out_dir / "condition_summary_against_human_gold.csv"),
            "per_item_key_condition_comparison": str(out_dir / "per_item_key_condition_comparison.csv"),
            "high_value_disagreement_cases": str(out_dir / "high_value_disagreement_cases.csv"),
            "dataset_and_stratum_breakdown": str(out_dir / "dataset_and_stratum_breakdown.csv"),
            "model_group_consensus": str(out_dir / "model_group_consensus_against_human_gold.csv"),
            "condition_transition_summary": str(out_dir / "condition_transition_summary_against_human.csv"),
            "paired_correctness_tests": str(out_dir / "paired_correctness_tests_against_human.csv"),
            "risk_score_analysis": str(out_dir / "risk_score_analysis_against_human.csv"),
            "strict_language_control_shift_summary": str(out_dir / "strict_language_control_shift_summary.csv"),
        },
    }
    write_json(out_dir / "summary.json", summary_obj)

    print(json.dumps(validation, ensure_ascii=False, indent=2))
    print(f"Wrote analysis outputs to {out_dir}")


if __name__ == "__main__":
    main()
