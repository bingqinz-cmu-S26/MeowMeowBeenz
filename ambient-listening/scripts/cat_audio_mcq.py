"""Config-driven MCQ evaluation for Meow-Omni-1 over local cat-audio datasets.

Run on the GPU pod from the repo root, after `scripts/runpod_setup.sh`:
    python scripts/cat_audio_mcq.py --dataset all --definitions --cot --k 5
    python scripts/cat_audio_mcq.py --dataset cat_corpus --per-class 3 --k 1
    python scripts/cat_audio_mcq.py --ablate-cat-corpus --per-class 0
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

import librosa
import numpy as np
import torch

sys.path.insert(0, os.getenv("MEOW_OMNI_REPO", "/workspace/Meow-Omni-1"))
from src.modeling_meow_omni_1 import MeowOmni1ForCausalLM  # noqa: E402
from src.processing_meow_omni_1 import MeowOmni1Processor  # noqa: E402

WEIGHTS = os.getenv("MEOW_OMNI_WEIGHTS", "/workspace/Meow-Omni-1-weights")
MAX_SAMPLES = 480000
TRIM_TOP_DB = 30

CAT_CORPUS_FOLDERS = {
    "chatter": "chatter嘎嘎 兴奋捕猎状态",
    "hiss": "hiss哈气 defense",
    "chirrup": "chirrup咕噜 交流",
    "nyaaan": "nyaaan打架 暴怒",
    "growl": "growl低吼 警告",
    "purr": "purr呼噜 舒适",
    "caterwaul": "caterwaul老吴 cat-mate",
    "meow": "meow喵 开心",
}

DATASETS = [
    {
        "id": "cat_corpus",
        "root": "data/猫子语料",
        "ext": "mp3",
        "label_from": "folder",
        "folder_map": CAT_CORPUS_FOLDERS,
        "classes": ["chatter", "hiss", "chirrup", "nyaaan", "growl", "purr", "caterwaul", "meow"],
        "chance": 1 / 8,
        "definitions": {
            "purr": "a low, continuous rumble",
            "meow": "a typical 'meow' vocalization",
            "hiss": "a sharp, aggressive exhale / noise burst",
            "growl": "a low-pitched, rumbling threat growl",
            "chatter": "rapid stuttering 'ack-ack-ack' often at prey",
            "chirrup": "a short rising trill / chirp greeting",
            "nyaaan": "a drawn-out angry/fighting yowl",
            "caterwaul": "a loud, wailing mating yowl",
        },
    },
    {
        "id": "catmeows",
        "root": "data/catmeows/dataset/dataset",
        "ext": "wav",
        "label_from": "filename_prefix",
        "prefix_map": {"B": "brushing", "F": "waiting_for_food", "I": "isolation"},
        "option_text": {
            "brushing": "being brushed",
            "waiting_for_food": "waiting for food",
            "isolation": "alone in an unfamiliar place",
        },
        "classes": ["brushing", "waiting_for_food", "isolation"],
        "chance": 1 / 3,
        "definitions": {
            "brushing": "meowing while being brushed",
            "waiting_for_food": "meowing in anticipation of food",
            "isolation": "meowing while alone in an unfamiliar place",
        },
    },
    {
        "id": "catsound_v2",
        "root": "data/catsound_v2/samples/CAT_SOUND_DB_SAMPLES",
        "ext": "mp3",
        "label_from": "folder",
        "folder_map": "identity_lowercase",
        "classes": [
            "paining",
            "happy",
            "mating",
            "warning",
            "angry",
            "huntingmind",
            "fighting",
            "mothercall",
            "resting",
            "defense",
        ],
        "chance": 1 / 10,
        "definitions": {
            "paining": "a distressed or painful vocalization",
            "happy": "a relaxed or positive cat vocalization",
            "mating": "a loud mating call or yowl",
            "warning": "a cautionary threat sound",
            "angry": "an aggressive angry vocalization",
            "huntingmind": "excited hunting or prey-focused chatter",
            "fighting": "a harsh fighting vocalization",
            "mothercall": "a call associated with mother-kitten contact",
            "resting": "a calm resting-state sound",
            "defense": "a defensive hiss, growl, or threat sound",
        },
    },
]

DATASET_BY_ID = {d["id"]: d for d in DATASETS}
ABLATIONS = [
    ("bare_mcq", False, False, 1),
    ("definitions", True, False, 1),
    ("definitions_cot", True, True, 1),
    ("definitions_cot_self_consistency", True, True, 5),
]


def to_dev(x, dev="cuda"):
    if isinstance(x, torch.Tensor):
        return x.to(dev)
    if isinstance(x, dict):
        return {k: to_dev(v, dev) for k, v in x.items()}
    if isinstance(x, list):
        return [to_dev(v, dev) for v in x]
    return x


def robust_decode(output, tok):
    if isinstance(output, tuple) and output and isinstance(output[0], list) and output[0]:
        return str(output[0][0])
    if hasattr(output, "sequences"):
        return tok.decode(output.sequences[0], skip_special_tokens=True)
    if isinstance(output, torch.Tensor):
        return tok.decode(output[0] if output.ndim > 1 else output, skip_special_tokens=True)
    if isinstance(output, str):
        return output
    if isinstance(output, (list, tuple)) and output:
        first = output[0]
        if isinstance(first, str):
            return first
        if isinstance(first, torch.Tensor):
            return tok.decode(first[0] if first.ndim > 1 else first, skip_special_tokens=True)
        return str(first)
    return str(output)


def infer_source(path):
    name = Path(path).name.lower()
    if "youtube" in name:
        return "youtube"
    if "recorded" in name:
        return "recorded"
    if "flickr" in name:
        return "flickr"
    if "coll" in name or name.startswith("cat") or name.startswith("last_add") or name.startswith("car_extcoll"):
        return "scraped_pack"
    return "unknown"


def cat_id(path, dataset_id):
    if dataset_id != "catmeows":
        return ""
    parts = Path(path).stem.split("_")
    return parts[1] if len(parts) > 1 else ""


def iter_clips(cfg, per_class=0):
    root = Path(cfg["root"])
    rows = []
    if cfg["label_from"] == "folder":
        if cfg.get("folder_map") == "identity_lowercase":
            for label in cfg["classes"]:
                folder = next((p for p in root.iterdir() if p.is_dir() and p.name.lower() == label), None)
                if not folder:
                    continue
                paths = sorted(folder.glob(f"*.{cfg['ext']}"))
                rows.extend((label, p) for p in (paths[:per_class] if per_class else paths))
        else:
            for label, folder_name in cfg["folder_map"].items():
                paths = sorted((root / folder_name).glob(f"*.{cfg['ext']}"))
                rows.extend((label, p) for p in (paths[:per_class] if per_class else paths))
    elif cfg["label_from"] == "filename_prefix":
        by_label = {label: [] for label in cfg["classes"]}
        for path in sorted(root.glob(f"*.{cfg['ext']}")):
            label = cfg["prefix_map"].get(path.name[:1])
            if label:
                by_label[label].append(path)
        for label in cfg["classes"]:
            paths = by_label[label]
            rows.extend((label, p) for p in (paths[:per_class] if per_class else paths))
    return rows


def option_text(cfg, label):
    return cfg.get("option_text", {}).get(label, label)


def option_line(cfg, label, use_definitions):
    text = option_text(cfg, label)
    definition = cfg.get("definitions", {}).get(label, "") if use_definitions else ""
    return f"{text} — {definition}" if definition else text


def seed_for(dataset_id, path, shuffle_index, variant):
    raw = f"{dataset_id}:{Path(path).as_posix()}:{shuffle_index}:{variant}".encode("utf-8")
    return int(hashlib.sha1(raw).hexdigest()[:12], 16)


def build_prompt(cfg, path, shuffle_index, variant, use_definitions, use_cot):
    labels = list(cfg["classes"])
    rnd = random.Random(seed_for(cfg["id"], path, shuffle_index, variant))
    rnd.shuffle(labels)
    letters = [chr(ord("A") + i) for i in range(len(labels))]
    lines = [
        "<audio>./</audio>",
        "Listen to the cat audio and decide which option best matches the sound you hear.",
    ]
    lines.extend(f"{letter}) {option_line(cfg, label, use_definitions)}" for letter, label in zip(letters, labels))
    if use_cot:
        lines.append('First briefly describe the sound in one sentence, then on a new line write "Answer: X" where X is the single letter.')
    else:
        lines.append("Answer with the letter only.")
    return "\n".join(lines), labels


def extract_answer(raw_output, option_labels, cfg):
    text = str(raw_output or "").strip()
    valid = "".join(chr(ord("A") + i) for i in range(len(option_labels)))
    answer = re.search(rf"answer\s*:\s*([{valid}])\b", text, flags=re.IGNORECASE)
    if answer:
        letter = answer.group(1).upper()
        return option_labels[ord(letter) - ord("A")], letter, "answer_tag"

    match = re.search(rf"(?<![A-Za-z])([{valid}])(?![A-Za-z])", text, flags=re.IGNORECASE)
    if match:
        letter = match.group(1).upper()
        return option_labels[ord(letter) - ord("A")], letter, "letter"

    lowered = text.lower()
    hits = []
    for idx, label in enumerate(option_labels):
        candidates = {label.lower(), option_text(cfg, label).lower(), label.replace("_", " ").lower()}
        if any(candidate and candidate in lowered for candidate in candidates):
            hits.append((idx, label))
    if len(hits) == 1:
        idx, label = hits[0]
        return label, chr(ord("A") + idx), "content"
    return "", "", "none"


def load_audio(path):
    audio_full = librosa.load(path, sr=16000, mono=True)[0].astype(np.float32)
    original_duration_s = len(audio_full) / 16000.0
    trimmed, _ = librosa.effects.trim(audio_full, top_db=TRIM_TOP_DB)
    if len(trimmed) == 0:
        trimmed = audio_full
    trimmed_duration_s = len(trimmed) / 16000.0
    audio = trimmed[:MAX_SAMPLES]
    return audio, original_duration_s, trimmed_duration_s


def generate(model, proc, audio, prompt):
    enc = proc(
        text=[f"User: {prompt}\nAssistant:"],
        images=None,
        audios=[audio],
        time_series_paths=None,
        time_series_sampling_rates=None,
        ids=["mcq"],
        return_tensors="pt",
    )
    enc = dict(enc.data) if hasattr(enc, "data") else dict(enc.items())
    enc = to_dev(enc)
    bs = enc["input_ids"].shape[0]
    if enc.get("image_bound") is None:
        enc["image_bound"] = torch.zeros(bs, 0, 2, dtype=torch.long, device="cuda")
    gk = {
        "input_ids": enc["input_ids"],
        "attention_mask": enc.get("attention_mask"),
        "tokenizer": proc.tokenizer,
        "max_new_tokens": 96,
        "do_sample": False,
    }
    for key in ["pixel_values", "tgt_sizes", "image_bound", "audio_features", "audio_feature_lens", "audio_bounds"]:
        if key in enc:
            gk[key] = enc[key]
    return robust_decode(model.generate(**gk), proc.tokenizer).strip()


def load_model():
    proc = MeowOmni1Processor.from_pretrained(WEIGHTS, trust_remote_code=True)
    model = MeowOmni1ForCausalLM.from_pretrained(
        WEIGHTS,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    ).to("cuda").eval()
    return model, proc


def vote_trials(trials, classes):
    counts = Counter(t["pred_label"] for t in trials if t["pred_label"])
    if not counts:
        return "", "", 0.0, {}
    class_rank = {label: i for i, label in enumerate(classes)}
    winner, votes = sorted(counts.items(), key=lambda kv: (-kv[1], class_rank.get(kv[0], 999), kv[0]))[0]
    winner_letter = next((t["pred_letter"] for t in trials if t["pred_label"] == winner), "")
    return winner, winner_letter, votes / len(trials), dict(counts)


def run_dataset(cfg, model, proc, out_root, per_class=0, k=1, use_definitions=False, use_cot=False, variant="mcq"):
    out_dir = Path(out_root) / cfg["id"] if variant == "mcq" else Path(out_root) / cfg["id"] / "ablations" / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "predictions_mcq.csv"
    clips = iter_clips(cfg, per_class=per_class)
    rows = []
    for index, (gold, path) in enumerate(clips, start=1):
        audio, original_duration_s, trimmed_duration_s = load_audio(path)
        trials = []
        for shuffle_index in range(k):
            prompt, option_order = build_prompt(cfg, path, shuffle_index, variant, use_definitions, use_cot)
            raw = generate(model, proc, audio, prompt)
            pred, letter, status = extract_answer(raw, option_order, cfg)
            trials.append({
                "shuffle_index": shuffle_index,
                "pred_label": pred,
                "pred_letter": letter,
                "parse_status": status,
                "option_order": option_order,
                "raw_output": raw,
            })
        pred, pred_letter, agreement, vote_dist = vote_trials(trials, cfg["classes"])
        parse_status = "none" if not pred else Counter(t["parse_status"] for t in trials if t["pred_label"] == pred).most_common(1)[0][0]
        row = {
            "dataset_id": cfg["id"],
            "variant": variant,
            "clip_path": str(path),
            "filename": path.name,
            "gold_label": gold,
            "pred_label": pred,
            "pred_letter": pred_letter,
            "correct": str(pred == gold).lower(),
            "parse_status": parse_status,
            "vote_distribution": json.dumps(vote_dist, ensure_ascii=False),
            "agreement": f"{agreement:.4f}",
            "source_hint": infer_source(path),
            "cat_id": cat_id(path, cfg["id"]),
            "duration_s": f"{original_duration_s:.3f}",
            "trimmed_duration_s": f"{trimmed_duration_s:.3f}",
            "truncated": str(trimmed_duration_s > (MAX_SAMPLES / 16000)).lower(),
            "k": k,
            "use_definitions": str(use_definitions).lower(),
            "use_cot": str(use_cot).lower(),
            "trials": json.dumps(trials, ensure_ascii=False),
            "raw_output": "\n---TRIAL---\n".join(t["raw_output"] for t in trials),
        }
        rows.append(row)
        print(f"[{cfg['id']}:{variant} {index}/{len(clips)}] {gold} -> {pred or 'none'} agree={agreement:.2f}", flush=True)

    fields = [
        "dataset_id", "variant", "clip_path", "filename", "gold_label", "pred_label", "pred_letter", "correct",
        "parse_status", "vote_distribution", "agreement", "source_hint", "cat_id", "duration_s", "trimmed_duration_s",
        "truncated", "k", "use_definitions", "use_cot", "trials", "raw_output",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path}", flush=True)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="all", choices=["all"] + sorted(DATASET_BY_ID))
    ap.add_argument("--out-root", default="outputs/artifacts")
    ap.add_argument("--per-class", type=int, default=0, help="clips per class; 0=all")
    ap.add_argument("--k", type=int, default=1, help="self-consistency shuffles per clip")
    ap.add_argument("--definitions", action="store_true", help="include per-class definitions in options")
    ap.add_argument("--cot", action="store_true", help="ask for one-sentence description before Answer: X")
    ap.add_argument("--variant", default="mcq", help="label to store in predictions")
    ap.add_argument("--ablate-cat-corpus", action="store_true", help="run cat_corpus ablation ladder from the plan")
    args = ap.parse_args()

    model, proc = load_model()
    if args.ablate_cat_corpus:
        cfg = DATASET_BY_ID["cat_corpus"]
        for variant, defs, cot, k in ABLATIONS:
            run_dataset(cfg, model, proc, args.out_root, per_class=args.per_class, k=k, use_definitions=defs, use_cot=cot, variant=variant)
        return

    selected = DATASETS if args.dataset == "all" else [DATASET_BY_ID[args.dataset]]
    for cfg in selected:
        run_dataset(
            cfg,
            model,
            proc,
            args.out_root,
            per_class=args.per_class,
            k=args.k,
            use_definitions=args.definitions,
            use_cot=args.cot,
            variant=args.variant,
        )


if __name__ == "__main__":
    main()
