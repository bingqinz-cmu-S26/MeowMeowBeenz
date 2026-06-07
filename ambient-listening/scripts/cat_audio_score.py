"""
Forced-label-likelihood evaluation of Meow-Omni-1 on the 8-class cat-audio set.

The model describes audio rather than emitting labels, so instead of generating we
SCORE each of the 8 label strings as the continuation of an audio-conditioned
prompt and take the argmax of the length-normalized log-prob. This sidesteps the
description bias and the rare-token (nyaaan/chirrup/caterwaul) confound.

Run on the pod from /workspace:
    python scripts/cat_audio_score.py --per-class 0   # 0 = all 40/class; e.g. 3 for a quick check
"""
import argparse, csv, glob, json, os, sys
import numpy as np, librosa, torch

sys.path.insert(0, "/workspace/Meow-Omni-1")
from src.modeling_meow_omni_1 import MeowOmni1ForCausalLM
from src.processing_meow_omni_1 import MeowOmni1Processor

WEIGHTS = "/workspace/Meow-Omni-1-weights"
LABELS = ["chatter", "hiss", "chirrup", "nyaaan", "growl", "purr", "caterwaul", "meow"]
FOLDERS = {
    "chatter": "chatter嘎嘎 兴奋捕猎状态", "hiss": "hiss哈气 defense",
    "chirrup": "chirrup咕噜 交流", "nyaaan": "nyaaan打架 暴怒",
    "growl": "growl低吼 警告", "purr": "purr呼噜 舒适",
    "caterwaul": "caterwaul老吴 cat-mate", "meow": "meow喵 开心",
}
QUESTION = "What kind of sound is this cat making? Answer with one word."


def infer_source(name):
    n = name.lower()
    for k in ("youtube", "recorded", "flickr"):
        if k in n:
            return k
    if "coll" in n or n.startswith("cat") or n.startswith("last_add"):
        return "scraped_pack"
    return "unknown"


def to_dev(x, d="cuda"):
    if isinstance(x, torch.Tensor): return x.to(d)
    if isinstance(x, dict): return {k: to_dev(v, d) for k, v in x.items()}
    if isinstance(x, list): return [to_dev(v, d) for v in x]
    return x


def build_context(proc, audio):
    injected = "\n".join(["<audio>./</audio>", QUESTION])
    text = f"User: {injected}\nAssistant:"
    enc = proc(text=[text], images=None, audios=[audio], time_series_paths=None,
               time_series_sampling_rates=None, ids=["s"], return_tensors="pt")
    enc = dict(enc.data) if hasattr(enc, "data") else dict(enc.items())
    enc = to_dev(enc)
    bs = enc["input_ids"].shape[0]
    if enc.get("image_bound") is None:
        enc["image_bound"] = torch.zeros(bs, 0, 2, dtype=torch.long, device="cuda")
    return enc


@torch.no_grad()
def score_labels(model, proc, ctx, label_token_ids):
    """Return length-normalized logprob for each label given the audio context."""
    tok = proc.tokenizer
    ctx_ids = ctx["input_ids"]
    ctx_len = ctx_ids.shape[1]
    scores = []
    for lab_ids in label_token_ids:
        lab = torch.tensor([lab_ids], device="cuda")
        full = torch.cat([ctx_ids, lab], dim=1)
        data = dict(ctx)
        data["input_ids"] = full
        data["attention_mask"] = torch.ones_like(full)
        out = model(data=data)
        logits = out.logits if hasattr(out, "logits") else out[0]
        logp = torch.log_softmax(logits.float(), dim=-1)
        total = 0.0
        for j, tid in enumerate(lab_ids):
            total += logp[0, ctx_len - 1 + j, tid].item()
        scores.append(total / max(1, len(lab_ids)))
    return scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=0, help="clips per class; 0=all")
    ap.add_argument("--out", default="/workspace/predictions.csv")
    args = ap.parse_args()

    proc = MeowOmni1Processor.from_pretrained(WEIGHTS, trust_remote_code=True)
    model = MeowOmni1ForCausalLM.from_pretrained(
        WEIGHTS, trust_remote_code=True, torch_dtype=torch.bfloat16).to("cuda").eval()
    tok = proc.tokenizer
    label_token_ids = [tok(" " + l, add_special_tokens=False).input_ids for l in LABELS]
    print("label token lengths:", {l: len(ids) for l, ids in zip(LABELS, label_token_ids)}, flush=True)

    # Contextual-calibration baseline: score labels against 1s of SILENCE so we can
    # subtract each label's intrinsic prior (surface-form competition fix).
    prior_ctx = build_context(proc, np.zeros(16000, dtype=np.float32))
    prior = np.array(score_labels(model, proc, prior_ctx, label_token_ids))
    print("silence prior:", {l: round(float(p), 3) for l, p in zip(LABELS, prior)}, flush=True)

    rows = []
    for gold, folder in FOLDERS.items():
        clips = sorted(glob.glob(f"data/猫子语料/{folder}/*.mp3"))
        if args.per_class:
            clips = clips[: args.per_class]
        for path in clips:
            audio_full = librosa.load(path, sr=16000, mono=True)[0].astype(np.float32)
            dur = len(audio_full) / 16000.0
            audio = audio_full[:480000]
            ctx = build_context(proc, audio)
            sc = np.array(score_labels(model, proc, ctx, label_token_ids))
            cal = sc - prior  # calibrated: how much THIS audio raises each label vs silence
            pred = LABELS[int(np.argmax(cal))]
            pred_raw = LABELS[int(np.argmax(sc))]
            rows.append({
                "audio_path": path, "filename": os.path.basename(path), "gold_label": gold,
                "pred_label": pred, "pred_raw": pred_raw, "correct": str(pred == gold).lower(),
                "source_hint": infer_source(os.path.basename(path)),
                "duration_s": f"{dur:.2f}", "truncated": str(dur > 30).lower(),
                "scores": json.dumps({l: round(float(s), 3) for l, s in zip(LABELS, sc)}),
                "calibrated": json.dumps({l: round(float(c), 3) for l, c in zip(LABELS, cal)}),
            })
            print(f"{gold:>10} | {os.path.basename(path):<28} -> cal={pred:<10} raw={pred_raw:<10} {'OK' if pred==gold else 'x'}", flush=True)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    n = len(rows); acc = sum(r["correct"] == "true" for r in rows) / n
    conf = {g: {p: 0 for p in LABELS} for g in LABELS}
    for r in rows: conf[r["gold_label"]][r["pred_label"]] += 1
    print(f"\n==== N={n}  accuracy={acc:.3f}  (chance=0.125) ====")
    print("per-class recall:")
    for g in LABELS:
        tot = sum(conf[g].values()); tp = conf[g][g]
        print(f"  {g:>10}: {tp}/{tot} = {tp/tot:.2f}" if tot else f"  {g}: n/a")
    print("\nconfusion (rows=gold, cols=pred):")
    print("gold\\pred  " + " ".join(f"{l[:4]:>5}" for l in LABELS))
    for g in LABELS:
        print(f"{g:>10} " + " ".join(f"{conf[g][p]:>5}" for p in LABELS))
    print(f"\nwrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
