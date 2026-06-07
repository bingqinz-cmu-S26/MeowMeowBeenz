"""Part C deliverable: build the head-to-head comparison summary.md + the probe-on-subsample slice.

- probe full CV metrics: outputs/artifacts/taxonomy5/probe/metrics.json
- probe on Gemini subsample: filter OOF preds to the exact Gemini clip set -> probe/metrics_subsample.json
- gemini metrics: outputs/artifacts/taxonomy5/gemini-3.5-flash/metrics.json
- summary.md with the comparison table, confusions, leakage breakdown, narrative.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from taxonomy5 import BUCKETS  # noqa: E402
import taxonomy5_metrics as M  # noqa: E402

ROOT = Path("outputs/artifacts/taxonomy5")
PROBE_DIR = ROOT / "probe"
GEM_DIR = ROOT / "gemini-3.5-flash"


def build_probe_subsample(gemini_pred_path):
    gem_rows = list(csv.DictReader(open(gemini_pred_path, encoding="utf-8")))
    gem_paths = {r["clip_path"] for r in gem_rows}
    probe_rows = list(csv.DictReader(open(PROBE_DIR / "predictions.csv", encoding="utf-8")))
    sub = [r for r in probe_rows if r["clip_path"] in gem_paths]
    out = PROBE_DIR / "predictions_subsample.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=probe_rows[0].keys())
        w.writeheader()
        w.writerows(sub)
    return out, len(sub), len(gem_paths)


def fmt_ci(m):
    return f"{m['accuracy']:.3f} [{m['accuracy_ci'][0]:.3f}, {m['accuracy_ci'][1]:.3f}]"


def per_class_f1_str(m):
    return ", ".join(f"{b}={m['per_class'][b]['f1']:.2f}" for b in BUCKETS)


def confusion_md(m):
    lines = ["| gold \\ pred | " + " | ".join(BUCKETS) + " | none |", "|" + "---|" * (len(BUCKETS) + 2)]
    for g in BUCKETS:
        row = m["confusion"].get(g, {})
        lines.append("| " + g + " | " + " | ".join(str(row.get(p, 0)) for p in BUCKETS) + " | " + str(row.get("none", 0)) + " |")
    return "\n".join(lines)


def leakage_md(m):
    pdb = m["per_dataset_bucket_accuracy"]
    datasets = list(pdb.keys())
    lines = ["| bucket | " + " | ".join(datasets) + " |", "|" + "---|" * (len(datasets) + 1)]
    for b in BUCKETS:
        cells = []
        for ds in datasets:
            cell = pdb.get(ds, {}).get(b)
            cells.append(f"{cell['acc']:.2f} (n={cell['n']})" if cell else "-")
        lines.append("| " + b + " | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    gem_pred = GEM_DIR / "predictions.csv"
    if not gem_pred.exists():
        raise SystemExit("gemini predictions.csv not found; run taxonomy5_gemini.py first")

    # 1. probe full CV (already computed, recompute for freshness)
    probe_full = M.compute("AST+probe (full CV)", PROBE_DIR / "predictions.csv", PROBE_DIR)

    # 2. probe on gemini subsample
    sub_path, n_sub, n_gem = build_probe_subsample(gem_pred)
    probe_sub = M.compute("AST+probe (Gemini subsample)", sub_path, PROBE_DIR)
    # rename its metrics file
    (PROBE_DIR / "metrics.json").replace(PROBE_DIR / "metrics_full.json")  # save full separately
    (PROBE_DIR / "metrics_full.json")  # keep
    Path(PROBE_DIR / "metrics_subsample.json").write_text(json.dumps(probe_sub, ensure_ascii=False, indent=2), encoding="utf-8")
    # restore full metrics.json
    Path(PROBE_DIR / "metrics.json").write_text(json.dumps(probe_full, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. gemini
    gem = M.compute("gemini-3.5-flash (subsample)", gem_pred, GEM_DIR)

    # ---- summary.md ----
    data_report = json.loads((ROOT / "data_report.json").read_text(encoding="utf-8"))
    fold = json.loads((PROBE_DIR / "fold_macro_f1.json").read_text(encoding="utf-8"))

    rows = [
        ("AST+probe (full CV)", probe_full, f"{fold['mean']:.3f} [{fold['ci95_lo']:.3f}, {fold['ci95_hi']:.3f}]"),
        ("AST+probe (Gemini subsample)", probe_sub, f"{probe_sub['macro_f1']:.3f}"),
        ("gemini-3.5-flash (subsample)", gem, f"{gem['macro_f1']:.3f}"),
    ]

    md = []
    md.append("# Unified 5-Class Cat-Audio Taxonomy: AST-Probe vs Gemini 3.5 Flash\n")
    md.append("Buckets: **content, soliciting, agitated, distress, hunting**. Every clip mapped via probe_plan.md S1b; discards per S1c. Probe macro-F1 CI is mean +/- 95% across 5 StratifiedGroupKFold folds (group = dataset::cat-or-source, zero train/test group overlap verified).\n")

    md.append("## Comparison table\n")
    md.append("| Method | N | Accuracy [95% CI] | Macro-F1 | Per-class F1 | Hunger P/R | Parse-fail | Cost |")
    md.append("|---|---:|---|---|---|---|---:|---:|")
    for name, m, macro in rows:
        hunger = f"{m['hunger']['precision']:.2f}/{m['hunger']['recall']:.2f}"
        cost = f"${m['total_cost_usd']:.4f}" if m["total_cost_usd"] else "~$0"
        md.append(
            f"| {name} | {m['n']} | {fmt_ci(m)} | {macro} | {per_class_f1_str(m)} | {hunger} | {m['parse_fail_rate']:.3f} | {cost} |"
        )
    md.append("")

    md.append("## Data assembly (probe_plan.md S1c)\n")
    md.append(f"- Raw counts: cat_corpus {data_report['raw_counts']['cat_corpus']}, catmeows {data_report['raw_counts']['catmeows']}, naya base-only {data_report['raw_counts']['naya_catmood']} (naya `_aug` leaked: {data_report['naya_aug_leaked']}).")
    md.append(f"- Cross-dataset shared base filenames (cat_corpus vs naya): {data_report['cross_dataset_shared_stems']}. Bucket-conflict stems dropped from BOTH sides: {data_report['cross_dataset_conflict_stems_dropped_both']} (-> {data_report['cc_clips_dropped_by_rule2']} cat_corpus clips removed). Bucket-agreeing stems deduped keeping cat_corpus copy: {data_report['cross_dataset_agree_stems_merged_keep_cc']} (-> {data_report['naya_clips_dropped_by_rule2']} naya clips removed).")
    md.append(f"- **Final total: {data_report['final_total']} clips**, {data_report['n_groups']} CV groups. Hunger soft-tag positives (catmeows waiting_for_food): {data_report['hunger_positive']}.")
    md.append("")
    md.append("### Final per-bucket x per-dataset counts\n")
    pbd = data_report["per_bucket_per_dataset"]
    md.append("| bucket | cat_corpus | catmeows | naya | total |")
    md.append("|---|---:|---:|---:|---:|")
    for b in BUCKETS:
        d = pbd[b]
        md.append(f"| {b} | {d.get('cat_corpus',0)} | {d.get('catmeows',0)} | {d.get('naya',0)} | {data_report['per_bucket_total'][b]} |")
    md.append("")

    for name, m in [("AST+probe (full CV)", probe_full), ("AST+probe (Gemini subsample)", probe_sub), ("gemini-3.5-flash (subsample)", gem)]:
        md.append(f"## Confusion matrix - {name}\n")
        md.append(confusion_md(m))
        md.append("")

    md.append("## Per-dataset x per-bucket accuracy (dataset-signature leakage check) - probe full CV\n")
    md.append(leakage_md(probe_full))
    md.append("")
    md.append("## Per-dataset x per-bucket accuracy - gemini (subsample)\n")
    md.append(leakage_md(gem))
    md.append("")

    # narrative
    pf = probe_sub["macro_f1"]
    gf = gem["macro_f1"]
    pa = probe_sub["accuracy"]; pa_ci = probe_sub["accuracy_ci"]
    ga = gem["accuracy"]; ga_ci = gem["accuracy_ci"]
    overlap = not (pa_ci[1] < ga_ci[0] or ga_ci[1] < pa_ci[0])
    md.append("## Narrative\n")
    md.append(f"**(a) Probe vs Gemini on the 5 tags (same {gem['n']} clips).** On the identical subsample, AST+probe scores accuracy {pa:.3f} [{pa_ci[0]:.3f}, {pa_ci[1]:.3f}] / macro-F1 {pf:.3f}, vs gemini-3.5-flash accuracy {ga:.3f} [{ga_ci[0]:.3f}, {ga_ci[1]:.3f}] / macro-F1 {gf:.3f}. The supervised probe is **{'ahead by ' + format(pa-ga, '+.3f') + ' accuracy / ' + format(pf-gf, '+.3f') + ' macro-F1' if pa>ga else 'behind'}**; the accuracy CIs {'OVERLAP (treat as tied)' if overlap else 'do NOT overlap (a real gap)'}.")
    # per-class confusions
    def worst_confusions(m, k=3):
        pairs = []
        for g in BUCKETS:
            for p, c in m["confusion"].get(g, {}).items():
                if p != g and p in BUCKETS and c > 0:
                    pairs.append((c, g, p))
        pairs.sort(reverse=True)
        return pairs[:k]
    pc = worst_confusions(probe_sub)
    gc = worst_confusions(gem)
    md.append(f"\n**(b) Which buckets each confuses.** Probe's top cross-bucket confusions (subsample): " + "; ".join(f"{g}->{p} ({c})" for c, g, p in pc) + ". Gemini's: " + "; ".join(f"{g}->{p} ({c})" for c, g, p in gc) + ".")
    md.append(f"\n**(c) Dataset-signature leakage.** See the per-dataset x per-bucket tables above. Because each bucket draws from multiple datasets with different recording signatures, large per-dataset accuracy gaps within one bucket would flag that the probe is keying on recording provenance rather than the vocalization. Note also the S1c data artifact: **all 40 cat_corpus `meow` clips were discarded** because their base filenames collide with naya clips that map to different buckets - so the `soliciting` bucket is served only by catmeows (waiting_for_food) and naya (mothercall).")
    md.append(f"\n**Hunger soft-tag.** Hunger positives = catmeows waiting_for_food (n={data_report['hunger_positive']}). Among true food clips, recall of being predicted `soliciting`: probe(full CV) {probe_full['hunger']['recall']:.2f}, gemini {gem['hunger']['recall']:.2f}. Precision is low by construction (soliciting also contains mothercall and meow), confirming hunger is only a weak sub-signal of soliciting, not a confident alert.")
    md.append("")

    (ROOT / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nwrote {ROOT / 'summary.md'}")
    print(f"probe subsample N={n_sub} of {n_gem} gemini clips")


if __name__ == "__main__":
    main()
