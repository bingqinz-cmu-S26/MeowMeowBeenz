"""Run frontier-model direct audio classification over local cat-audio datasets."""
import argparse
import asyncio
import csv
import hashlib
import io
import json
import re
import time
from collections import Counter
from pathlib import Path

from cat_audio_datasets import (
    DATASET_BY_ID,
    DATASETS,
    build_prompt,
    cat_id,
    extract_answer,
    extract_confidence,
    infer_source,
    iter_clips,
    stratified_sample,
)
from frontier_summary import build_summary
from frontier_providers import PROVIDERS
from metrics_report import compute as compute_metrics

MAX_SAMPLES = 480000
TRIM_TOP_DB = 30
SAMPLE_RATE = 16000


class AsyncRateLimiter:
    def __init__(self, requests_per_minute=0):
        self.requests_per_minute = requests_per_minute
        self.interval_s = 60.0 / requests_per_minute if requests_per_minute else 0.0
        self.lock = asyncio.Lock()
        self.next_at = 0.0

    async def wait(self):
        if not self.interval_s:
            return
        async with self.lock:
            now = time.monotonic()
            if self.next_at > now:
                await asyncio.sleep(self.next_at - now)
                now = time.monotonic()
            self.next_at = now + self.interval_s


def parse_dataset_samples(raw):
    out = {}
    for item in raw or []:
        if "=" not in item:
            raise SystemExit(f"Invalid --dataset-sample {item!r}; expected dataset_id=N")
        dataset_id, value = item.split("=", 1)
        try:
            out[dataset_id] = int(value)
        except ValueError as exc:
            raise SystemExit(f"Invalid --dataset-sample {item!r}; N must be an integer") from exc
    return out


def sample_size_for(cfg, args):
    return args.dataset_samples.get(cfg["id"], args.sample_per_dataset)


def parse_retry_delay(error_text):
    text = str(error_text or "")
    patterns = [
        (r"retry_after=([0-9.]+)s?", 1.0),
        (r"retryDelay['\"]?\s*[:=]\s*['\"]?([0-9.]+)s", 1.0),
        (r"Please try again in ([0-9.]+)s", 1.0),
        (r"Please try again in ([0-9.]+)ms", 0.001),
    ]
    for pattern, scale in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        return float(match.group(1)) * scale
    return 0.0


def is_retryable_error(error_text):
    text = str(error_text or "").lower()
    return any(marker in text for marker in ["429", "rate_limit", "rate limit", "retry_after", "retrydelay", " 500", " 502", " 503", " 504"])


def should_use_cached_result(cached, retry_cached_errors=True):
    if not cached:
        return False
    result = cached.get("result") or {}
    if retry_cached_errors and result.get("error") and is_retryable_error(result.get("error")):
        return False
    return True


def load_audio_wav_bytes(path, sample_rate=SAMPLE_RATE):
    import librosa
    import numpy as np
    import soundfile as sf

    audio_full = librosa.load(path, sr=sample_rate, mono=True)[0].astype(np.float32)
    original_duration_s = len(audio_full) / sample_rate
    trimmed, _ = librosa.effects.trim(audio_full, top_db=TRIM_TOP_DB)
    if len(trimmed) == 0:
        trimmed = audio_full
    trimmed_duration_s = len(trimmed) / sample_rate
    max_samples = int(sample_rate * 30)
    truncated = len(trimmed) > max_samples
    audio = trimmed[:max_samples]
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue(), original_duration_s, trimmed_duration_s, truncated


def vote_trials(trials, classes):
    counts = Counter(t["pred_label"] for t in trials if t.get("pred_label"))
    if not counts:
        return "", "", 0.0, {}
    class_rank = {label: i for i, label in enumerate(classes)}
    winner, votes = sorted(counts.items(), key=lambda kv: (-kv[1], class_rank.get(kv[0], 999), kv[0]))[0]
    winner_letter = next((t["pred_letter"] for t in trials if t["pred_label"] == winner), "")
    return winner, winner_letter, votes / len(trials), dict(counts)


def cache_key(provider, model, clip_path, prompt, shuffle_index):
    raw = f"{provider}:{model}:{Path(clip_path).as_posix()}:{hashlib.sha1(prompt.encode('utf-8')).hexdigest()}:{shuffle_index}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class JsonlCache:
    def __init__(self, path):
        self.path = Path(path)
        self.items = {}
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.items[item["key"]] = item

    def get(self, key):
        return self.items.get(key)

    def put(self, item):
        self.items[item["key"]] = item
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


async def call_provider(provider, wav_bytes, prompt, timeout_s, retries, sample_rate=SAMPLE_RATE, rate_limiter=None):
    last = None
    for attempt in range(retries + 1):
        try:
            if rate_limiter:
                await rate_limiter.wait()
            return await asyncio.wait_for(
                asyncio.to_thread(provider.classify, wav_bytes, sample_rate, prompt),
                timeout=timeout_s,
            )
        except Exception as exc:
            last = exc
            if attempt < retries:
                retry_delay = parse_retry_delay(str(exc))
                backoff = retry_delay if retry_delay else min(60, 2 ** attempt)
                await asyncio.sleep(max(0.25, backoff))
    return {"raw": "", "usage": {}, "latency_s": 0.0, "error": str(last)}


async def run_clip(cfg, provider, cache, sem, rate_limiter, gold, path, k, timeout_s, retries, variant, retry_cached_errors):
    sample_rate = getattr(provider, "preferred_sample_rate", SAMPLE_RATE)
    wav_bytes, duration_s, trimmed_duration_s, truncated = load_audio_wav_bytes(path, sample_rate=sample_rate)
    trials = []
    for shuffle_index in range(k):
        prompt, option_order = build_prompt(cfg, path, shuffle_index, variant=variant, use_definitions=True, use_cot=True)
        key = cache_key(provider.name, provider.model, path, prompt, shuffle_index)
        cached = cache.get(key)
        if should_use_cached_result(cached, retry_cached_errors=retry_cached_errors):
            result = cached["result"]
        else:
            async with sem:
                result = await call_provider(provider, wav_bytes, prompt, timeout_s, retries, sample_rate=sample_rate, rate_limiter=rate_limiter)
            cache.put({"key": key, "provider": provider.name, "model": provider.model, "clip_path": str(path), "shuffle_seed": shuffle_index, "result": result})
        raw = result.get("raw") or ""
        if result.get("error"):
            pred, letter, status = "", "", "error"
        else:
            pred, letter, status = extract_answer(raw, option_order, cfg)
        confidence = extract_confidence(raw)
        usage = result.get("usage") or {}
        trials.append({
            "shuffle_index": shuffle_index,
            "pred_label": pred,
            "pred_letter": letter,
            "parse_status": status,
            "confidence": confidence,
            "option_order": option_order,
            "raw_output": raw,
            "usage": usage,
            "latency_s": result.get("latency_s", 0.0),
            "cost_usd": provider.estimate_cost(usage),
            "error": result.get("error", ""),
        })
    pred, pred_letter, agreement, vote_dist = vote_trials(trials, cfg["classes"])
    parse_status = "none" if not pred else Counter(t["parse_status"] for t in trials if t["pred_label"] == pred).most_common(1)[0][0]
    confidences = [float(t["confidence"]) for t in trials if t.get("confidence")]
    mean_confidence = sum(confidences) / len(confidences) if confidences else ""
    return {
        "dataset_id": cfg["id"],
        "clip_path": str(path),
        "filename": path.name,
        "gold_label": gold,
        "pred_label": pred,
        "pred_letter": pred_letter,
        "correct": str(pred == gold).lower(),
        "vote_distribution": json.dumps(vote_dist, ensure_ascii=False),
        "agreement": f"{agreement:.4f}",
        "confidence": f"{mean_confidence:.4f}" if mean_confidence != "" else "",
        "parse_status": parse_status,
        "source_hint": infer_source(path),
        "cat_id": cat_id(path, cfg["id"]),
        "duration_s": f"{duration_s:.3f}",
        "trimmed_duration_s": f"{trimmed_duration_s:.3f}",
        "truncated": str(truncated).lower(),
        "raw_output": "\n---TRIAL---\n".join(t["raw_output"] for t in trials),
        "option_order": json.dumps([t["option_order"] for t in trials], ensure_ascii=False),
        "cost_usd": f"{sum(t['cost_usd'] for t in trials):.8f}",
        "k": k,
        "trials": json.dumps(trials, ensure_ascii=False),
    }


async def run_dataset(cfg, provider, args):
    clips = iter_clips(cfg, max_clips=args.max_clips, smoke=args.smoke, seed=args.seed)
    sample_size = sample_size_for(cfg, args)
    if sample_size:
        clips = stratified_sample(clips, cfg["classes"], sample_size, seed=args.seed)
    out_dir = Path(args.out_root) / provider.name / cfg["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "predictions.csv"
    cache = JsonlCache(out_dir / "cache.jsonl")
    sem = asyncio.Semaphore(args.concurrency)
    rpm = args.rate_limit_rpm if args.rate_limit_rpm is not None else getattr(provider, "max_requests_per_minute", 0)
    rate_limiter = AsyncRateLimiter(rpm)
    started = time.perf_counter()
    fields = [
        "dataset_id", "clip_path", "filename", "gold_label", "pred_label", "pred_letter", "correct",
        "vote_distribution", "agreement", "confidence", "parse_status", "source_hint", "cat_id", "duration_s",
        "trimmed_duration_s", "truncated", "raw_output", "option_order", "cost_usd", "k", "trials",
    ]

    rows = []
    clip_iter = iter(clips)
    pending = set()

    def schedule_next():
        try:
            gold, path = next(clip_iter)
        except StopIteration:
            return False
        pending.add(asyncio.create_task(run_clip(cfg, provider, cache, sem, rate_limiter, gold, path, args.k, args.timeout, args.retries, args.variant, not args.use_cached_errors)))
        return True

    for _ in range(max(1, args.concurrency)):
        if not schedule_next():
            break

    completed = 0
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            row = await task
            rows.append(row)
            completed += 1
            print(f"[{provider.name}:{cfg['id']} {completed}/{len(clips)}] {row['gold_label']} -> {row['pred_label'] or 'none'} parse={row['parse_status']}", flush=True)
            schedule_next()

    rows.sort(key=lambda row: row["clip_path"])
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    total_cost = sum(float(row.get("cost_usd") or 0.0) for row in rows)
    (out_dir / "run_summary.json").write_text(json.dumps({
        "provider": provider.name,
        "model": provider.model,
        "dataset_id": cfg["id"],
        "n": len(rows),
        "k": args.k,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_clip_usd": round(total_cost / len(rows), 8) if rows else 0.0,
        "wall_clock_s": round(time.perf_counter() - started, 3),
    }, indent=2), encoding="utf-8")
    print(f"wrote {out_path}", flush=True)
    return out_path


def dry_run(provider, datasets, args):
    lines = []
    total_calls = 0
    for cfg in datasets:
        clips = iter_clips(cfg, max_clips=args.max_clips, smoke=args.smoke, seed=args.seed)
        sample_size = sample_size_for(cfg, args)
        if sample_size:
            clips = stratified_sample(clips, cfg["classes"], sample_size, seed=args.seed)
        n = len(clips)
        calls = n * args.k
        total_calls += calls
        lines.append(f"{cfg['id']}: {n} clips x K={args.k} = {calls} calls")
    print("\n".join(lines))
    print(f"provider={provider.name} model={provider.model} total_calls={total_calls}")
    rpm = args.rate_limit_rpm if args.rate_limit_rpm is not None else getattr(provider, "max_requests_per_minute", 0)
    if rpm:
        print(f"rate_limit={rpm} requests/minute")
    print("Exact spend depends on provider-reported audio/text token usage; responses are cached per clip/prompt shuffle.")


async def main_async(args):
    provider = PROVIDERS[args.provider]
    reason = provider.missing_reason()
    if reason and not (args.dry_run and provider.accepts_audio):
        raise SystemExit(f"Cannot run provider {args.provider}: {reason}")
    datasets = [d for d in DATASETS if d["id"] in ("cat_corpus", "catmeows", "naya_catmood")] if args.dataset == "all" else [DATASET_BY_ID[args.dataset]]
    if args.dry_run:
        dry_run(provider, datasets, args)
        return
    for cfg in datasets:
        pred_path = await run_dataset(cfg, provider, args)
        if not args.no_metrics:
            compute_metrics(cfg["id"], pred_path, pred_path.parent, metric_name="metrics.json")
    if not args.no_metrics:
        build_summary(args.out_root)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    ap.add_argument("--dataset", default="all", choices=["all", "cat_corpus", "catmeows", "naya_catmood"])
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--max-clips", type=int, default=0)
    ap.add_argument("--sample-per-dataset", type=int, default=0, help="seeded stratified sample size per dataset")
    ap.add_argument("--dataset-sample", action="append", default=[], help="override sample size for one dataset, e.g. naya_catmood=60")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--rate-limit-rpm", type=int, default=None, help="provider call pacing; defaults to provider safety limit when set")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--variant", default="frontier")
    ap.add_argument("--out-root", default="outputs/artifacts/frontier")
    ap.add_argument("--no-metrics", action="store_true")
    ap.add_argument("--use-cached-errors", action="store_true", help="reuse cached retryable errors instead of retrying them")
    args = ap.parse_args()
    args.dataset_samples = parse_dataset_samples(args.dataset_sample)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
