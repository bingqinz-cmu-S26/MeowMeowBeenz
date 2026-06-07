"""Compute metrics for MCQ cat-audio predictions.

Examples:
    python scripts/metrics_report.py --dataset cat_corpus
    python scripts/metrics_report.py --all
    python scripts/metrics_report.py --ablation-table
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from cat_audio_datasets import DATASETS as DATASET_ROWS

DATASETS = {cfg["id"]: {"classes": cfg["classes"], "chance": cfg["chance"], "note": cfg.get("note", "")} for cfg in DATASET_ROWS}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def prf(rows, labels):
    conf = {g: Counter() for g in labels}
    for row in rows:
        gold = row["gold_label"]
        pred = row.get("pred_label") or "none"
        if gold in conf:
            conf[gold][pred] += 1
    per = {}
    for lab in labels:
        tp = conf[lab][lab]
        fp = sum(conf[g][lab] for g in labels if g != lab)
        fn = sum(v for pred, v in conf[lab].items() if pred != lab)
        support = sum(conf[lab].values())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        _, lo, hi = wilson(tp, support)
        per[lab] = {
            "support": support,
            "tp": tp,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "recall_ci": [round(lo, 4), round(hi, 4)],
            "f1": round(f1, 4),
        }
    return conf, per


def accuracy_group(rows, key):
    grouped = defaultdict(lambda: [0, 0])
    for row in rows:
        value = row.get(key) or "unknown"
        grouped[value][1] += 1
        grouped[value][0] += row["gold_label"] == row.get("pred_label")
    return {k: {"correct": v[0], "n": v[1], "acc": round(v[0] / v[1], 4)} for k, v in sorted(grouped.items())}


def trial_rows(rows):
    for row in rows:
        raw = row.get("trials")
        if not raw:
            if row.get("pred_letter"):
                yield row.get("pred_letter"), row.get("pred_label"), row.get("parse_status")
            continue
        try:
            trials = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(trials, list):
            continue
        for trial in trials:
            if not isinstance(trial, dict):
                continue
            yield trial.get("pred_letter") or "none", trial.get("pred_label") or "none", trial.get("parse_status") or "unknown"


def letter_position_bias(rows, labels):
    letter_counts = Counter()
    letter_correct = Counter()
    label_by_letter = defaultdict(Counter)
    total_trials = 0
    for row in rows:
        try:
            trials = json.loads(row.get("trials") or "[]")
        except json.JSONDecodeError:
            trials = []
        if not isinstance(trials, list):
            trials = []
        for trial in trials:
            if not isinstance(trial, dict):
                continue
            letter = trial.get("pred_letter") or "none"
            letter_counts[letter] += 1
            total_trials += 1
            if trial.get("pred_label") == row.get("gold_label"):
                letter_correct[letter] += 1
            option_order = trial.get("option_order") or []
            if letter != "none" and len(letter) == 1:
                idx = ord(letter) - ord("A")
                if 0 <= idx < len(option_order):
                    label_by_letter[letter][option_order[idx]] += 1
    letters = [chr(ord("A") + i) for i in range(len(labels))] + ["none"]
    return {
        letter: {
            "picked": letter_counts.get(letter, 0),
            "share": round(letter_counts.get(letter, 0) / total_trials, 4) if total_trials else 0.0,
            "correct": letter_correct.get(letter, 0),
            "top_labels_when_picked": dict(label_by_letter.get(letter, Counter()).most_common(5)),
        }
        for letter in letters
    }


def compute(dataset_id, pred_path, out_dir, metric_name="metrics_mcq.json"):
    cfg = DATASETS[dataset_id]
    labels = cfg["classes"]
    rows = list(csv.DictReader(open(pred_path, encoding="utf-8")))
    n = len(rows)
    correct = sum(row["gold_label"] == row.get("pred_label") for row in rows)
    acc, lo, hi = wilson(correct, n)
    counts = Counter(row["gold_label"] for row in rows)
    majority = max(counts.values()) / n if n else 0.0
    conf, per = prf(rows, labels)
    macro = sum(v["f1"] for v in per.values()) / len(labels)
    weighted = sum(v["f1"] * v["support"] for v in per.values()) / n if n else 0.0
    parse_counts = Counter(row.get("parse_status") or "unknown" for row in rows)
    parse_fail_count = parse_counts.get("none", 0) + parse_counts.get("error", 0)
    trial_parse_counts = Counter(status for _, _, status in trial_rows(rows))
    agreements = [float(row.get("agreement") or 0.0) for row in rows]
    confidences = [float(row["confidence"]) for row in rows if row.get("confidence")]

    out = {
        "dataset_id": dataset_id,
        "variant": rows[0].get("variant", "") if rows else "",
        "n": n,
        "classes": labels,
        "n_classes": len(labels),
        "chance": round(cfg["chance"], 4),
        "majority_baseline": round(majority, 4),
        "accuracy": round(acc, 4),
        "accuracy_ci": [round(lo, 4), round(hi, 4)],
        "macro_f1": round(macro, 4),
        "weighted_f1": round(weighted, 4),
        "mean_agreement": round(sum(agreements) / len(agreements), 4) if agreements else 0.0,
        "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "parse_status": dict(parse_counts),
        "trial_parse_status": dict(trial_parse_counts),
        "parse_fail_rate": round(parse_fail_count / n, 4) if n else 0.0,
        "per_class": per,
        "hunger": per.get("waiting_for_food", {}),
        "paining": per.get("paining", {}),
        "accuracy_by_source": accuracy_group(rows, "source_hint"),
        "accuracy_by_truncation": accuracy_group(rows, "truncated"),
        "accuracy_by_cat": accuracy_group(rows, "cat_id") if dataset_id == "catmeows" else {},
        "letter_position_bias": letter_position_bias(rows, labels),
        "confusion": {g: dict(conf[g]) for g in labels},
        "note": cfg["note"],
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / metric_name
    metrics_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    confusion_name = "confusion_matrix.csv" if metric_name == "metrics.json" else "confusion_matrix_mcq.csv"
    with (out_dir / confusion_name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["gold_label"] + labels + ["none"])
        for gold in labels:
            writer.writerow([gold] + [conf[gold].get(pred, 0) for pred in labels] + [conf[gold].get("none", 0)])

    print(f"\n==== {dataset_id}: N={n} acc={out['accuracy']} CI={out['accuracy_ci']} chance={out['chance']} majority={out['majority_baseline']}")
    print(f"macro-F1={out['macro_f1']} weighted-F1={out['weighted_f1']} agreement={out['mean_agreement']} parse={out['parse_status']}")
    print("letter picks:", {k: v["picked"] for k, v in out["letter_position_bias"].items() if v["picked"]})
    for label in labels:
        item = per[label]
        print(f"  {label:>18}: P={item['precision']:.2f} R={item['recall']:.2f} F1={item['f1']:.2f} n={item['support']}")
    print(f"wrote {metrics_path}")
    return out


def write_ablation_table(root):
    root = Path(root)
    variants = ["bare_mcq", "definitions", "definitions_cot", "definitions_cot_self_consistency"]
    rows = []
    for variant in variants:
        path = root / "cat_corpus" / "ablations" / variant / "predictions_mcq.csv"
        if not path.exists():
            continue
        metrics = compute("cat_corpus", path, path.parent)
        rows.append(metrics)
    lines = [
        "# cat_corpus MCQ Ablation",
        "",
        "| Variant | N | K | Accuracy | 95% CI | Macro-F1 | Mean agreement | Parse-fail |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    serializable = []
    for metrics in rows:
        variant = metrics.get("variant") or "unknown"
        pred_path = root / "cat_corpus" / "ablations" / variant / "predictions_mcq.csv"
        pred_rows = list(csv.DictReader(open(pred_path, encoding="utf-8")))
        k = pred_rows[0].get("k", "") if pred_rows else ""
        ci = metrics["accuracy_ci"]
        lines.append(
            f"| {variant} | {metrics['n']} | {k} | {metrics['accuracy']:.3f} | "
            f"[{ci[0]:.3f}, {ci[1]:.3f}] | {metrics['macro_f1']:.3f} | {metrics['mean_agreement']:.3f} | {metrics['parse_fail_rate']:.3f} |"
        )
        serializable.append({k: metrics[k] for k in ["variant", "n", "accuracy", "accuracy_ci", "macro_f1", "mean_agreement", "parse_fail_rate"]})
    out_dir = root / "cat_corpus" / "ablations"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ablation_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "ablation_table.json").write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_dir / 'ablation_table.md'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(DATASETS))
    ap.add_argument("--pred")
    ap.add_argument("--out")
    ap.add_argument("--root", default="outputs/artifacts")
    ap.add_argument("--metric-name", default="metrics_mcq.json")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ablation-table", action="store_true")
    args = ap.parse_args()

    if args.ablation_table:
        write_ablation_table(args.root)
        return

    if args.all:
        for dataset_id in DATASETS:
            pred_path = Path(args.root) / dataset_id / "predictions_mcq.csv"
            if not pred_path.exists():
                print(f"skip {dataset_id}: missing {pred_path}")
                continue
            compute(
                dataset_id,
                pred_path,
                Path(args.root) / dataset_id,
                args.metric_name,
            )
        return

    if not args.dataset:
        raise SystemExit("Pass --dataset, --all, or --ablation-table")
    pred = Path(args.pred) if args.pred else Path(args.root) / args.dataset / "predictions_mcq.csv"
    out = Path(args.out) if args.out else Path(args.root) / args.dataset
    compute(args.dataset, pred, out, args.metric_name)


if __name__ == "__main__":
    main()
