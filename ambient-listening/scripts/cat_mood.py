"""Cat-mood perception layer: audio clip -> 5-class mood + confidence.

Uses the frozen AST encoder + the trained 5-class logistic-regression probe
(outputs/artifacts/taxonomy5/probe/cat_mood_probe.joblib).

CLI:    .venv/bin/python scripts/cat_mood.py path/to/clip.wav
Import: from cat_mood import CatMood;  CatMood().classify("clip.wav")
"""
import sys, json
from pathlib import Path
import numpy as np
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ast_embed import EmbeddingModel  # exact same embedding recipe used in training

REPO = Path(__file__).resolve().parent.parent
PROBE_PATH = REPO / "outputs/artifacts/taxonomy5/probe/cat_mood_probe.joblib"


class CatMood:
    def __init__(self, probe_path=PROBE_PATH, device="cpu"):
        b = joblib.load(probe_path)
        self.scaler, self.clf, self.classes = b["scaler"], b["clf"], b["classes"]
        self.encoder = EmbeddingModel(b["ast_model"], device, b["pool"], b["sr"])
        self.trim_top_db = b["trim_top_db"]

    def classify(self, audio_path):
        emb = self.encoder.embed(str(audio_path), self.trim_top_db).reshape(1, -1)
        proba = self.clf.predict_proba(self.scaler.transform(emb))[0]
        order = np.argsort(proba)[::-1]
        ranked = {str(self.clf.classes_[i]): round(float(proba[i]), 3) for i in order}
        top = str(self.clf.classes_[order[0]])
        return {"mood": top, "confidence": round(float(proba[order[0]]), 3), "scores": ranked}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: cat_mood.py <audio_clip>"); sys.exit(1)
    print(json.dumps(CatMood().classify(sys.argv[1]), indent=2))
