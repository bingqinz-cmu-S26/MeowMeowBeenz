#!/usr/bin/env python3
import argparse
import base64
import csv
import hashlib
import json
import os
import re
import string
import subprocess
import tempfile
import time
import urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


LABELS = ["chatter", "hiss", "chirrup", "nyaaan", "growl", "purr", "caterwaul", "meow"]
FOLDERS = {
    "chatter": "chatter嘎嘎 兴奋捕猎状态",
    "hiss": "hiss哈气 defense",
    "chirrup": "chirrup咕噜 交流",
    "nyaaan": "nyaaan打架 暴怒",
    "growl": "growl低吼 警告",
    "purr": "purr呼噜 舒适",
    "caterwaul": "caterwaul老吴 cat-mate",
    "meow": "meow喵 开心",
}
PROMPT = (
    "Listen to the cat audio and classify it as exactly one of: "
    + ", ".join(LABELS)
    + ". Return only the label."
)


def load_dotenv(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ffprobe_duration(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def infer_source(path):
    name = path.stem.lower()
    if "youtube" in name:
        return "youtube"
    if "recorded" in name:
        return "recorded"
    if "flickr" in name:
        return "flickr"
    if "coll" in name or "extcoll" in name:
        return "scraped_pack"
    if name.startswith("cat") or name.startswith("last_addcat"):
        return "scraped_pack"
    return "unknown"


def build_manifest(dataset_root, output):
    dataset_root = Path(dataset_root)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, folder_name in FOLDERS.items():
        folder = dataset_root / folder_name
        for path in sorted(folder.glob("*.mp3")):
            rel = path.as_posix()
            duration = ffprobe_duration(path)
            rows.append(
                {
                    "clip_id": hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12],
                    "audio_path": rel,
                    "filename": path.name,
                    "label": label,
                    "source_hint": infer_source(path),
                    "duration_seconds": f"{duration:.6f}",
                    "truncated": str(duration > 10).lower(),
                }
            )

    fields = ["clip_id", "audio_path", "filename", "label", "source_hint", "duration_seconds", "truncated"]
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output}")


def parse_label(raw):
    text = str(raw or "").strip().lower()
    text = text.translate(str.maketrans("", "", string.punctuation.replace("_", "")))
    exact = text.replace(" ", "_")
    if exact in LABELS:
        return exact, "exact"
    hits = []
    for label in LABELS:
        if re.search(rf"\b{re.escape(label)}\b", text) or label in text:
            hits.append(label)
    hits = sorted(set(hits))
    if len(hits) == 1:
        return hits[0], "contains"
    if len(hits) > 1:
        return "", "ambiguous"
    return "", "invalid"


def make_payload(row):
    audio = Path(row["audio_path"]).read_bytes()
    return {
        "clip_id": row["clip_id"],
        "audio_base64": base64.b64encode(audio).decode("ascii"),
        "audio_filename": row["filename"],
        "labels": LABELS,
        "prompt": PROMPT,
        "preprocessing": {"target_sample_rate_hz": 16000, "mono": True, "max_duration_seconds": 10},
        "generation": {"temperature": 0, "max_new_tokens": 16},
    }


def post_json(url, payload, api_key=None, timeout=900):
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_output(response):
    if "output" in response and isinstance(response["output"], dict):
        response = response["output"]
    for key in ("label", "text", "generated_text", "prediction", "raw_output"):
        if key in response:
            return response[key]
    return json.dumps(response, ensure_ascii=False)


def eval_endpoint(manifest, output, limit=None):
    load_dotenv()
    url = os.getenv("CAT_AUDIO_ENDPOINT_URL")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    api_key = os.getenv("RUNPOD_API_KEY")
    if endpoint_id:
        url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
    if not url:
        raise SystemExit("Set CAT_AUDIO_ENDPOINT_URL for a Pod proxy, or RUNPOD_ENDPOINT_ID for Serverless.")

    with open(manifest, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if limit:
        rows = rows[:limit]

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "clip_id",
        "audio_path",
        "gold_label",
        "source_hint",
        "duration_seconds",
        "truncated",
        "raw_output",
        "parsed_label",
        "parse_status",
        "correct",
        "latency_seconds",
        "error",
    ]
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, start=1):
            started = time.time()
            raw_output = ""
            parsed = ""
            status = "invalid"
            error = ""
            try:
                payload = make_payload(row)
                body = {"input": payload} if endpoint_id else payload
                response = post_json(url, body, api_key=api_key if endpoint_id else None)
                raw_output = extract_output(response)
                parsed, status = parse_label(raw_output)
            except Exception as exc:
                error = repr(exc)
            correct = parsed == row["label"]
            writer.writerow(
                {
                    "clip_id": row["clip_id"],
                    "audio_path": row["audio_path"],
                    "gold_label": row["label"],
                    "source_hint": row["source_hint"],
                    "duration_seconds": row["duration_seconds"],
                    "truncated": row["truncated"],
                    "raw_output": raw_output,
                    "parsed_label": parsed,
                    "parse_status": status,
                    "correct": str(correct).lower(),
                    "latency_seconds": f"{time.time() - started:.3f}",
                    "error": error,
                }
            )
            print(f"[{i}/{len(rows)}] {row['label']} -> {parsed or status} correct={correct}")
    print(f"Wrote {output}")


def compute_metrics(predictions, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(predictions, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    confusion = {gold: {pred: 0 for pred in LABELS + ["invalid"]} for gold in LABELS}
    for row in rows:
        gold = row["gold_label"]
        pred = row["parsed_label"] if row["parsed_label"] in LABELS else "invalid"
        confusion[gold][pred] += 1

    total = len(rows)
    correct = sum(row["correct"] == "true" for row in rows)
    per_class = {}
    f1_values = []
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[gold][label] for gold in LABELS if gold != label)
        fn = sum(v for pred, v in confusion[label].items() if pred != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        support = sum(confusion[label].values())
        per_class[label] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
        f1_values.append(f1)

    metrics = {
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "chance_baseline": 1 / len(LABELS),
        "macro_f1": sum(f1_values) / len(f1_values),
        "parse_status_counts": dict(Counter(row["parse_status"] for row in rows)),
        "per_class": per_class,
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    with (out_dir / "confusion_matrix.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["gold_label"] + LABELS + ["invalid"])
        for label in LABELS:
            writer.writerow([label] + [confusion[label][pred] for pred in LABELS + ["invalid"]])

    with (out_dir / "eval_report.md").open("w", encoding="utf-8") as f:
        f.write("# Cat Audio Eval Report\n\n")
        f.write(f"- Clips: {total}\n")
        f.write(f"- Accuracy: {metrics['accuracy']:.4f}\n")
        f.write(f"- Chance baseline: {metrics['chance_baseline']:.4f}\n")
        f.write(f"- Macro F1: {metrics['macro_f1']:.4f}\n\n")
        f.write("| Label | Support | Precision | Recall | F1 |\n")
        f.write("|---|---:|---:|---:|---:|\n")
        for label, item in per_class.items():
            f.write(f"| {label} | {item['support']} | {item['precision']:.4f} | {item['recall']:.4f} | {item['f1']:.4f} |\n")
    print(f"Wrote metrics to {out_dir}")


def server():
    import librosa  # noqa: F401  (used for mp3 decode in do_POST)
    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor

    model_path = os.getenv("MEOW_OMNI_MODEL_PATH", "/workspace/Meow-Omni-1-weights")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    state = {"model": None, "processor": None}

    def load_model():
        if state["model"] is None:
            print(f"Loading model from {model_path}", flush=True)
            state["processor"] = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            state["model"] = AutoModelForCausalLM.from_pretrained(
                model_path, trust_remote_code=True, torch_dtype=torch.bfloat16
            ).to("cuda").eval()
            print("Model loaded", flush=True)

    def classify(audio, prompt):
        # Verified call shape from the repo's src/evaluation/eval_meow.py:
        # build a prompt with the literal <audio>./</audio> placeholder, run it
        # through the processor, then model.generate with the custom tokenizer= kwarg.
        proc = state["processor"]
        injected = "\n".join(["<audio>./</audio>", prompt])
        text = f"User: {injected}\nAssistant:"
        enc = proc(text=[text], audios=[audio], return_tensors="pt").to("cuda")
        input_len = enc["input_ids"].shape[1]
        gen_kwargs = {
            "input_ids": enc["input_ids"],
            "attention_mask": enc.get("attention_mask"),
            "tokenizer": proc.tokenizer,  # non-standard kwarg required by MiniCPM-o generate
            "max_new_tokens": 16,
            "do_sample": False,  # temperature-0 greedy
        }
        for k in ["audio_features", "audio_feature_lens", "audio_bounds"]:
            if k in enc:
                gen_kwargs[k] = enc[k]
        output = state["model"].generate(**gen_kwargs)
        # Robust decode: generate may return a string, a tensor, or an object with
        # .sequences; in the token cases strip the echoed prompt before decoding.
        if isinstance(output, str):
            decoded = output
        else:
            if isinstance(output, (list, tuple)):
                output = output[0]
            seq = output.sequences[0] if hasattr(output, "sequences") else output[0]
            if hasattr(seq, "shape") and seq.shape[0] > input_len:
                seq = seq[input_len:]
            decoded = proc.tokenizer.decode(seq, skip_special_tokens=True)
        if "Assistant:" in decoded:
            decoded = decoded.split("Assistant:")[-1]
        return decoded.strip()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.write_json({"ok": True, "model_loaded": state["model"] is not None})

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                load_model()
                audio_bytes = base64.b64decode(payload["audio_base64"])
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as tmp:
                    tmp.write(audio_bytes)
                    tmp.flush()
                    audio, _ = librosa.load(tmp.name, sr=16000, mono=True)
                max_samples = 16000 * 10
                if len(audio) > max_samples:
                    audio = audio[:max_samples]
                raw = classify(audio, payload.get("prompt", PROMPT))
                label, _ = parse_label(raw)
                self.write_json({"label": label, "text": raw})
            except Exception as exc:
                self.write_json({"label": "", "text": "", "error": repr(exc)}, status=500)

        def write_json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = HTTPServer((host, port), Handler)
    print(f"Serving on http://{host}:{port}", flush=True)
    httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("manifest")
    p.add_argument("--dataset-root", default="data/猫子语料")
    p.add_argument("--output", default="outputs/artifacts/manifest.csv")

    p = sub.add_parser("eval")
    p.add_argument("--manifest", default="outputs/artifacts/manifest.csv")
    p.add_argument("--output", default="outputs/artifacts/predictions.csv")
    p.add_argument("--limit", type=int)

    p = sub.add_parser("metrics")
    p.add_argument("--predictions", default="outputs/artifacts/predictions.csv")
    p.add_argument("--out-dir", default="outputs/artifacts")

    sub.add_parser("server")
    args = parser.parse_args()

    if args.cmd == "manifest":
        build_manifest(args.dataset_root, args.output)
    elif args.cmd == "eval":
        eval_endpoint(args.manifest, args.output, args.limit)
    elif args.cmd == "metrics":
        compute_metrics(args.predictions, args.out_dir)
    elif args.cmd == "server":
        server()


if __name__ == "__main__":
    main()
