"""Train one probe per dataset on frozen AST embeddings."""

from __future__ import annotations

import argparse
import csv
import json
import math
import inspect
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Sequence

import joblib
import numpy as np

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.preprocessing import StandardScaler

from probe_registry import DATASET_BY_ID, PROBE_DATASETS, ProbeDataset, coarse_label_naya


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["all"] + [cfg.dataset_id for cfg in PROBE_DATASETS], default="all")
    parser.add_argument("--emb-dir", default="outputs/artifacts/probe/_emb")
    parser.add_argument("--out-root", default="outputs/artifacts/probe")
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--c", type=float, default=1.0)
    parser.add_argument("--max-iter", type=int, default=2000)
    parser.add_argument("--class-weight", default="balanced")
    parser.add_argument("--multi-class", default="multinomial")
    return parser.parse_args()


def _select_datasets(dataset_id: str) -> List[ProbeDataset]:
    if dataset_id == "all":
        return PROBE_DATASETS
    return [DATASET_BY_ID[dataset_id]]


def _wilson_interval(successes: int, n: int, z: float = 1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def _ci_from_samples(values: Sequence[float]):
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = float(np.mean(values))
    if n == 1:
        return mean, mean, mean
    sd = float(np.std(values, ddof=1))
    # For k=5, t_0.975 ~ 2.776.
    if n == 2:
        t = 12.706
    elif n == 3:
        t = 4.303
    elif n == 4:
        t = 3.182
    elif n == 5:
        t = 2.776
    else:
        t = 1.96
    half = t * sd / math.sqrt(n)
    return mean, max(0.0, mean - half), min(1.0, mean + half)


def _precision_recall_f1_for_confusion(confusion: Dict[str, Dict[str, int]], labels: Sequence[str]):
    out = {}
    for label in labels:
        tp = float(confusion[label][label])
        fp = sum(float(confusion[other][label]) for other in labels if other != label)
        fn = sum(float(confusion[label][other]) for other in labels if other != label)
        support = sum(float(confusion[label][other]) for other in labels)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[label] = {
            "support": int(support),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return out


def _macro_f1_from_confusion(confusion: Dict[str, Dict[str, int]], labels: Sequence[str]):
    per = _precision_recall_f1_for_confusion(confusion, labels)
    if not labels:
        return 0.0
    return float(np.mean([per[label]["f1"] for label in labels]))


def _group_accuracy(labels: Sequence[str], preds: Sequence[str], groups: Sequence[str]):
    by_group = defaultdict(lambda: {"correct": 0, "n": 0})
    for gold, pred, group in zip(labels, preds, groups):
        entry = by_group[group]
        entry["n"] += 1
        if gold == pred:
            entry["correct"] += 1
    rows = []
    for key in sorted(by_group):
        counts = by_group[key]
        acc = counts["correct"] / counts["n"] if counts["n"] else 0.0
        rows.append({"group": key, "n": counts["n"], "correct": counts["correct"], "acc": acc})
    return rows


def _coarse_metrics(labels: Sequence[str], preds: Sequence[str]):
    c_labels = [coarse_label_naya(l) for l in labels]
    c_preds = [coarse_label_naya(l) for l in preds]
    classes = sorted(set(c_labels))
    conf = {lab: {pl: 0 for pl in classes} for lab in classes}
    for g, p in zip(c_labels, c_preds):
        conf[g][p] += 1
    per = _precision_recall_f1_for_confusion(conf, classes)
    return {
        "classes": classes,
        "confusion": conf,
        "per_class": per,
        "macro_f1": _macro_f1_from_confusion(conf, classes),
    }


def _build_fold_indices(y: Sequence[str], groups: Sequence[str], n_splits: int, seed: int):
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    try:
        return list(sgkf.split(np.zeros(len(y)), y, groups=groups))
    except ValueError:
        kf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        return list(kf.split(np.zeros(len(y)), y))


def _make_logistic_regression(args) -> LogisticRegression:
    kwargs = {
        "max_iter": args.max_iter,
        "C": args.c,
        "class_weight": args.class_weight,
        "solver": "lbfgs",
    }
    if "multi_class" in inspect.signature(LogisticRegression.__init__).parameters:
        kwargs["multi_class"] = args.multi_class
    return LogisticRegression(**kwargs)


def _load_embeddings_and_meta(cfg: ProbeDataset, emb_dir: Path):
    emb_path = emb_dir / f"{cfg.dataset_id}.npy"
    meta_path = emb_dir / f"{cfg.dataset_id}_meta.csv"
    if not emb_path.exists() or not meta_path.exists():
        raise SystemExit(
            f"Missing artifacts for {cfg.dataset_id}: {emb_path} or {meta_path}. "
            f"Run scripts/ast_embed.py first."
        )

    X = np.load(emb_path)
    rows = []
    with meta_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "path": row["clip_path"],
                    "label": row["label"],
                    "group_key": row["group_key"],
                    "source_hint": row["source_hint"],
                }
            )
    if len(rows) != len(X):
        raise SystemExit(f"Embeddings/meta length mismatch for {cfg.dataset_id}: {len(X)} != {len(rows)}")
    return X, rows


def _fit_predict_folds(X: np.ndarray, y: Sequence[str], groups: Sequence[str], class_names: Sequence[str], args):
    n = len(y)
    oof_pred = np.empty(n, dtype=object)
    oof_proba = np.zeros((n, len(class_names)), dtype=np.float32)
    oof_fold = np.full(n, -1, dtype=int)
    fold_scores = []
    y_arr = np.array(y)
    class_index = {label: i for i, label in enumerate(class_names)}
    class_names_arr = np.array(class_names)
    splits = _build_fold_indices(y, groups, args.n_splits, args.seed)

    for fold_i, (train_idx, val_idx) in enumerate(splits):
        scaler = StandardScaler()
        Xtr = scaler.fit_transform(X[train_idx])
        Xv = scaler.transform(X[val_idx])
        clf = _make_logistic_regression(args)
        clf.fit(Xtr, y_arr[train_idx])
        proba = clf.predict_proba(Xv)
        fold_proba = np.zeros((len(val_idx), len(class_names)), dtype=np.float32)
        for j, label in enumerate(clf.classes_):
            fold_proba[:, class_index[label]] = proba[:, j]
        pred = class_names_arr[np.argmax(fold_proba, axis=1)] if class_names else ""
        oof_proba[val_idx] = fold_proba
        oof_pred[val_idx] = pred
        fold_f1 = f1_score(y_arr[val_idx], pred, average="macro", labels=class_names, zero_division=0.0)
        fold_scores.append(float(fold_f1))
        for i in val_idx:
            oof_fold[i] = fold_i

    return oof_pred, oof_proba, fold_scores, oof_fold


def train_dataset(cfg: ProbeDataset, args):
    X, rows = _load_embeddings_and_meta(cfg, Path(args.emb_dir))
    n = len(rows)
    y = [row["label"] for row in rows]
    groups = [row["group_key"] for row in rows]
    classes = sorted(set(y))

    oof_fold = np.full(n, -1, dtype=int)
    oof_pred, oof_proba, fold_scores, oof_fold = _fit_predict_folds(X, y, groups, classes, args)

    y_true = np.array(y, dtype=object)
    correct = int((y_true == oof_pred).sum())
    acc, acc_lo, acc_hi = _wilson_interval(correct, n)
    majority = Counter(y).most_common(1)[0][1] / n

    confusion = {lab: {pl: 0 for pl in classes} for lab in classes}
    for gold, pred in zip(y_true, oof_pred):
        if gold in confusion and pred in confusion[gold]:
            confusion[gold][pred] += 1

    per_class = _precision_recall_f1_for_confusion(confusion, classes)
    macro_f1 = float(np.mean([per_class[lab]["f1"] for lab in classes]))
    mean_macro, macro_lo, macro_hi = _ci_from_samples(fold_scores)

    group_acc = _group_accuracy(y_true.tolist(), oof_pred.tolist(), groups)

    out_dir = Path(args.out_root) / cfg.dataset_id
    out_dir.mkdir(parents=True, exist_ok=True)

    oof_rows = []
    for i, row in enumerate(rows):
        item = {
            "clip_path": row["path"],
            "gold_label": row["label"],
            "pred_label": oof_pred[i],
            "group_key": row["group_key"],
            "source_hint": row.get("source_hint", ""),
            "fold": int(oof_fold[i]),
            "probability_max": float(oof_proba[i].max()),
        }
        for label, score in zip(classes, oof_proba[i]):
            item[f"proba_{label}"] = f"{float(score):.6f}"
        oof_rows.append(item)

    with (out_dir / "oof_predictions.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(oof_rows[0].keys()))
        writer.writeheader()
        writer.writerows(oof_rows)

    metrics = {
        "dataset_id": cfg.dataset_id,
        "n": n,
        "n_classes": len(classes),
        "classes": classes,
        "chance": cfg.chance,
        "majority": majority,
        "accuracy": acc,
        "accuracy_ci": [acc_lo, acc_hi],
        "macro_f1": macro_f1,
        "macro_f1_fold_mean": mean_macro,
        "macro_f1_ci": [macro_lo, macro_hi],
        "macro_f1_fold_scores": fold_scores,
        "per_class": per_class,
        "confusion": confusion,
        "per_group_accuracy": group_acc,
        "hunger": per_class.get("waiting_for_food"),
    }

    if cfg.dataset_id == "cat_corpus" and cfg.single_source_classes:
        mask = [row["label"] not in cfg.single_source_classes for row in rows]
        if any(mask):
            y2 = [row["label"] for row, keep in zip(rows, mask) if keep]
            p2 = [oof_pred[i] for i, keep in enumerate(mask) if keep]
            classes2 = sorted(set(y2))
            conf2 = {lab: {pl: 0 for pl in classes2} for lab in classes2}
            for gold, pred in zip(y2, p2):
                if gold in conf2 and pred in conf2[gold]:
                    conf2[gold][pred] += 1
            metrics["macro_f1_excluding_single_source"] = _macro_f1_from_confusion(conf2, classes2)

    if cfg.dataset_id == "naya_catmood":
        coarse = _coarse_metrics(y, oof_pred.tolist())
        metrics["coarse"] = coarse
        metrics["paining"] = per_class.get("paining")

    with (out_dir / "metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    # train final model and persist
    scaler = StandardScaler()
    X_all = scaler.fit_transform(X)
    model = _make_logistic_regression(args)
    model.fit(X_all, y_true)

    joblib.dump({"scaler": scaler, "model": model}, out_dir / "probe.joblib")
    with (out_dir / "label_names.json").open("w", encoding="utf-8") as f:
        json.dump({"label_names": sorted(set(y))}, f, indent=2, ensure_ascii=False)

    print(
        f"{cfg.dataset_id}: n={n}, acc={acc:.4f}, "
        f"macro_f1={macro_f1:.4f} (CV mean {mean_macro:.4f}), folds={len(fold_scores)}"
    )


def main():
    args = parse_args()
    for cfg in _select_datasets(args.dataset):
        train_dataset(cfg, args)


if __name__ == "__main__":
    main()
