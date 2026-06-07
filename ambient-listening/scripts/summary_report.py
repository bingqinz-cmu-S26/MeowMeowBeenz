"""Build cross-dataset MCQ summary without pooling incompatible taxonomies."""
import argparse
import json
from pathlib import Path

DATASET_ORDER = ["cat_corpus", "catmeows", "catsound_v2"]


def best_worst(per_class):
    items = sorted(per_class.items(), key=lambda kv: kv[1].get("f1", 0.0))
    if not items:
        return "", ""
    worst = f"{items[0][0]} ({items[0][1].get('f1', 0):.2f})"
    best = f"{items[-1][0]} ({items[-1][1].get('f1', 0):.2f})"
    return best, worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/artifacts")
    args = ap.parse_args()
    root = Path(args.root)
    rows = []
    for dataset_id in DATASET_ORDER:
        path = root / dataset_id / "metrics_mcq.json"
        if not path.exists():
            continue
        metrics = json.loads(path.read_text(encoding="utf-8"))
        best, worst = best_worst(metrics.get("per_class", {}))
        rows.append({
            "dataset": dataset_id,
            "n": metrics["n"],
            "n_classes": metrics["n_classes"],
            "chance": metrics["chance"],
            "majority": metrics["majority_baseline"],
            "accuracy": metrics["accuracy"],
            "accuracy_ci": metrics["accuracy_ci"],
            "macro_f1": metrics["macro_f1"],
            "best_class": best,
            "worst_class": worst,
            "parse_fail_rate": metrics["parse_fail_rate"],
        })

    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# MCQ Audio-Only Evaluation Summary",
        "",
        "No pooled accuracy is reported because the datasets use different taxonomies, class counts, and baselines.",
        "",
        "| Dataset | N | Classes | Chance | Majority | Accuracy [95% CI] | Macro-F1 | Best class | Worst class | Parse-fail |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|---:|",
    ]
    for row in rows:
        ci = row["accuracy_ci"]
        lines.append(
            f"| {row['dataset']} | {row['n']} | {row['n_classes']} | {row['chance']:.3f} | "
            f"{row['majority']:.3f} | {row['accuracy']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] | "
            f"{row['macro_f1']:.3f} | {row['best_class']} | {row['worst_class']} | {row['parse_fail_rate']:.3f} |"
        )
    lines.extend([
        "",
        "## Caveats",
        "",
        "- `cat_corpus` has strong source leakage; chirrup and caterwaul are single-source classes.",
        "- `catmeows` labels behavioral context, which may not be recoverable from audio alone; macro-F1 should be emphasized over accuracy.",
        "- `catsound_v2` is exploratory only because it has 5 clips per class and overlaps with scrape sources used by `cat_corpus`.",
    ])
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {root / 'summary.md'} and {root / 'summary.json'}")


if __name__ == "__main__":
    main()
