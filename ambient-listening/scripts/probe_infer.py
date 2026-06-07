"""Run saved probe models on one audio clip."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import librosa


class _IdentityScaler:
    def transform(self, x):
        return x


@dataclass
class ProbeHead:
    name: str
    model: any
    scaler: any
    labels: list[str]

    def predict(self, embedding: np.ndarray) -> Dict[str, object]:
        x = self.scaler.transform(embedding.reshape(1, -1))
        proba = self.model.predict_proba(x)[0]
        labels = list(self.model.classes_)
        if labels != self.labels:
            index_by_label = {label: idx for idx, label in enumerate(labels)}
            ordered = np.asarray([proba[index_by_label[label]] for label in self.labels], dtype=float)
        else:
            ordered = proba
        pred_idx = int(np.argmax(ordered))
        pred_label = self.labels[pred_idx]
        conf = float(ordered[pred_idx])
        return {
            "label": pred_label,
            "confidence": conf,
            "proba_dict": {lab: float(prob) for lab, prob in zip(self.labels, ordered)},
        }


@dataclass
class ProbeEngine:
    probe_root: Path
    model_name: str
    device: str = "cpu"
    embedding_mode: str = "mean"
    selected: Optional[set[str]] = None
    heads: Dict[str, ProbeHead] = None

    def __post_init__(self):
        self.probe_root = Path(self.probe_root)
        self.model = None
        self.feature_extractor = None
        self.heads = {}
        self._load_heads(self.selected)
        self._load_ast_model()

    def _load_heads(self, selected: Optional[set[str]] = None):
        for head_dir in sorted(self.probe_root.iterdir()):
            if not head_dir.is_dir():
                continue
            if selected and head_dir.name not in selected:
                continue
            bundle_path = head_dir / "probe.joblib"
            labels_path = head_dir / "label_names.json"
            if not bundle_path.exists() or not labels_path.exists():
                print(f"skip {head_dir.name}: missing probe.joblib or label_names.json")
                continue
            bundle = joblib.load(bundle_path)
            if isinstance(bundle, dict) and "scaler" in bundle and "model" in bundle:
                scaler = bundle["scaler"]
                model = bundle["model"]
            else:
                model = bundle
                scaler = None
            labels = json.loads(labels_path.read_text(encoding="utf-8")).get("label_names")
            if labels is None:
                labels = list(getattr(model, "classes_", []))
            if scaler is None:
                # fallback for older pickles saved as pipeline objects
                if hasattr(model, "transform") and hasattr(model, "predict_proba"):
                    scaler = _IdentityScaler()
                else:
                    raise ValueError(f"{head_dir}: unsupported probe format in {bundle_path}")
            self.heads[head_dir.name] = ProbeHead(name=head_dir.name, model=model, scaler=scaler, labels=labels)

    def _load_ast_model(self):
        import torch
        from transformers import ASTModel, AutoFeatureExtractor

        device = torch.device(self.device if torch.cuda.is_available() or self.device != "cuda" else "cpu")
        self.model = ASTModel.from_pretrained(self.model_name).to(device).eval()
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(self.model_name)
        self.torch_device = device

    def _embed(self, path: str, sample_rate: int = 16000, trim_top_db: float = 30.0) -> np.ndarray:
        import torch

        audio, _ = librosa.load(path, sr=sample_rate, mono=True)
        trimmed, _ = librosa.effects.trim(audio.astype(np.float32), top_db=trim_top_db)
        if len(trimmed) == 0:
            trimmed = audio
        inputs = self.feature_extractor(
            trimmed.astype(np.float32),
            sampling_rate=sample_rate,
            return_tensors="pt",
            return_attention_mask=True,
        )
        for k in list(inputs):
            if hasattr(inputs[k], "to"):
                inputs[k] = inputs[k].to(self.torch_device)

        with torch.no_grad():
            hidden = self.model(**inputs).last_hidden_state
        if self.embedding_mode == "cls":
            emb = hidden[:, 0, :]
        else:
            if "attention_mask" in inputs:
                mask = inputs["attention_mask"].to(hidden.dtype)
                denom = mask.sum(dim=1).clamp_min(1.0).unsqueeze(-1)
                emb = (hidden * mask.unsqueeze(-1)).sum(dim=1) / denom
            else:
                emb = hidden.mean(dim=1)
        return emb.detach().cpu().numpy().astype(np.float32).reshape(-1)

    def classify(self, audio_path: str, selected: Optional[set[str]] = None) -> Dict[str, object]:
        emb = self._embed(audio_path)
        result: Dict[str, object] = {}
        for head_name, head in self.heads.items():
            if selected and head_name not in selected:
                continue
            result[head_name] = head.predict(emb)
        return result


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio_path")
    ap.add_argument("--probe-root", default="outputs/artifacts/probe")
    ap.add_argument("--model", default="MIT/ast-finetuned-audioset-10-10-0.4593")
    ap.add_argument("--head", action="append", help="Limit output to one or more heads (defaults to all).")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--embedding-mode", default="mean", choices=["mean", "cls"])
    return ap.parse_args()


def classify(
    audio_path: str,
    probe_root: str = "outputs/artifacts/probe",
    model_name: str = "MIT/ast-finetuned-audioset-10-10-0.4593",
    head: Optional[list[str]] = None,
    device: str = "cpu",
    embedding_mode: str = "mean",
) -> Dict[str, object]:
    selected = set(head) if head else None
    engine = ProbeEngine(
        probe_root=Path(probe_root),
        model_name=model_name,
        device=device,
        embedding_mode=embedding_mode,
        selected=selected,
    )
    return engine.classify(audio_path, selected=selected)


def main():
    args = parse_args()
    selected = set(args.head) if args.head else None
    engine = ProbeEngine(
        probe_root=Path(args.probe_root),
        model_name=args.model,
        device=args.device,
        embedding_mode=args.embedding_mode,
        selected=selected,
    )
    result = engine.classify(args.audio_path, selected=selected)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
