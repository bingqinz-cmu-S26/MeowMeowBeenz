"""Dataset registry and helpers shared by cat-audio evaluation scripts."""
import hashlib
import random
import re
from pathlib import Path

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

CAT_CORPUS_DEFS = {
    "purr": "a low, continuous rumble",
    "meow": "a typical 'meow' vocalization",
    "hiss": "a sharp, aggressive exhale / noise burst",
    "growl": "a low-pitched, rumbling threat growl",
    "chatter": "rapid stuttering 'ack-ack-ack' often at prey",
    "chirrup": "a short rising trill / chirp greeting",
    "nyaaan": "a drawn-out angry/fighting yowl",
    "caterwaul": "a loud, wailing mating yowl",
}

NAYA_CLASSES = [
    "angry",
    "defence",
    "fighting",
    "happy",
    "huntingmind",
    "mating",
    "mothercall",
    "paining",
    "resting",
    "warning",
]

NAYA_DEFS = {
    "angry": "an aggressive angry vocalization",
    "defence": "a defensive hiss, growl, or threat sound",
    "fighting": "a harsh fighting vocalization",
    "happy": "a relaxed or positive cat vocalization",
    "huntingmind": "excited hunting or prey-focused chatter",
    "mating": "a loud mating call or yowl",
    "mothercall": "a call associated with mother-kitten contact",
    "paining": "a distressed scraper-labeled mood vocalization, not validated clinical pain",
    "resting": "a calm resting-state sound",
    "warning": "a cautionary threat sound",
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
        "definitions": CAT_CORPUS_DEFS,
        "note": "Primary 8-way acoustic corpus; source leakage is severe for several classes.",
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
        "note": "Behavioral-context labels; macro-F1 is more informative than raw accuracy.",
    },
    {
        "id": "naya_catmood",
        "root": "data/NAYA_DATA_AUG1X",
        "ext": "mp3",
        "label_from": "folder",
        "folder_map": "identity_lowercase",
        "classes": NAYA_CLASSES,
        "chance": 1 / 10,
        "definitions": NAYA_DEFS,
        "file_filter": "exclude_aug",
        "note": "NAYA base clips only; augmented duplicates are excluded and Paining is not clinical pain ground truth.",
    },
    {
        "id": "catsound_v2",
        "root": "data/catsound_v2/samples/CAT_SOUND_DB_SAMPLES",
        "ext": "mp3",
        "label_from": "folder",
        "folder_map": "identity_lowercase",
        "classes": ["paining", "happy", "mating", "warning", "angry", "huntingmind", "fighting", "mothercall", "resting", "defense"],
        "chance": 1 / 10,
        "definitions": {
            **NAYA_DEFS,
            "defense": NAYA_DEFS["defence"],
        },
        "note": "Exploratory smoke sample only; use naya_catmood for real evaluation.",
    },
]

DATASET_BY_ID = {d["id"]: d for d in DATASETS}


def is_augmented_naya(path):
    return bool(re.search(r"_aug", Path(path).name, flags=re.IGNORECASE))


def include_file(cfg, path):
    if cfg.get("file_filter") == "exclude_aug" and is_augmented_naya(path):
        return False
    return True


def iter_clips(cfg, per_class=0, max_clips=0, smoke=False, seed=13):
    limit = 3 if smoke and not per_class else per_class
    root = Path(cfg["root"])
    rows = []
    if cfg["label_from"] == "folder":
        if cfg.get("folder_map") == "identity_lowercase":
            for label in cfg["classes"]:
                folder = next((p for p in root.iterdir() if p.is_dir() and p.name.lower() == label), None)
                if not folder:
                    continue
                paths = [p for p in sorted(folder.glob(f"*.{cfg['ext']}")) if include_file(cfg, p)]
                rows.extend((label, p) for p in (paths[:limit] if limit else paths))
        else:
            for label, folder_name in cfg["folder_map"].items():
                paths = [p for p in sorted((root / folder_name).glob(f"*.{cfg['ext']}")) if include_file(cfg, p)]
                rows.extend((label, p) for p in (paths[:limit] if limit else paths))
    elif cfg["label_from"] == "filename_prefix":
        by_label = {label: [] for label in cfg["classes"]}
        for path in sorted(root.glob(f"*.{cfg['ext']}")):
            if not include_file(cfg, path):
                continue
            label = cfg["prefix_map"].get(path.name[:1])
            if label:
                by_label[label].append(path)
        for label in cfg["classes"]:
            paths = by_label[label]
            rows.extend((label, p) for p in (paths[:limit] if limit else paths))

    if max_clips and max_clips < len(rows):
        rnd = random.Random(seed)
        rows = sorted(rnd.sample(rows, max_clips), key=lambda item: str(item[1]))
    return rows


def stratified_sample(rows, classes, n, seed=13):
    """Return roughly class-balanced rows without replacement."""
    if not n or n >= len(rows):
        return list(rows)
    by_label = {label: [] for label in classes}
    for gold, path in rows:
        by_label.setdefault(gold, []).append((gold, path))

    rnd = random.Random(seed)
    for label_rows in by_label.values():
        rnd.shuffle(label_rows)

    selected = []
    labels = [label for label in classes if by_label.get(label)]
    if not labels:
        return []

    base = n // len(labels)
    remainder = n % len(labels)
    for idx, label in enumerate(labels):
        take = base + (1 if idx < remainder else 0)
        selected.extend(by_label[label][:take])

    if len(selected) < n:
        already = {path for _, path in selected}
        leftovers = [(gold, path) for gold, path in rows if path not in already]
        rnd.shuffle(leftovers)
        selected.extend(leftovers[: n - len(selected)])

    return sorted(selected[:n], key=lambda item: str(item[1]))


def option_text(cfg, label):
    return cfg.get("option_text", {}).get(label, label)


def option_line(cfg, label, use_definitions=True):
    text = option_text(cfg, label)
    definition = cfg.get("definitions", {}).get(label, "") if use_definitions else ""
    return f"{text} - {definition}" if definition else text


def seed_for(dataset_id, path, shuffle_index, variant):
    raw = f"{dataset_id}:{Path(path).as_posix()}:{shuffle_index}:{variant}".encode("utf-8")
    return int(hashlib.sha1(raw).hexdigest()[:12], 16)


def build_prompt(cfg, path, shuffle_index, variant="frontier", use_definitions=True, use_cot=True):
    labels = list(cfg["classes"])
    rnd = random.Random(seed_for(cfg["id"], path, shuffle_index, variant))
    rnd.shuffle(labels)
    letters = [chr(ord("A") + i) for i in range(len(labels))]
    lines = [
        "You are an expert in cat vocalizations. Listen to the audio clip and choose the single option that best matches the sound.",
    ]
    lines.extend(f"{letter}) {option_line(cfg, label, use_definitions)}" for letter, label in zip(letters, labels))
    lines.append('Output exactly two lines and no other text: "Answer: X" where X is one letter, and "Confidence: Y" where Y is a number from 0 to 1.')
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


def extract_confidence(raw_output):
    text = str(raw_output or "")
    match = re.search(r"confidence\s*:\s*([01](?:\.\d+)?)", text, flags=re.IGNORECASE)
    if not match:
        return ""
    value = float(match.group(1))
    if 0 <= value <= 1:
        return f"{value:.4f}"
    return ""


def infer_source(path):
    name = Path(path).name.lower()
    stem = Path(path).stem.lower()
    if "youtube" in name:
        return "youtube"
    if "recorded" in name:
        return "recorded"
    if "flickr" in name:
        return "flickr"
    if "coll" in name or name.startswith("cat") or name.startswith("last_add") or name.startswith("car_extcoll"):
        return "scraped_pack"
    return re.sub(r"[\d_(). -]+$", "", stem) or "unknown"


def cat_id(path, dataset_id):
    if dataset_id != "catmeows":
        return ""
    parts = Path(path).stem.split("_")
    return parts[1] if len(parts) > 1 else ""
