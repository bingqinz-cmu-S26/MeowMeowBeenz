"""Create cached AST embeddings for probe datasets."""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np

import librosa

from probe_registry import PROBE_DATASETS, ProbeDataset, DATASET_BY_ID, enrich_rows_with_group_and_source, iter_rows


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["all"] + [cfg.dataset_id for cfg in PROBE_DATASETS], default="all")
    parser.add_argument("--out-dir", default="outputs/artifacts/probe/_emb")
    parser.add_argument("--cache-dir", default="outputs/artifacts/encoder-probe/_cache")
    parser.add_argument("--embedding-mode", default="mean", choices=["mean", "cls"])
    parser.add_argument("--model-name", default="MIT/ast-finetuned-audioset-10-10-0.4593")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--trim-top-db", type=float, default=30.0)
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="Recompute embeddings even if cached array matches.")
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def _select_datasets(dataset_id: str) -> List[ProbeDataset]:
    if dataset_id == "all":
        return PROBE_DATASETS
    return [DATASET_BY_ID[dataset_id]]


def _load_reference_paths(dataset_id: str) -> Tuple[List[str], Path]:
    candidates = [
        Path("outputs/artifacts/encoder-probe") / dataset_id / "ast_probe_predictions.csv",
        Path("outputs/artifacts/encoder-probe") / dataset_id / "ast_probe_hunger_predictions.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        rows: List[str] = []
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                item = row.get("path") or row.get("audio_path") or row.get("clip_path")
                if item:
                    rows.append(item)
        if rows:
            return rows, path
    return [], Path()


def _matching_cache(cfg: ProbeDataset, rows: List[dict], cache_path: Path) -> bool:
    if not cache_path.exists():
        return False
    reference_paths, source_file = _load_reference_paths(cfg.dataset_id)
    if not reference_paths:
        print(f"skip cache reuse for {cfg.dataset_id}: no reference manifest from encoder-probe run.")
        return False
    current_paths = [row["path"] for row in rows]
    if len(reference_paths) != len(current_paths):
        print(
            f"skip cache reuse for {cfg.dataset_id}: size mismatch "
            f"(reference={len(reference_paths)} current={len(current_paths)} via {source_file})."
        )
        return False
    if reference_paths != current_paths:
        print(f"skip cache reuse for {cfg.dataset_id}: path order mismatch vs {source_file}.")
        return False
    cached = np.load(cache_path)
    if cached.shape[0] != len(current_paths):
        print(
            f"skip cache reuse for {cfg.dataset_id}: embedding array rows {cached.shape[0]} != {len(current_paths)}."
        )
        return False
    return True


def _extract_embedding(feature_extractor, model, audio: np.ndarray, mode: str, sample_rate: int):
    import torch

    inputs = feature_extractor(
        audio,
        sampling_rate=sample_rate,
        return_tensors="pt",
        return_attention_mask=True,
    )
    audio_inputs = {k: v for k, v in inputs.items() if hasattr(v, "to")}
    device = next(model.parameters()).device
    for key in list(audio_inputs):
        audio_inputs[key] = audio_inputs[key].to(device)

    with torch.no_grad():
        outputs = model(**audio_inputs)
    hidden = outputs.last_hidden_state
    if hidden.ndim != 3:
        raise RuntimeError(f"Unexpected AST hidden shape: {tuple(hidden.shape)}")

    if mode == "cls":
        pooled = hidden[:, 0, :]
    else:
        if "attention_mask" not in audio_inputs:
            pooled = hidden.mean(dim=1)
        else:
            mask = audio_inputs["attention_mask"].to(hidden.dtype)
            denom = mask.sum(dim=1).clamp_min(1.0).unsqueeze(-1)
            pooled = (hidden * mask.unsqueeze(-1)).sum(dim=1) / denom
    return pooled.squeeze(0).detach().cpu().numpy()


def _load_audio(path: str, sample_rate: int, trim_top_db: float) -> np.ndarray:
    audio_full, _ = librosa.load(path, sr=sample_rate, mono=True)
    trimmed, _ = librosa.effects.trim(audio_full.astype(np.float32), top_db=trim_top_db)
    if len(trimmed) == 0:
        trimmed = audio_full
    return trimmed.astype(np.float32)


@dataclass
class EmbeddingModel:
    model_name: str
    device: str
    embedding_mode: str
    sample_rate: int

    def __post_init__(self):
        import torch
        from transformers import ASTModel, AutoFeatureExtractor

        self.device_obj = torch.device(self.device if torch.cuda.is_available() or self.device != "cuda" else "cpu")
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(self.model_name)
        self.model = ASTModel.from_pretrained(self.model_name).to(self.device_obj).eval()

    def embed(self, path: str, trim_top_db: float) -> np.ndarray:
        audio = _load_audio(path, self.sample_rate, trim_top_db)
        return _extract_embedding(self.feature_extractor, self.model, audio, self.embedding_mode, self.sample_rate)


def run_dataset(cfg: ProbeDataset, args):
    rows = iter_rows(cfg)
    rows = rows[: args.max_items] if args.max_items else rows
    rows = enrich_rows_with_group_and_source(rows, cfg)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_npy = out_dir / f"{cfg.dataset_id}.npy"
    out_meta = out_dir / f"{cfg.dataset_id}_meta.csv"
    cache_npy = Path(args.cache_dir) / f"{cfg.dataset_id}_ast.npy"

    if not rows:
        print(f"{cfg.dataset_id}: no clips found, skipping.")
        return

    if not args.force and _matching_cache(cfg, rows, cache_npy):
        emb = np.load(cache_npy)
        print(f"{cfg.dataset_id}: reusing {cache_npy} (ordering verified).")
        np.save(out_npy, emb)
    else:
        print(f"{cfg.dataset_id}: computing {len(rows)} embeddings with {args.model_name} ({args.embedding_mode}).")
        model = EmbeddingModel(args.model_name, args.device, args.embedding_mode, args.sample_rate)
        vectors = []
        for i, row in enumerate(rows, 1):
            vector = model.embed(row["path"], args.trim_top_db)
            vectors.append(vector)
            if i % 25 == 0 or i == len(rows):
                print(f"{cfg.dataset_id}: {i}/{len(rows)}")
        emb = np.stack(vectors, axis=0).astype(np.float32)
        np.save(out_npy, emb)

    with out_meta.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["clip_path", "label", "group_key", "source_hint"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "clip_path": row["path"],
                    "label": row["label"],
                    "group_key": row["group_key"],
                    "source_hint": row["source_hint"],
                }
            )

    print(f"{cfg.dataset_id}: wrote {out_npy} and {out_meta}")


def main():
    args = parse_args()
    for cfg in _select_datasets(args.dataset):
        run_dataset(cfg, args)


if __name__ == "__main__":
    if not os.environ.get("AST_EMBED_DISABLE_HEALTHCHECK"):
        for dep in ("librosa",):
            __import__(dep)
    main()
