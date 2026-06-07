"""Shared dataset config and helpers for probe-only AST workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


CAT_CORPUS_FOLDER_MAP: Dict[str, str] = {
    "chatter": "chatter嘎嘎 兴奋捕猎状态",
    "hiss": "hiss哈气 defense",
    "chirrup": "chirrup咕噜 交流",
    "nyaaan": "nyaaan打架 暴怒",
    "growl": "growl低吼 警告",
    "purr": "purr呼噜 舒适",
    "caterwaul": "caterwaul老吴 cat-mate",
    "meow": "meow喵 开心",
}

CATMEOWS_PREFIX_TO_LABEL: Dict[str, str] = {
    "B": "brushing",
    "F": "waiting_for_food",
    "I": "isolation",
}

NAYA_CLASS_NAMES: List[str] = [
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

NAYA_COARSE_MAP: Dict[str, str] = {
    "angry": "agonistic",
    "fighting": "agonistic",
    "warning": "agonistic",
    "defence": "agonistic",
    "happy": "content",
    "resting": "content",
    "mating": "social",
    "mothercall": "social",
    "huntingmind": "hunting",
    "paining": "distress",
}


@dataclass(frozen=True)
class ProbeDataset:
    dataset_id: str
    root: str
    ext: str
    classes: List[str]
    chance: float
    label_from: str
    folder_map: Optional[Dict[str, str]] = None
    prefix_map: Optional[Dict[str, str]] = None
    file_filter: Optional[str] = None
    source_filter: bool = True
    notes: str = ""
    single_source_classes: Optional[Sequence[str]] = None


PROBE_DATASETS: List[ProbeDataset] = [
    ProbeDataset(
        dataset_id="cat_corpus",
        root="data/猫子语料",
        ext="mp3",
        classes=["chatter", "hiss", "chirrup", "nyaaan", "growl", "purr", "caterwaul", "meow"],
        chance=1 / 8,
        label_from="folder",
        folder_map=CAT_CORPUS_FOLDER_MAP,
        source_filter=True,
        notes="Primary 8-way acoustic head. Group by recording source.",
        single_source_classes=["chirrup", "caterwaul"],
    ),
    ProbeDataset(
        dataset_id="catmeows",
        root="data/catmeows/dataset/dataset",
        ext="wav",
        classes=["brushing", "waiting_for_food", "isolation"],
        chance=1 / 3,
        label_from="filename_prefix",
        prefix_map=CATMEOWS_PREFIX_TO_LABEL,
        source_filter=True,
        notes="Hunger/context head. Group by cat_id.",
    ),
    ProbeDataset(
        dataset_id="naya_catmood",
        root="data/NAYA_DATA_AUG1X",
        ext="mp3",
        classes=NAYA_CLASS_NAMES,
        chance=1 / 10,
        label_from="folder",
        folder_map="identity_lowercase",
        file_filter="exclude_aug",
        source_filter=False,
        notes="Exploratory emotion head. Use base clips only; drop *_aug*.mp3.",
    ),
]

DATASET_BY_ID = {cfg.dataset_id: cfg for cfg in PROBE_DATASETS}


def _has_valid_ext(path: Path, ext: str) -> bool:
    return path.suffix.lower() == f".{ext.lower()}"


def _is_augmented_file(path: Path) -> bool:
    return bool(re.search(r"_aug", path.name, flags=re.IGNORECASE))


def include_file(cfg: ProbeDataset, path: Path) -> bool:
    if not path.is_file():
        return False
    if not _has_valid_ext(path, cfg.ext):
        return False
    if cfg.file_filter == "exclude_aug" and _is_augmented_file(path):
        return False
    return True


def iter_rows(cfg: ProbeDataset) -> List[Dict[str, str]]:
    root = Path(cfg.root)
    if not root.is_dir():
        return []

    rows: List[Dict[str, str]] = []

    if cfg.label_from == "folder":
        if cfg.folder_map == "identity_lowercase":
            label_to_dir = {label.lower(): label for label in cfg.classes}
            for path in sorted(root.iterdir()):
                if not path.is_dir():
                    continue
                label = label_to_dir.get(path.name.lower())
                if label is None:
                    continue
                for clip in sorted(path.glob(f"*.{cfg.ext}")):
                    if include_file(cfg, clip):
                        rows.append({"path": str(clip), "label": label})
        else:
            for label, folder in (cfg.folder_map or {}).items():
                folder_path = root / folder
                if not folder_path.is_dir():
                    continue
                for clip in sorted(folder_path.glob(f"*.{cfg.ext}")):
                    if include_file(cfg, clip):
                        rows.append({"path": str(clip), "label": label})

    elif cfg.label_from == "filename_prefix":
        for clip in sorted(root.glob(f"*.{cfg.ext}")):
            if not include_file(cfg, clip):
                continue
            stem = clip.stem
            label = cfg.prefix_map.get(stem[:1]) if cfg.prefix_map else None
            if label:
                rows.append({"path": str(clip), "label": label})

    return rows


def infer_source_hint(path: str) -> str:
    name = Path(path).name.lower()
    stem = Path(path).stem.lower()

    if "youtube" in name:
        return "youtube"
    if "recorded" in name:
        return "recorded"
    if "flickr" in name:
        return "flickr"
    if "extcoll" in stem or "car_extcoll" in stem:
        return "external_collection"
    if stem.startswith("cat") or stem.startswith("last_add") or stem.startswith("lastentry"):
        return "scraped_pack"
    return re.sub(r"[\d_(). -]+$", "", stem) or "unknown"


def infer_catmeows_cat_id(path: str) -> str:
    parts = Path(path).stem.split("_")
    return parts[1] if len(parts) > 1 else "unknown"


def _collapse_aug_suffix(stem: str) -> str:
    stem = re.sub(r"_aug.*$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\([^)]*\)$", "", stem)
    stem = re.sub(r"[\(\)]", "", stem)
    stem = re.sub(r"\d+$", "", stem)
    return stem.lower().strip("._- ")


def infer_naya_group_key(path: str) -> str:
    stem = Path(path).stem
    base = _collapse_aug_suffix(stem)
    if not base:
        return "unknown"
    return base


def group_key_for_row(cfg: ProbeDataset, path: str) -> str:
    if cfg.dataset_id == "cat_corpus":
        return infer_source_hint(path)
    if cfg.dataset_id == "catmeows":
        return infer_catmeows_cat_id(path)
    if cfg.dataset_id == "naya_catmood":
        return infer_naya_group_key(path)
    return "unknown"


def enrich_rows_with_group_and_source(rows: Iterable[Dict[str, str]], cfg: ProbeDataset) -> List[Dict[str, str]]:
    out = []
    for item in rows:
        path = item["path"]
        enriched = dict(item)
        enriched["group_key"] = group_key_for_row(cfg, path)
        enriched["source_hint"] = infer_source_hint(path)
        out.append(enriched)
    return out


def coarse_label_naya(label: str) -> str:
    return NAYA_COARSE_MAP.get(label, "other")
