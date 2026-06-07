"""Unified 5-class cat-audio taxonomy: label->bucket mapping, discard rules, clip assembly.

Source of truth: probe_plan.md sections 1a/1b/1c.

Buckets: content, soliciting, agitated, distress, hunting.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_registry import (  # noqa: E402
    DATASET_BY_ID,
    iter_rows,
    enrich_rows_with_group_and_source,
)

BUCKETS = ["content", "soliciting", "agitated", "distress", "hunting"]

# probe_plan.md section 1b -- canonical native-label -> bucket map, VERBATIM.
# cat_corpus native label keys are the lowercase folder ids used in probe_registry.
CAT_CORPUS_BUCKET = {
    "purr": "content",
    "chirrup": "content",
    "meow": "soliciting",
    "hiss": "agitated",
    "growl": "agitated",
    "nyaaan": "distress",
    "caterwaul": "distress",
    "chatter": "hunting",
}

# catmeows native labels (filename-prefix derived in probe_registry):
#   brushing (B), waiting_for_food (F), isolation (I)
CATMEOWS_BUCKET = {
    "brushing": "content",
    "waiting_for_food": "soliciting",  # also gets a hunger soft-tag
    "isolation": "distress",
}

# naya native labels (folder, lowercased in probe_registry NAYA_CLASS_NAMES)
NAYA_BUCKET = {
    "happy": "content",
    "resting": "content",
    "mothercall": "soliciting",
    "angry": "agitated",
    "defence": "agitated",
    "warning": "agitated",
    "fighting": "distress",
    "paining": "distress",
    "mating": "distress",
    "huntingmind": "hunting",
}

BUCKET_MAPS = {
    "cat_corpus": CAT_CORPUS_BUCKET,
    "catmeows": CATMEOWS_BUCKET,
    "naya_catmood": NAYA_BUCKET,
}

DATASET_SHORT = {"cat_corpus": "cat_corpus", "catmeows": "catmeows", "naya_catmood": "naya"}

# One-line definitions for the Gemini MCQ (derived from probe_plan.md section 1a).
BUCKET_DEFS = {
    "content": "relaxed/affiliative purr or trill (happy, calm)",
    "soliciting": "meow asking for something, including food",
    "agitated": "growl/hiss, annoyed or feeling threatened ('back off')",
    "distress": "yowl/shriek/caterwaul, something is wrong",
    "hunting": "chatter/excited stalking at prey",
}


@dataclass
class Clip:
    clip_path: str
    dataset_id: str  # cat_corpus | catmeows | naya_catmood
    native_label: str
    bucket: str
    group_key: str  # (dataset, cat/source) -- prefixed with dataset for global uniqueness
    source_hint: str
    hunger: int  # 1 if catmeows waiting_for_food soft-tag, else 0


def _stem(path: str) -> str:
    return Path(path).stem


def build_clips(verbose: bool = True) -> (List[Clip], dict):
    """Assemble the unified clip list, applying probe_plan.md section 1c discards.

    Returns (clips, report_dict).
    """
    report: dict = {}

    raw: Dict[str, List[Clip]] = {}
    for did in ["cat_corpus", "catmeows", "naya_catmood"]:
        cfg = DATASET_BY_ID[did]
        rows = enrich_rows_with_group_and_source(iter_rows(cfg), cfg)  # iter_rows already excludes _aug for naya
        bmap = BUCKET_MAPS[did]
        clips = []
        for r in rows:
            native = r["label"]
            bucket = bmap.get(native)
            if bucket is None:
                # section 1c rule 3: unmapped native label -> discard
                continue
            hunger = 1 if (did == "catmeows" and native == "waiting_for_food") else 0
            clips.append(
                Clip(
                    clip_path=r["path"],
                    dataset_id=did,
                    native_label=native,
                    bucket=bucket,
                    group_key=f"{DATASET_SHORT[did]}::{r['group_key']}",
                    source_hint=r["source_hint"],
                    hunger=hunger,
                )
            )
        raw[did] = clips

    report["raw_counts"] = {did: len(clips) for did, clips in raw.items()}

    # section 1c rule 1 already applied (naya _aug excluded by iter_rows file_filter).
    # Verify no _aug leaked.
    aug_leak = sum(1 for c in raw["naya_catmood"] if "_aug" in Path(c.clip_path).name.lower())
    report["naya_aug_leaked"] = aug_leak

    # section 1c rule 2: cross-dataset shared base filename in BOTH cat_corpus and naya.
    # Compare by exact stem. If their BUCKETS differ -> discard both. If same bucket -> keep one (dedup).
    cc_by_stem: Dict[str, List[Clip]] = defaultdict(list)
    for c in raw["cat_corpus"]:
        cc_by_stem[_stem(c.clip_path)].append(c)
    naya_by_stem: Dict[str, List[Clip]] = defaultdict(list)
    for c in raw["naya_catmood"]:
        naya_by_stem[_stem(c.clip_path)].append(c)

    shared_stems = set(cc_by_stem) & set(naya_by_stem)
    drop_cc_paths = set()
    drop_naya_paths = set()
    n_conflict_dropped = 0
    n_agree_merged = 0

    for stem in shared_stems:
        cc_buckets = {c.bucket for c in cc_by_stem[stem]}
        naya_buckets = {c.bucket for c in naya_by_stem[stem]}
        # A shared stem "agrees" only if both sides map to a single, identical bucket.
        if len(cc_buckets) == 1 and naya_buckets == cc_buckets:
            # agree -> keep cat_corpus copy (higher trust), drop the naya duplicate(s)
            for c in naya_by_stem[stem]:
                drop_naya_paths.add(c.clip_path)
            n_agree_merged += 1
        else:
            # conflict -> discard both sides
            for c in cc_by_stem[stem]:
                drop_cc_paths.add(c.clip_path)
            for c in naya_by_stem[stem]:
                drop_naya_paths.add(c.clip_path)
            n_conflict_dropped += 1

    report["cross_dataset_shared_stems"] = len(shared_stems)
    report["cross_dataset_conflict_stems_dropped_both"] = n_conflict_dropped
    report["cross_dataset_agree_stems_merged_keep_cc"] = n_agree_merged
    report["cc_clips_dropped_by_rule2"] = len(drop_cc_paths)
    report["naya_clips_dropped_by_rule2"] = len(drop_naya_paths)

    final: List[Clip] = []
    for c in raw["cat_corpus"]:
        if c.clip_path not in drop_cc_paths:
            final.append(c)
    for c in raw["catmeows"]:
        final.append(c)
    for c in raw["naya_catmood"]:
        if c.clip_path not in drop_naya_paths:
            final.append(c)

    report["final_total"] = len(final)

    # final per-bucket x per-dataset counts
    grid: Dict[str, Counter] = {b: Counter() for b in BUCKETS}
    for c in final:
        grid[c.bucket][DATASET_SHORT[c.dataset_id]] += 1
    report["per_bucket_per_dataset"] = {b: dict(grid[b]) for b in BUCKETS}
    report["per_bucket_total"] = {b: sum(grid[b].values()) for b in BUCKETS}
    report["per_dataset_total"] = dict(Counter(DATASET_SHORT[c.dataset_id] for c in final))
    report["hunger_positive"] = sum(c.hunger for c in final)
    report["n_groups"] = len({c.group_key for c in final})

    if verbose:
        print("=== taxonomy5 clip assembly report ===")
        for k, v in report.items():
            print(f"{k}: {v}")

    return final, report


if __name__ == "__main__":
    build_clips(verbose=True)
