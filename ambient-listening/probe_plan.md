# Plan: AST + Linear-Probe Audio Perception Layer (audio-only, deployable)

## Goal
Build the **production audio-perception module** for the cat product: a frozen **AST**
encoder turns a cat clip into an embedding, and cheap **logistic-regression probes** map that
embedding to labels. Audio-only (no video here). Deliver **honestly-evaluated metrics**
(grouped CV) **and a saved, runnable probe artifact** the conversational LLM can call.

This is NOT a fresh exploration — the `encoder-probe` experiment already showed **AST-probe
wins** (cat_corpus acc ~0.79, ties Meow-Omni's 18GB encoder; catmeows macro-F1 ~0.54). This
plan **consolidates that into a deployable module**: pick AST + logistic regression (the proven
winner), evaluate it rigorously, and save the model + an inference function.

---

## 1. Dataset strategy — UNIFIED 5-CLASS TAXONOMY
We classify into **5 product categories** (science-grounded — see §1a). Every dataset's native
labels are **mapped into these 5 buckets** (§1b) so that a single probe AND a single Gemini prompt
use the *same* labels → finally comparable. Embed each clip once (frozen AST), then train **one
5-class** logistic-regression probe.

Pooling RAW labels would be invalid (the same `car_extcoll` clip is `Angry` in naya, `nyaaan` in
cat_corpus). Pooling into COARSE buckets is the controlled version **only if** the discard rules
(§1c) are obeyed. Trust still varies (catmeows ★★★ peer-reviewed + cat IDs; cat_corpus ★★
acoustic-real; naya ★ scraper-noise), so **report a per-dataset breakdown** of each bucket to
detect dataset-signature leakage (e.g. probe learning "this is a catmeows 0–4 kHz recording" → a
class). Group CV by `(dataset, cat/source)` so no recording spans folds.

### 1a. The 5 categories (arousal/valence-grounded)
| Category | Vocalizations | Owner meaning | arousal/valence |
|---|---|---|---|
| **content** | purr, trill | relaxed / happy | low / + |
| **soliciting** *(+hunger soft-tag)* | meow, chirp | wants something / food | low-med / neutral |
| **agitated** | growl, hiss, snarl | "back off" — annoyed/threatened | med / − |
| **distress** | yowl, shriek, caterwaul | something's wrong (**pain folds here**) | high / − |
| **hunting** | chatter, chirrup-at-prey | excited / stalking | med / + |

**Pain is NOT a category** — feline pain is acoustically a fight-only "shriek" or silence; the
validated pain signal is visual (Feline Grimace Scale). Audio pain → **distress** bucket; true pain
detection is deferred to the video arm + the conversation layer. **Hunger is a soft sub-tag of
soliciting** (food-meows only ~40% recognizable), not its own class.

### 1b. Canonical label → bucket mapping (authoritative — use verbatim)
```
content    : cat_corpus{purr, chirrup}      catmeows{brushing}            naya{Happy, Resting}
soliciting : cat_corpus{meow}               catmeows{waiting_for_food*}   naya{MotherCall}
agitated   : cat_corpus{hiss, growl}                                      naya{Angry, Defence, Warning}
distress   : cat_corpus{nyaaan, caterwaul}  catmeows{isolation}           naya{Fighting, Paining, Mating}
hunting    : cat_corpus{chatter}                                          naya{HuntingMind}
```
`*` waiting_for_food also gets a boolean `hunger` sub-tag for the soft hunger signal.
**Soft judgment calls (flagged, change if desired):** `chirrup→content` (trill=affiliative
greeting), `brushing→content` & `isolation→distress` (context-meows = the hard semantic-aliasing
cases), `caterwaul`+`Mating→distress` (acoustic yowl, not emotionally distress), `MotherCall→
soliciting` (contact call). All native labels are mapped; nothing is unmapped by default.

### 1c. Discard rules (the "discard if needed")
1. **Drop every naya `*_aug*.mp3`** (augmented dupes — eval on base clips only).
2. **Cross-dataset shared clips** (same base filename in both cat_corpus and naya): if the two
   datasets' labels map to **different** buckets → **discard both**; if the **same** bucket → keep
   **one** copy (dedup). Report how many were dropped/merged.
3. Any clip whose native label isn't in the §1b map → discard (none today; rule stands for new data).
4. Log final per-bucket, per-dataset counts so class balance + sourcing are visible.

---

## 2. The method — universally-accepted protocol (do exactly this)
**(a) Linear probing on frozen embeddings.** Freeze AST, extract one embedding per clip, train a
**`LogisticRegression`** on top. Linear is the *convention* precisely because it's weak — if a
linear boundary separates classes, the *embedding* did the work (which is what we're testing).

**(b) Subject/source-independent k-fold CV.** `StratifiedGroupKFold` so the **same cat/source
never appears in train and test**. This is non-negotiable: CatMeows scored 95.94% with random
splits but **63.6%** holding out whole cats — the 30-pt gap is leakage. The product meets *new*
cats, so only grouped CV measures what it actually does. Report **macro-F1, mean ± 95% CI across
folds** (macro, not accuracy — catmeows & naya care about minority classes).

```
clip → AST (frozen) → mean-pooled embedding → StandardScaler → LogisticRegression
     → StratifiedGroupKFold(group = cat/source) → macro-F1 mean±95% CI + per-class P/R/F1
```

---

## 3. AST + embedding specifics (don't re-derive)
- **Model:** `MIT/ast-finetuned-audioset-10-10-0.4593` (pure-PyTorch, the proven winner). Use the
  HF `ASTModel` + `AutoFeatureExtractor`.
- **Audio prep (identical to the frontier runs so inputs match):** load → **16 kHz mono float32**;
  `librosa.effects.trim(top_db=30)` to drop dead air; the AST feature extractor handles mel-spec
  (128 bins) + its own length norm. Clips are short (<10 s) so no truncation issue. Works for
  `.mp3` and `.wav`.
- **Embedding = mean-pool the last hidden state** over the time axis → one vector/clip (~768-d).
  Also try the model's pooled/`[CLS]` output as an ablation; keep whichever scores higher on
  cat_corpus (decide once, use everywhere). *(Lead from prior work: earlier layers sometimes beat
  the last — optional layer sweep, not required.)*
- **Probe:** `sklearn.linear_model.LogisticRegression(max_iter=2000, C=1.0,
  class_weight="balanced", multi_class="multinomial")`, on **StandardScaler-ed** features.
  `class_weight="balanced"` matters for catmeows/naya imbalance.

**Embed ONCE, reuse forever.** Cache embeddings to `.npy` keyed by dataset+clip. The
`outputs/artifacts/encoder-probe/_cache/` dir already has `cat_corpus_ast.npy`,
`catmeows_ast.npy`, `catsound_v2_ast.npy` — **reuse those if the clip ordering matches**;
**naya must be embedded fresh** (it didn't exist then). Re-embedding all is fine too (cheap-ish,
one pass); just verify counts: cat_corpus 320, catmeows 440, naya **base-clips-only** ≈ 2961.

---

## 4. Per-dataset details

### acoustic head — cat_corpus (`data/猫子语料/`)
- 8 classes, label = parent folder (map via `FOLDERS` from `docs/plan_meow_omni_mcq.md`).
- **Group = recording source** (derive source from filename / use existing `source_hint`).
- **chirrup & caterwaul are 100% single-source** → under grouped CV they're structurally
  untrainable (can't put the class in both train and test). **Report them, flag the artifact,
  and also report macro-F1 EXCLUDING them** (prior work: that lifts macro-F1 ~0.50 → ~0.70).
- Headline: accuracy + macro-F1, **per-source accuracy** (the leakage check).

### hunger head — catmeows (`data/catmeows/dataset/dataset/`)
- 3 context classes from filename prefix: `B`→brushing, `F`→**waiting_for_food**, `I`→isolation.
- **Group = cat ID** (filename field 2, e.g. `ANI01`) — the gold subject-independent eval.
- **Report `waiting_for_food` precision & recall explicitly** (the product's hunger signal) +
  **majority baseline 50.2%** + macro-F1. Expect modest (~0.54 macro-F1, hunger ~0.33 P) — that's
  the honest ceiling, not a failure (context isn't fully audible).
- Exclude `data/catmeows/extras/*`.

### emotion head — naya_catmood (`data/NAYA_DATA_AUG1X/`)
- 10 emotion folders, label = folder lowercased. **DROP every `*_aug*.mp3`** (augmented twins
  inflate metrics) → ~2961 base clips.
- **Group = source pack** (filename stem, strip trailing digits + `_aug`: `car_extcoll`,
  `cat_flickr`, `cat_youtube`, …). Without this the number is leakage.
- Report fine 10-way **and** a **coarse collapse** as an ablation (the 10-way is over-split):
  `{angry,fighting,warning,defence}→agonistic`, `{happy,resting}→content`,
  `{mating,mothercall}→social`, `huntingmind→hunting`, `paining→distress`.
- **`Paining` is NOT clinical pain** — report P/R but label it "scraper-mood, unvalidated" in every
  output. Do not present a "pain detector."

---

## 5. Steps for the implementer (codex)
1. `scripts/ast_embed.py` — config-driven over the dataset registry (reuse `DATASETS` +
   `FOLDERS`/prefix maps from `docs/plan_meow_omni_mcq.md`; add the `naya_catmood` row with the
   `*_aug*` filter). Loads AST once, embeds each dataset's clips, writes
   `outputs/artifacts/probe/_emb/<dataset>.npy` + a parallel `<dataset>_meta.csv`
   (`clip_path, label, group_key, source_hint`). Reuse existing `_cache/*_ast.npy` if ordering
   verifiably matches; else re-embed.
2. `scripts/train_probe.py` — for each dataset: StandardScaler + LogisticRegression under
   `StratifiedGroupKFold(n_splits=5, group=group_key)`. Emit OOF predictions + metrics.
3. **Metrics** (reuse/generalize `scripts/metrics_report.py`): per dataset →
   `outputs/artifacts/probe/<dataset>/metrics.json`: accuracy + Wilson CI, **macro-F1 mean±95%
   CI across folds**, per-class P/R/F1, confusion, per-group accuracy (leakage check),
   majority baseline. **catmeows also:** `waiting_for_food` P/R. **cat_corpus also:** macro-F1
   excluding single-source classes. **naya also:** fine + coarse tables, Paining flagged.
4. **Final artifacts** — after CV, refit each head on **all** that dataset's data and save:
   `outputs/artifacts/probe/<dataset>/probe.joblib` (scaler + LogisticRegression) +
   `label_names.json`. Provide `scripts/probe_infer.py` with
   `classify(audio_path) -> {head: {label, confidence, proba_dict}}` running AST once and all
   heads on the shared embedding. `confidence = max predict_proba`.
5. `outputs/artifacts/probe/summary.md` — one row per head: `dataset | N | #classes | chance |
   majority | accuracy[CI] | macro-F1[CI] | key class P/R | top leakage flag`. Compare against the
   anchors (Meow-Omni MCQ 31%, frontier Gemini-flash ~0.54, this probe). Honest narrative.

---

## 6. What "good" looks like / decision criteria
- **acoustic head:** macro-F1 (ex single-source) ≳ 0.70, per-source spread not wild → ship it as
  the perception backbone. This is the signal the LLM reasons over ("hiss → likely upset").
- **hunger head:** honest `waiting_for_food` P/R under cat-grouped CV. If precision stays ~0.33,
  ship it only as a **low-confidence "possible hunger" tag**, never a confident alert. State it.
- **emotion head:** if source-grouped macro-F1 collapses toward chance, that confirms it was
  leakage → keep naya as exploratory only, don't ship the emotion labels. If coarse-collapse holds
  up, the coarse buckets may be usable.
- **One-SE / CI honesty:** overlapping CIs = tied; don't crown noise. Report CIs everywhere.

## 7. Deliverable summary
A saved `probe.joblib` per head + `probe_infer.py` that takes an audio file and returns labels +
confidences for all heads from a single AST pass — the runnable perception layer that the
frontier conversation model consumes. Plus the honest grouped-CV metrics in `summary.md`.

## 8. Out of scope
- No video (audio-only). No fine-tuning of AST (frozen — that's the whole point; fine-tune was
  already tried, 70% noisy/overfit). No pooling datasets into one accuracy. No "pain detector"
  claim from naya. Pain stays out (no validated cat-pain audio exists).
