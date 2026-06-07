"""Build a concise summary report for probe artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/artifacts/probe")
    return ap.parse_args()


def _format_ci(point: float, ci: List[float]) -> str:
    if not ci or len(ci) < 2:
        return f"{point:.3f}"
    lo, hi = ci[0], ci[1]
    return f"{point:.3f} [{lo:.3f}, {hi:.3f}]"


def _label_for_key_class(metrics: Dict[str, Any], dataset_id: str) -> str:
    if dataset_id == "catmeows":
        hunger = metrics.get("hunger")
        if hunger:
            return f"{hunger.get('precision', 0.0):.3f}/{hunger.get('recall', 0.0):.3f}"
        return ""
    if dataset_id == "naya_catmood":
        paining = metrics.get("paining")
        if paining:
            return f"{paining.get('precision', 0.0):.3f}/{paining.get('recall', 0.0):.3f}"
        return ""
    if dataset_id == "cat_corpus":
        macro = metrics.get("macro_f1_excluding_single_source")
        if macro is None:
            return "n/a"
        return f"{macro:.3f}"
    return ""


def _leakage_flag(metrics: Dict[str, Any]) -> str:
    groups = metrics.get("per_group_accuracy", [])
    if not groups:
        return "n/a"
    accuracies = [g.get("acc", 0.0) for g in groups if g.get("n", 0) > 0]
    if not accuracies:
        return "n/a"
    spread = max(accuracies) - min(accuracies)
    if spread >= 0.40:
        return "high"
    if spread >= 0.25:
        return "medium"
    return "low"


def build_summary(root: Path):
    root = Path(root)
    rows = []
    for dataset_dir in sorted(root.iterdir()):
        if not dataset_dir.is_dir():
            continue
        metrics_path = dataset_dir / "metrics.json"
        if not metrics_path.exists():
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        rows.append(metrics)

    out = [
        "# Probe Summary",
        "",
        "## Per-head metrics",
        "",
        "| Head | N | #classes | chance | majority | accuracy[CI] | macro-F1[CI] | key class P/R (or macro excl) | leakage flag |",
        "|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for m in rows:
        n = m.get("n", 0)
        dataset_id = m.get("dataset_id", "unknown")
        n_classes = m.get("n_classes", 0)
        chance = m.get("chance", 0)
        majority = m.get("majority", 0)
        acc = _format_ci(m.get("accuracy", 0.0), m.get("accuracy_ci") or [0.0, 0.0])
        macro = _format_ci(m.get("macro_f1", 0.0), m.get("macro_f1_ci") or [0.0, 0.0])
        key_cls = _label_for_key_class(m, dataset_id)
        leakage = _leakage_flag(m)
        out.append(
            f"| {dataset_id} | {n} | {n_classes} | {chance:.3f} | {majority:.3f} | "
            f"{acc} | {macro} | {key_cls} | {leakage} |"
        )

    out.extend(
        [
            "",
            "## Anchors",
            "",
            "| Approach | cat_corpus acc | catmeows macro-F1 | waiting_for_food P/R | note |",
            "|---|---:|---:|---|---|",
            "| Meow-Omni MCQ | 31% | 0.21 | ~33% P | baseline for comparison |",
            "| AST probe (target) | N/A | N/A | N/A | report from table above |",
            "| frontier Gemini (example) | 54% | n/a | n/a | cost comparison only |",
            "",
            "## Notes",
            "",
            "- `cat_corpus` has source-concentration risk for single-source classes; compare "
            "`macro_f1_excluding_single_source` via fine-grained logs.",
            "- `naya_catmood` uses base-clips-only (`*_aug*` dropped) and reports coarse labels as an ablation.",
            "- `paining` in naya is a scraper-mood label, not a validated pain signal.",
        ]
    )

    out_path = root / "summary.md"
    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")


def main():
    args = parse_args()
    build_summary(Path(args.root))


if __name__ == "__main__":
    main()
