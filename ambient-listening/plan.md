# Plan: Frontier-Model Audio Classification of Cat Sounds (model-agnostic, 3 datasets)

## Goal
Test whether a **frontier multimodal model** (e.g. GPT-realtime / gpt-4o-audio, MiniMax,
Gemini, …) can classify cat audio directly: **give it the label set + the audio, read back
one label.** Produce **per-dataset** metrics and an **overall comparison** that drops each
model's number next to our existing baselines:

| approach | cat_corpus acc | catmeows macro-F1 | hunger P/R | cost |
|---|---|---|---|---|
| Meow-Omni MCQ prompting | 31% | 0.21 | ~33% P | — |
| embedding-probe (AST/Whisper) | **79%** | **0.54** | ~33% P @ 50–65% R | tiny |
| AST fine-tune | 70% (noisy) | 0.46–0.50 | ~18% P | — |
| **frontier model (this plan)** | _?_ | _?_ | _?_ | _$ / clip_ |

**The one question this answers:** does a frontier model classify well enough to *be* the
perception layer (drop the probe), or does it fumble the hard sound classes so we keep the
hybrid (cheap probe perceives → frontier LLM converses)? Pay special attention to **hunger**
(`waiting_for_food`) — reasoning may be the frontier model's relative strength.

**No training. No RunPod. No GPU.** This runs locally as batched API calls.

---

## Design principle: MODEL-AGNOSTIC (this is the whole point)
The runner never names a vendor. It calls one interface:

```python
class Provider(ABC):
    name: str                      # "gpt-realtime", "minimax-3", "gemini-2.5-pro", ...
    accepts_audio: bool            # True if it ingests raw audio (vs transcript-only)
    def classify(self, audio_wav_bytes: bytes, sr: int, prompt: str) -> dict:
        # returns {"raw": str, "usage": {...}, "latency_s": float}
        ...
```

**Adding a model = one adapter class + one registry row.** Nothing else changes — same
datasets, same prompt builder, same parser, same metrics. So you can run several providers
**in parallel** (each writes to its own output dir) and compare on identical inputs.

```python
PROVIDERS = {
  "gpt-realtime":   OpenAIAudioProvider(model="gpt-realtime",          env="OPENAI_API_KEY"),
  "gpt-4o-audio":   OpenAIAudioProvider(model="gpt-4o-audio-preview",  env="OPENAI_API_KEY"),
  "gemini-2.5-pro": GeminiProvider(model="gemini-2.5-pro",             env="GEMINI_API_KEY"),
  "minimax-3":      MiniMaxProvider(model="<minimax-audio-model-id>",  env="MINIMAX_API_KEY"),
  # add more here
}
```
Select at runtime: `python scripts/frontier_classify.py --provider gpt-realtime --dataset all`.

**Adapter notes (verify per vendor at implementation time — APIs drift):**
- **OpenAI audio** (`gpt-4o-audio-preview`, realtime): chat.completions with a content part
  `{"type":"input_audio","input_audio":{"data":<b64 wav>,"format":"wav"}}`. Realtime model is
  for the live product; for *batch eval* use the regular audio chat endpoint (cheaper, simpler).
- **Gemini**: `inline_data` with `mime_type:"audio/wav"` + base64, or the Files API for larger clips.
- **MiniMax / others**: confirm they accept raw audio input (many "audio" models are TTS-only —
  set `accepts_audio=False` and **skip with a logged reason** if they can't ingest audio; do NOT
  silently fall back to a transcript, that's a different experiment).
- API keys live in `.env` (gitignored) — load via env, **never hard-code or print keys**.

---

## Datasets (all under `data/` — explore ALL three; reuse docs/plan_meow_omni_mcq.md's registry verbatim)

### 1. `cat_corpus` — `data/猫子语料/`  (primary, 8-way, chance 12.5%)
- 8 acoustic classes, label = parent folder. 320 `.mp3`, balanced 40/class.
- Folders: `chatter / hiss / chirrup / nyaaan / growl / purr / caterwaul / meow`
  (Chinese-suffixed dir names; map via `FOLDERS` from docs/plan_meow_omni_mcq.md).
- **Confound:** severe source leakage (chirrup 100% one source, etc.). Report **per-source
  accuracy**; flag single-source classes (chirrup, caterwaul). This is zero-shot so there's no
  train/test leakage, but per-source spread still tells us if it's recognizing recordings.

### 2. `catmeows` — `data/catmeows/dataset/dataset/`  (the product-relevant one, 3-way)
- 3 **context** classes, label = first filename char: `B`→brushing, `F`→**waiting_for_food**,
  `I`→isolation. 440 `.wav`. Imbalanced → **majority baseline 50.2%**; headline = **macro-F1**.
- `waiting_for_food` = **hunger**, our best ground truth. Report its **precision & recall**
  explicitly — a model that nails hunger can win even if overall accuracy is mid.
- Context isn't acoustically obvious ("semantic aliasing") → expect hardest. Beating majority
  at all is notable. Exclude `data/catmeows/extras/*` from the primary run.

### 3. `naya_catmood` — `data/NAYA_DATA_AUG1X/`  (10-way emotion, the real-N version)
- 10 emotion folders: `Angry, Defence, Fighting, Happy, HuntingMind, Mating, MotherCall,
  Paining, Resting, Warning`. Label = parent folder, lowercased.
- **2961 base clips + 2961 augmented copies = 5922 `.mp3`.** Each base clip `X.mp3` has one
  augmented twin `X_aug1(1).mp3`.
- **EVAL ON BASE CLIPS ONLY — drop every `*_aug*.mp3`.** Augmentation exists for *training*;
  for zero-shot it just adds near-duplicates that inflate metrics. After the drop: ~290–300/class,
  **N≈2961, chance 10%, balanced** → real per-class CIs (this is why it replaces catsound_v2).
- **`catsound_v2` is a 5/class SAMPLE of this dataset — retire it; use `naya_catmood` instead.**
  (Keep catsound_v2 only as a tiny smoke set if convenient.)
- **Contamination (confirmed at scale):** source packs (`car_extcoll`, `cat_flickr`, `cat_youtube`,
  `LastEntry_cat`, …) are the **same scrapes as cat_corpus** with **conflicting labels**
  (`car_extcoll0103` = `Angry` here, `nyaaan` in cat_corpus). **Never pool with cat_corpus.**
  Report **per-source-pack accuracy** (group by filename stem, strip trailing digits/`_aug`).
- **`Paining` (291 clips) is NOT clinical pain ground truth** — it's scraper-labeled mood from
  YouTube/flickr on contaminated sources. Report its P/R, but do **not** claim a pain result; the
  "no validated cat-pain audio" finding stands.
- Ships `model_best.hdf5` (the original NAYA Keras classifier) + `Catmood_NAYA_1xAug.csv` (file list).
  Out of scope (no training); a reference baseline only if ever wanted.

**Do NOT pool the datasets** (different taxonomies/chance). Report each separately; "overall" is a
comparison table. Reuse the `DATASETS` registry + `FOLDERS`/prefix maps/definitions from
`docs/plan_meow_omni_mcq.md` so label derivation is identical to every prior experiment (apples-to-apples).
Add a `naya_catmood` registry row: `root=data/NAYA_DATA_AUG1X`, `ext=mp3`,
`label_from=folder` (identity-lowercase), the 10 classes above, `chance=0.10`, and a
**`file_filter` that excludes `*_aug*.mp3`** so only base clips are scored. Write one short
definition per emotion (implementer; flag they're approximate). The 10-class label list is
identical to the old catsound_v2 row — drop that row or point it at the smoke sample.

---

## The method — direct labeling (give labels + audio → return one label)
The frontier model follows instructions (unlike Meow-Omni), so we ask for the label directly.
Reuse docs/plan_meow_omni_mcq.md's **MCQ-with-definitions** format because it (a) pins the model to the exact
allowed label set and (b) keeps scoring identical to the 31% baseline for a fair comparison.

**Per clip:**
1. **Audio prep** (identical to docs/plan_meow_omni_mcq.md so inputs match): load → 16 kHz mono float32;
   `librosa.effects.trim(top_db=30)` to drop dead air; cap ~30 s (480000 samples); encode to
   in-memory **WAV bytes** → base64 for the API. Log original vs trimmed duration + `truncated`.
2. **Build prompt** with all classes + a one-line acoustic/context **definition** each
   (reuse `DEFS_cat_corpus` and the catmeows/catsound_v2 definitions from docs/plan_meow_omni_mcq.md),
   **randomized option order** (seed per clip) to kill position bias:
   ```
   You are an expert in cat vocalizations. Listen to the audio clip and choose the single
   option that best matches the sound. Briefly describe the sound in one sentence, then on a
   new line output exactly "Answer: X" (one letter).
   A) purr — a low, continuous rumble
   B) hiss — a sharp, aggressive exhale / noise burst
   ... (all classes for that dataset, shuffled)
   ```
3. **Self-consistency (optional, default K=1):** repeat with a different shuffle K times,
   majority-vote, record vote distribution + agreement = votes/K (free confidence signal).
   Use K=3 for final numbers if budget allows; K=1 for smoke + cost control.
4. **Parse** (reuse docs/plan_meow_omni_mcq.md's CoT-aware `extract_answer`): `Answer:\s*([A-?])` → else standalone
   in-range letter → else substring-match an option **label word** (exactly one) → else
   `parse_status="none"` (counts wrong). Record `parse_status ∈ {answer_tag, letter, content, none}`.
5. Map voted letter→label; compare to gold.

**Prompt-overfitting guard (don't skip):** zero-shot has no train set, but if you hand-tune the
prompt against the full eval set you're peeking. So **freeze a small dev slice** (~5 clips/class,
seeded) for prompt iteration, and **report on the held-out remainder.** State the split. One
prompt design, applied to every provider — don't tune the prompt per model.

---

## Execution (local, async, cost-aware)
- **Concurrency:** asyncio + a semaphore (start ~8 in-flight); exponential backoff on 429/5xx;
  per-clip timeout + 1 retry, then record `parse_status="error"` (counts wrong, logged).
- **Cost tracking:** capture token/audio usage per call; write per-provider **total + per-clip
  cost** and total wall-clock into the summary. (This is a real decision axis vs the ~free probe.)
- **Caching:** key raw responses by `(provider, model, clip_path, prompt_hash, shuffle_seed)` to a
  JSONL cache so reruns/aborts don't re-pay. Resumable.
- **Cost guardrail:** `--max-clips` and a `--dry-run` that prints estimated spend (clips × K ×
  price) before any paid call. cat_corpus 320 + catmeows 440 + naya_catmood **2961 (base only)**
  = **3721 clips** ×K. NAYA dominates the bill — consider a **stratified subsample** (e.g.
  ~80–100/class, seeded) for the first pass per provider; full 2961 only for the finalist. Smoke
  (3/class) first, confirm parses aren't degenerate, then the (sub)sampled run.

---

## Steps for the implementer (codex)
1. `scripts/frontier_providers.py` — the `Provider` ABC + one adapter per vendor + `PROVIDERS`
   registry. Each reads its key from env; `accepts_audio` gate; returns `{raw, usage, latency_s}`.
2. `scripts/frontier_classify.py` — config-driven runner over the `DATASETS` registry (imported/
   copied from docs/plan_meow_omni_mcq.md). Flags: `--provider`,
   `--dataset {cat_corpus,catmeows,naya_catmood,all}`, `--k`, `--max-clips`, `--dry-run`, `--smoke`.
   For `naya_catmood`, **filter out `*_aug*.mp3` before anything else.**
   Does audio prep → prompt build (shuffled) →
   `provider.classify` → `extract_answer` → row out. Writes
   `outputs/artifacts/frontier/<provider>/<dataset>/predictions.csv` with columns:
   `dataset_id, clip_path, gold_label, pred_label, vote_distribution, agreement, parse_status,
   source_hint, duration_s, trimmed_duration_s, truncated, raw_output, option_order, cost_usd`.
3. Reuse **`scripts/metrics_report.py`** (already label-set-agnostic per docs/plan_meow_omni_mcq.md) per dataset →
   `outputs/artifacts/frontier/<provider>/<dataset>/metrics.json`: accuracy + Wilson 95% CI,
   majority baseline, per-class P/R/F1 (+recall CIs), macro & weighted F1, per-source accuracy,
   parse_status breakdown, confusion matrix, letter-position-bias check. **Plus hunger:**
   `waiting_for_food` precision & recall called out separately.
4. **Smoke** (3 clips/class for cat_corpus, catmeows & naya_catmood, K=1): confirm
   letters extract and predictions aren't degenerate. Then full runs at the chosen K.
5. `outputs/artifacts/frontier/summary.md` — one row **per (provider × dataset)**, merged into the
   comparison table at the top of this doc (alongside MCQ 31% / probe 79% / FT 70%). Include the
   **hunger P/R column** and a **cost column**. Short honest narrative.

---

## How to decide (inherits `experiments.md` — do not crown a noisy winner)
- **Overlapping Wilson CIs = TIED.** At ~40 clips/class, per-class CIs are ±10–15 pts. 52% vs 49%
  is a tie, not a result.
- **The fork:** frontier accuracy **≥ ~probe (79% / macro-F1 0.54), within CI** → frontier *is* the
  perception layer; drop the probe. Clearly **below** (good on easy classes, fumbles the agonistic
  cluster) → keep the hybrid (probe perceives, frontier LLM converses). Decide on the **CI overlap
  with 79% / 0.54**, plus **hunger P/R**, **cost/latency**, and **robustness** (fold/per-source spread).
- **Across providers:** same tie rule. If two models tie, prefer cheaper / lower-latency / the one
  that also fits the live realtime product.
- **Honesty (mandatory in writeup):** per-source-pack accuracy, the **naya_catmood↔cat_corpus
  source overlap with conflicting labels**, that NAYA `Paining` is scraper-labeled (not clinical
  pain), augmented `_aug` dupes excluded, parse/error rates, single-source classes
  (chirrup/caterwaul), catmeows imbalance, and per-provider cost. Small confounded starter datasets
  — report CIs + caveats, don't over-claim.

## Out of scope (explicitly)
- No fine-tuning / training of any kind (settled — embedding-probe already covered the supervised side).
- No RunPod / GPU (frontier eval is API-only and local).
- Transcript-only "audio" models (TTS, ASR-then-LLM) — `accepts_audio=False`, skip with a logged
  reason; that's a different experiment.
- Pain is **not** a target (no open cat-pain audio; cats go silent in pain — settled).
