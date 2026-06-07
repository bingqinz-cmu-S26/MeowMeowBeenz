"""Part A: AST + LogisticRegression 5-class probe with StratifiedGroupKFold OOF predictions.

Writes outputs/artifacts/taxonomy5/probe/predictions.csv (OOF preds for every clip)
and metrics via taxonomy5_metrics.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from taxonomy5 import BUCKETS  # noqa: E402

EMB_DIR = Path("outputs/artifacts/taxonomy5/_emb")
OUT_DIR = Path("outputs/artifacts/taxonomy5/probe")
N_SPLITS = 5
SEED = 13


def load():
    emb = np.load(EMB_DIR / "embeddings.npy")
    rows = list(csv.DictReader(open(EMB_DIR / "clips.csv", encoding="utf-8")))
    assert emb.shape[0] == len(rows), (emb.shape, len(rows))
    return emb, rows


def main():
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.metrics import f1_score

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    emb, rows = load()
    y = np.array([r["bucket"] for r in rows])
    groups = np.array([r["group_key"] for r in rows])
    label_idx = {b: i for i, b in enumerate(BUCKETS)}
    y_idx = np.array([label_idx[b] for b in y])

    sgkf = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    oof_pred = np.empty(len(rows), dtype=object)
    fold_assign = np.full(len(rows), -1, dtype=int)
    fold_macro_f1 = []

    for fold, (tr, te) in enumerate(sgkf.split(emb, y_idx, groups)):
        scaler = StandardScaler().fit(emb[tr])
        # newer sklearn dropped multi_class (lbfgs is multinomial by default for multiclass)
        clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
        clf.fit(scaler.transform(emb[tr]), y_idx[tr])
        pred = clf.predict(scaler.transform(emb[te]))
        for i, p in zip(te, pred):
            oof_pred[i] = BUCKETS[p]
            fold_assign[i] = fold
        f1 = f1_score(y_idx[te], pred, labels=list(range(len(BUCKETS))), average="macro", zero_division=0)
        fold_macro_f1.append(float(f1))
        # leakage check: any group in both train and test?
        overlap = set(groups[tr]) & set(groups[te])
        print(f"fold {fold}: n_test={len(te)} macro-F1={f1:.4f} group_overlap={len(overlap)}")

    assert all(p is not None for p in oof_pred), "some clips never in any test fold"

    # write OOF predictions
    with (OUT_DIR / "predictions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "clip_path", "dataset_id", "native_label", "gold_label", "pred_label",
            "group_key", "source_hint", "hunger", "fold", "correct",
        ])
        w.writeheader()
        for i, r in enumerate(rows):
            w.writerow({
                "clip_path": r["clip_path"], "dataset_id": r["dataset_id"],
                "native_label": r["native_label"], "gold_label": r["bucket"],
                "pred_label": oof_pred[i], "group_key": r["group_key"],
                "source_hint": r["source_hint"], "hunger": r["hunger"], "fold": int(fold_assign[i]),
                "correct": str(oof_pred[i] == r["bucket"]).lower(),
            })

    mean = float(np.mean(fold_macro_f1))
    sd = float(np.std(fold_macro_f1, ddof=1)) if len(fold_macro_f1) > 1 else 0.0
    ci = 1.96 * sd / (len(fold_macro_f1) ** 0.5)
    (OUT_DIR / "fold_macro_f1.json").write_text(json.dumps({
        "fold_macro_f1": fold_macro_f1,
        "mean": round(mean, 4),
        "ci95": round(ci, 4),
        "ci95_lo": round(mean - ci, 4),
        "ci95_hi": round(mean + ci, 4),
    }, indent=2), encoding="utf-8")
    print(f"\nmacro-F1 across folds: {mean:.4f} +/- {ci:.4f} (95% CI)")
    print(f"wrote {OUT_DIR / 'predictions.csv'}")


if __name__ == "__main__":
    main()
