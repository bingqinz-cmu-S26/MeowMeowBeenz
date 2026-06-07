"""Embed all taxonomy5 clips with AST, reusing cached cat_corpus/catmeows arrays.

Writes:
  outputs/artifacts/taxonomy5/_emb/embeddings.npy   (N x 768, aligned to clips.csv order)
  outputs/artifacts/taxonomy5/_emb/clips.csv        (clip metadata, the canonical order)
  outputs/artifacts/taxonomy5/_emb/naya.npy         (cached naya embeddings, source-stem keyed)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from taxonomy5 import build_clips, Clip  # noqa: E402
from probe_registry import iter_rows, enrich_rows_with_group_and_source, DATASET_BY_ID  # noqa: E402
from ast_embed import EmbeddingModel, _load_audio  # noqa: E402

EMB_DIR = Path("outputs/artifacts/taxonomy5/_emb")
MODEL_NAME = "MIT/ast-finetuned-audioset-10-10-0.4593"
SR = 16000
TRIM = 30.0


def _load_cached_dataset_emb(did: str) -> dict:
    """Return {clip_path: vector} for cat_corpus/catmeows from probe/_emb, ordering verified."""
    npy = Path(f"outputs/artifacts/probe/_emb/{did}.npy")
    meta = Path(f"outputs/artifacts/probe/_emb/{did}_meta.csv")
    if not (npy.exists() and meta.exists()):
        return {}
    emb = np.load(npy)
    rows = list(csv.DictReader(open(meta, encoding="utf-8")))
    # verify against current iter_rows ordering
    cfg = DATASET_BY_ID[did]
    cur = [r["path"] for r in enrich_rows_with_group_and_source(iter_rows(cfg), cfg)]
    meta_paths = [r["clip_path"] for r in rows]
    if cur != meta_paths or emb.shape[0] != len(meta_paths):
        print(f"WARNING: cached {did} ordering mismatch; will re-embed.")
        return {}
    print(f"reuse cached {did}: {emb.shape}")
    return {p: emb[i] for i, p in enumerate(meta_paths)}


def main():
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    clips, report = build_clips(verbose=True)

    # cached cat_corpus + catmeows vectors keyed by path
    cached = {}
    cached.update(_load_cached_dataset_emb("cat_corpus"))
    cached.update(_load_cached_dataset_emb("catmeows"))

    # naya cache (built here once, reused on rerun)
    naya_cache_npy = EMB_DIR / "naya.npy"
    naya_cache_paths = EMB_DIR / "naya_paths.csv"
    naya_cached = {}
    if naya_cache_npy.exists() and naya_cache_paths.exists():
        arr = np.load(naya_cache_npy)
        paths = [r[0] for r in csv.reader(open(naya_cache_paths, encoding="utf-8"))]
        if arr.shape[0] == len(paths):
            naya_cached = {p: arr[i] for i, p in enumerate(paths)}
            print(f"reuse cached naya: {arr.shape}")

    needed_naya = [c.clip_path for c in clips if c.dataset_id == "naya_catmood" and c.clip_path not in naya_cached]
    if needed_naya:
        print(f"embedding {len(needed_naya)} naya clips fresh ...")
        model = EmbeddingModel(MODEL_NAME, "cpu", "mean", SR)
        new_vecs = {}
        for i, p in enumerate(needed_naya, 1):
            new_vecs[p] = model.embed(p, TRIM)
            if i % 50 == 0 or i == len(needed_naya):
                print(f"  naya {i}/{len(needed_naya)}")
        naya_cached.update(new_vecs)
        # rewrite full naya cache
        all_naya_paths = sorted(naya_cached)
        arr = np.stack([naya_cached[p] for p in all_naya_paths]).astype(np.float32)
        np.save(naya_cache_npy, arr)
        with naya_cache_paths.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for p in all_naya_paths:
                w.writerow([p])
        print(f"wrote naya cache {arr.shape}")

    # any cat_corpus/catmeows not cached (shouldn't happen) -> embed fresh
    missing = [c.clip_path for c in clips if c.clip_path not in cached and c.clip_path not in naya_cached]
    if missing:
        print(f"embedding {len(missing)} uncached clips fresh ...")
        model = EmbeddingModel(MODEL_NAME, "cpu", "mean", SR)
        for p in missing:
            cached[p] = model.embed(p, TRIM)

    lookup = {}
    lookup.update(cached)
    lookup.update(naya_cached)

    vecs = np.stack([lookup[c.clip_path] for c in clips]).astype(np.float32)
    np.save(EMB_DIR / "embeddings.npy", vecs)
    with (EMB_DIR / "clips.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["clip_path", "dataset_id", "native_label", "bucket", "group_key", "source_hint", "hunger"])
        w.writeheader()
        for c in clips:
            w.writerow({
                "clip_path": c.clip_path, "dataset_id": c.dataset_id, "native_label": c.native_label,
                "bucket": c.bucket, "group_key": c.group_key, "source_hint": c.source_hint, "hunger": c.hunger,
            })
    print(f"wrote embeddings {vecs.shape} and clips.csv ({len(clips)} rows)")

    import json
    (Path("outputs/artifacts/taxonomy5") / "data_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
