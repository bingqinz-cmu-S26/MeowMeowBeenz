"""Part B: zero-shot Gemini 5-way MCQ on the unified taxonomy, on a seeded stratified subsample.

Reuses GeminiProvider (429 backoff), audio prep, and the extract_answer machinery conventions
from scripts/frontier_classify.py / frontier_providers.py.

Subsample: seeded stratified, capped at --cap clips/bucket (default 150) ~= 750 total.
Writes outputs/artifacts/taxonomy5/gemini-3.5-flash/predictions.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from taxonomy5 import build_clips, BUCKETS, BUCKET_DEFS  # noqa: E402
from frontier_providers import PROVIDERS  # noqa: E402

OUT_DIR = Path("outputs/artifacts/taxonomy5/gemini-3.5-flash")
SR = 16000
TRIM_TOP_DB = 30
SEED = 13


def load_audio_wav_bytes(path, sample_rate=SR):
    import librosa
    import numpy as np
    import soundfile as sf

    audio_full = librosa.load(path, sr=sample_rate, mono=True)[0].astype(np.float32)
    trimmed, _ = librosa.effects.trim(audio_full, top_db=TRIM_TOP_DB)
    if len(trimmed) == 0:
        trimmed = audio_full
    audio = trimmed[: sample_rate * 30]
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def build_prompt(clip_path, shuffle_index):
    rnd = random.Random(f"taxo5:{Path(clip_path).as_posix()}:{shuffle_index}")
    labels = list(BUCKETS)
    rnd.shuffle(labels)
    letters = [chr(ord("A") + i) for i in range(len(labels))]
    lines = [
        "You are an expert in cat vocalizations. Listen to the audio clip and choose the single option that best matches the cat's state.",
    ]
    lines += [f"{ltr}) {lab} - {BUCKET_DEFS[lab]}" for ltr, lab in zip(letters, labels)]
    lines.append("First briefly describe the sound in one sentence, then on a new line write \"Answer: X\" (one letter).")
    return "\n".join(lines), labels


def extract_answer(raw, option_labels):
    text = str(raw or "").strip()
    valid = "".join(chr(ord("A") + i) for i in range(len(option_labels)))
    m = re.search(rf"answer\s*:\s*([{valid}])\b", text, flags=re.IGNORECASE)
    if m:
        ltr = m.group(1).upper()
        return option_labels[ord(ltr) - ord("A")], ltr, "answer_tag"
    m = re.search(rf"(?<![A-Za-z])([{valid}])(?![A-Za-z])", text, flags=re.IGNORECASE)
    if m:
        ltr = m.group(1).upper()
        return option_labels[ord(ltr) - ord("A")], ltr, "letter"
    lowered = text.lower()
    hits = [lab for lab in option_labels if lab.lower() in lowered]
    if len(hits) == 1:
        lab = hits[0]
        return lab, chr(ord("A") + option_labels.index(lab)), "content"
    return "", "", "none"


def stratified_subsample(clips, cap, seed=SEED):
    by_bucket = defaultdict(list)
    for c in clips:
        by_bucket[c.bucket].append(c)
    rnd = random.Random(seed)
    out = []
    for b in BUCKETS:
        pool = sorted(by_bucket[b], key=lambda c: c.clip_path)
        rnd.shuffle(pool)
        out.extend(pool[:cap])
    return sorted(out, key=lambda c: c.clip_path)


def parse_retry_delay(text):
    text = str(text or "")
    m = re.search(r"retry_after=([0-9.]+)s?", text, flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?([0-9.]+)s", text, flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 0.0


def call_with_backoff(provider, wav_bytes, prompt, retries, rpm):
    interval = 60.0 / rpm if rpm else 0.0
    last = None
    for attempt in range(retries + 1):
        try:
            if interval:
                time.sleep(interval)
            return provider.classify(wav_bytes, SR, prompt)
        except Exception as exc:
            last = exc
            if attempt < retries:
                rd = parse_retry_delay(str(exc))
                backoff = rd if rd else min(60, 2 ** attempt)
                time.sleep(max(1.0, backoff))
    return {"raw": "", "usage": {}, "latency_s": 0.0, "error": str(last)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=150, help="max clips per bucket")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--smoke", type=int, default=0, help="N clips/bucket smoke run")
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("--rate-limit-rpm", type=int, default=24, help="throttle to stay under free-tier limits")
    ap.add_argument("--provider", default="gemini-3.5-flash")
    args = ap.parse_args()

    provider = PROVIDERS[args.provider]
    clips, _ = build_clips(verbose=False)

    if args.smoke:
        subset = stratified_subsample(clips, args.smoke)
        out_csv = OUT_DIR / "smoke_predictions.csv"
    else:
        subset = stratified_subsample(clips, args.cap)
        out_csv = OUT_DIR / "predictions.csv"

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        from collections import Counter
        bd = Counter(c.bucket for c in subset)
        print(f"DRY RUN: provider={provider.name} model={provider.model}")
        print(f"subsample N={len(subset)} per-bucket={dict(bd)}")
        # Gemini flash audio: ~30s clip ~= a few hundred audio tokens + ~250 prompt + ~80 output.
        # price_per_1m_input={provider.price_per_1m_input_tokens} output={provider.price_per_1m_output_tokens}
        est_in = 600  # tokens/call rough (audio+text prompt)
        est_out = 90
        per_call = (est_in * provider.price_per_1m_input_tokens + est_out * provider.price_per_1m_output_tokens) / 1_000_000
        print(f"rough est input~{est_in}tok output~{est_out}tok/call -> ${per_call:.5f}/call -> total ~${per_call*len(subset):.4f}")
        print(f"rate_limit={args.rate_limit_rpm} rpm -> ~{len(subset)/args.rate_limit_rpm:.1f} min wall-clock")
        return

    # resumable cache
    cache_path = OUT_DIR / "cache.jsonl"
    cache = {}
    if cache_path.exists():
        for line in open(cache_path, encoding="utf-8"):
            try:
                it = json.loads(line)
                cache[it["key"]] = it["result"]
            except Exception:
                pass

    fields = ["clip_path", "dataset_id", "native_label", "gold_label", "pred_label", "pred_letter",
              "correct", "parse_status", "group_key", "source_hint", "hunger", "option_order",
              "raw_output", "cost_usd", "usage", "latency_s", "error"]
    rows = []
    total_cost = 0.0
    started = time.perf_counter()
    for i, c in enumerate(subset, 1):
        prompt, option_order = build_prompt(c.clip_path, 0)
        key = f"{provider.name}:{Path(c.clip_path).as_posix()}"
        if key in cache and not cache[key].get("error"):
            result = cache[key]
        else:
            wav = load_audio_wav_bytes(c.clip_path)
            result = call_with_backoff(provider, wav, prompt, args.retries, args.rate_limit_rpm)
            with cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "result": result}, ensure_ascii=False) + "\n")
            cache[key] = result
        raw = result.get("raw") or ""
        if result.get("error"):
            pred, letter, status = "", "", "error"
        else:
            pred, letter, status = extract_answer(raw, option_order)
        usage = result.get("usage") or {}
        cost = provider.estimate_cost(usage)
        total_cost += cost
        rows.append({
            "clip_path": c.clip_path, "dataset_id": c.dataset_id, "native_label": c.native_label,
            "gold_label": c.bucket, "pred_label": pred, "pred_letter": letter,
            "correct": str(pred == c.bucket).lower(), "parse_status": status,
            "group_key": c.group_key, "source_hint": c.source_hint, "hunger": c.hunger,
            "option_order": json.dumps(option_order), "raw_output": raw,
            "cost_usd": f"{cost:.8f}", "usage": json.dumps(usage), "latency_s": result.get("latency_s", 0.0),
            "error": result.get("error", ""),
        })
        if i % 10 == 0 or i == len(subset):
            print(f"[{i}/{len(subset)}] {c.bucket} -> {pred or 'none'} ({status}) cost=${total_cost:.4f}", flush=True)

    rows.sort(key=lambda r: r["clip_path"])
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    (OUT_DIR / "run_summary.json").write_text(json.dumps({
        "provider": provider.name, "model": provider.model, "n": len(rows),
        "total_cost_usd": round(total_cost, 6),
        "wall_clock_s": round(time.perf_counter() - started, 1),
    }, indent=2), encoding="utf-8")
    print(f"wrote {out_csv} | N={len(rows)} total_cost=${total_cost:.4f}")


if __name__ == "__main__":
    main()
