"""Build a provider x dataset summary for frontier audio evaluations."""
import argparse
import json
from pathlib import Path

DATASET_ORDER = ["cat_corpus", "catmeows", "naya_catmood"]


def fmt(value):
    return "" if value is None else f"{value:.3f}"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_summary(root):
    root = Path(root)
    rows = []
    for provider_dir in sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []:
        for dataset_id in DATASET_ORDER:
            ddir = provider_dir / dataset_id
            metrics_path = ddir / "metrics.json"
            if not metrics_path.exists():
                continue
            metrics = load_json(metrics_path)
            run = load_json(ddir / "run_summary.json")
            hunger = metrics.get("hunger") or {}
            paining = metrics.get("paining") or {}
            rows.append({
                "provider": provider_dir.name,
                "dataset": dataset_id,
                "n": metrics.get("n", 0),
                "accuracy": metrics.get("accuracy"),
                "accuracy_ci": metrics.get("accuracy_ci", [None, None]),
                "macro_f1": metrics.get("macro_f1"),
                "hunger_precision": hunger.get("precision"),
                "hunger_recall": hunger.get("recall"),
                "paining_precision": paining.get("precision"),
                "paining_recall": paining.get("recall"),
                "parse_fail_rate": metrics.get("parse_fail_rate"),
                "cost_per_clip_usd": run.get("cost_per_clip_usd", 0.0),
                "total_cost_usd": run.get("total_cost_usd", 0.0),
            })

    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Frontier Audio Classification Summary",
        "",
        "No pooled accuracy is reported because the datasets use different taxonomies, class counts, and baselines.",
        "",
        "| Provider | Dataset | N | Accuracy [95% CI] | Macro-F1 | Hunger P/R | Paining P/R | Parse-fail | Cost/clip | Total cost |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        ci = row["accuracy_ci"]
        acc = row["accuracy"]
        acc_cell = "" if acc is None else f"{acc:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]"
        hunger = "" if row["hunger_precision"] is None else f"{row['hunger_precision']:.3f}/{row['hunger_recall']:.3f}"
        paining = "" if row["paining_precision"] is None else f"{row['paining_precision']:.3f}/{row['paining_recall']:.3f}"
        lines.append(
            f"| {row['provider']} | {row['dataset']} | {row['n']} | {acc_cell} | {fmt(row['macro_f1'])} | "
            f"{hunger} | {paining} | {fmt(row['parse_fail_rate'])} | ${row['cost_per_clip_usd']:.6f} | ${row['total_cost_usd']:.4f} |"
        )
    lines.extend([
        "",
        "## Baseline Anchors",
        "",
        "| Approach | cat_corpus acc | catmeows macro-F1 | hunger P/R | cost |",
        "|---|---:|---:|---:|---:|",
        "| Meow-Omni MCQ prompting | 31% | 0.21 | ~33% P | - |",
        "| embedding-probe (AST/Whisper) | 79% | 0.54 | ~33% P @ 50-65% R | tiny |",
        "| AST fine-tune | 70% noisy | 0.46-0.50 | ~18% P | - |",
        "",
        "## Caveats",
        "",
        "- `cat_corpus` has strong source leakage; chirrup and caterwaul are single-source classes.",
        "- `catmeows` labels behavioral context; emphasize macro-F1 and `waiting_for_food` precision/recall.",
        "- `naya_catmood` excludes `_aug` duplicates. Its `Paining` label is scraper-labeled mood, not validated clinical pain.",
    ])
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {root / 'summary.md'} and {root / 'summary.json'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/artifacts/frontier")
    args = ap.parse_args()
    build_summary(args.root)


if __name__ == "__main__":
    main()
