"""Part C metrics: compute unified-taxonomy metrics for any predictions.csv (probe or gemini).

Reuses wilson() + prf() primitives from metrics_report.py.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics_report import wilson, prf  # noqa: E402
from taxonomy5 import BUCKETS  # noqa: E402

DATASET_SHORT = {"cat_corpus": "cat_corpus", "catmeows": "catmeows", "naya_catmood": "naya"}


def hunger_pr(rows, mode="true"):
    """Recover the hunger boolean among soliciting clips.

    mode='true': within clips whose GOLD bucket is soliciting (catmeows F = hunger=1),
                 treat hunger=1 as positive; predicted-positive = predicted soliciting.
    Returns precision/recall of recovering the hunger soft-tag.
    We report: among clips with hunger=1 (true food clips), what fraction are predicted soliciting (recall),
    and among clips predicted soliciting, what fraction are hunger=1 (precision).
    """
    pred_sol = [r for r in rows if r.get("pred_label") == "soliciting"]
    true_hunger = [r for r in rows if str(r.get("hunger")) == "1"]
    tp = sum(1 for r in pred_sol if str(r.get("hunger")) == "1")
    precision = tp / len(pred_sol) if pred_sol else 0.0
    recall = tp / len(true_hunger) if true_hunger else 0.0
    return {
        "n_pred_soliciting": len(pred_sol),
        "n_true_hunger": len(true_hunger),
        "tp": tp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
    }


def per_dataset_bucket_accuracy(rows):
    """accuracy per (dataset, gold bucket): exposes dataset-signature leakage."""
    grid = defaultdict(lambda: [0, 0])  # (dataset, bucket) -> [correct, n]
    for r in rows:
        ds = DATASET_SHORT.get(r["dataset_id"], r["dataset_id"])
        b = r["gold_label"]
        grid[(ds, b)][1] += 1
        grid[(ds, b)][0] += (r.get("pred_label") == b)
    out = {}
    for (ds, b), (c, n) in sorted(grid.items()):
        out.setdefault(ds, {})[b] = {"correct": c, "n": n, "acc": round(c / n, 4) if n else 0.0}
    return out


def compute(name, pred_path, out_dir):
    rows = list(csv.DictReader(open(pred_path, encoding="utf-8")))
    n = len(rows)
    correct = sum(r["gold_label"] == r.get("pred_label") for r in rows)
    acc, lo, hi = wilson(correct, n)
    counts = Counter(r["gold_label"] for r in rows)
    majority = max(counts.values()) / n if n else 0.0
    conf, per = prf(rows, BUCKETS)
    macro = sum(v["f1"] for v in per.values()) / len(BUCKETS)
    weighted = sum(v["f1"] * v["support"] for v in per.values()) / n if n else 0.0
    parse = Counter(r.get("parse_status") or "n/a" for r in rows)
    parse_fail = parse.get("none", 0) + parse.get("error", 0)
    total_cost = sum(float(r.get("cost_usd") or 0.0) for r in rows)

    out = {
        "name": name,
        "n": n,
        "classes": BUCKETS,
        "accuracy": round(acc, 4),
        "accuracy_ci": [round(lo, 4), round(hi, 4)],
        "majority_baseline": round(majority, 4),
        "macro_f1": round(macro, 4),
        "weighted_f1": round(weighted, 4),
        "per_class": per,
        "hunger": hunger_pr(rows),
        "parse_status": dict(parse),
        "parse_fail_rate": round(parse_fail / n, 4) if n else 0.0,
        "per_dataset_bucket_accuracy": per_dataset_bucket_accuracy(rows),
        "confusion": {g: dict(conf[g]) for g in BUCKETS},
        "total_cost_usd": round(total_cost, 6),
        "support_by_bucket": dict(counts),
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    with (out_dir / "confusion_matrix.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gold"] + BUCKETS + ["none"])
        for g in BUCKETS:
            w.writerow([g] + [conf[g].get(p, 0) for p in BUCKETS] + [conf[g].get("none", 0)])

    print(f"== {name}: N={n} acc={out['accuracy']} CI={out['accuracy_ci']} macroF1={out['macro_f1']} parse_fail={out['parse_fail_rate']} cost=${out['total_cost_usd']}")
    for b in BUCKETS:
        it = per[b]
        print(f"  {b:>11}: P={it['precision']:.2f} R={it['recall']:.2f} F1={it['f1']:.2f} n={it['support']}")
    print(f"  hunger: P={out['hunger']['precision']} R={out['hunger']['recall']} (pred_sol={out['hunger']['n_pred_soliciting']}, true_hunger={out['hunger']['n_true_hunger']})")
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    compute(args.name, args.pred, args.out)


if __name__ == "__main__":
    main()
