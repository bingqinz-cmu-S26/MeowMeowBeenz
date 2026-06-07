# Plan: MCQ-Style Audio-Only Evaluation of Meow-Omni-1 (3 datasets)

## Goal
Evaluate Meow-Omni-1 audio-only on **three** local cat-audio datasets using the
**paper's own prediction method** (multiple-choice + letter extraction + text
fallback). Produce **per-dataset** metrics and an **overall summary** comparing them.

**Why MCQ:** the model was trained to *describe* standalone audio, not emit labels
(paper Appendix A.3), so it ignores "return only the label." The paper handles this
by posing each item as a multiple-choice question, asking for a letter, extracting
`A–D` with a regex, and falling back to matching option *text* inside the model's
description (`src/evaluation/eval_meow.py::extract_answer`). We mirror that.

**Baseline to beat (dataset 1 only):** forced-label-likelihood scoring got **30.3%**
overall (chance 12.5%); only `purr` was reliable (F1 0.92), the rest collapsed to a
bias attractor. The MCQ method should measure the model's actual hearing instead of
its word-priors. Prior run: `outputs/artifacts/predictions.csv` / `metrics.json`.

> The harness MUST be **config-driven** (a dataset registry), because the three
> datasets have different label sets, label-derivation rules, file types, and sizes.
> More datasets are coming, so adding one should be a config entry, not new code.

---

## Datasets (all under `data/`)

### 1. `cat_corpus` — `data/猫子语料/`  (the primary)
- **8 acoustic sound-type classes**, label = parent folder. 320 `.mp3`, **balanced 40/class**. Chance **12.5%**.
- Canonical labels + folders:
  ```python
  FOLDERS = {"chatter":"chatter嘎嘎 兴奋捕猎状态","hiss":"hiss哈气 defense",
    "chirrup":"chirrup咕噜 交流","nyaaan":"nyaaan打架 暴怒","growl":"growl低吼 警告",
    "purr":"purr呼噜 舒适","caterwaul":"caterwaul老吴 cat-mate","meow":"meow喵 开心"}
  ```
- 44.1 kHz stereo MP3 → load as 16 kHz mono.
- **Confound:** severe source leakage (chirrup 100% YouTube, caterwaul 100% one source,
  hiss/nyaaan/meow 100% scraped). Report per-source accuracy; flag single-source classes.

### 2. `catmeows` — `data/catmeows/dataset/dataset/`  (Ntalampiras CatMeows)
- **3 behavioral-CONTEXT classes**, label = **first char of filename**: `B`→`brushing`,
  `F`→`waiting_for_food`, `I`→`isolation`. 440 `.wav`.
- **Imbalanced:** B=127, F=92, I=221 → **majority baseline = 221/440 ≈ 50.2%** (report it!).
  Uniform chance over 3 = 33.3%. Use macro-F1 as the headline, not raw accuracy.
- Filename format `C_CATID_BREED_SEX_OWNERREC_...wav` (e.g. `I_ANI01_MC_FN_SIM01_101.wav`);
  21 distinct cats (field 2). **Cat-ID leakage** isn't an issue for zero-shot (no training),
  but report per-cat spread if easy.
- These are **why the cat meowed** (context), NOT acoustic types — this is the paper's
  "semantic aliasing" case (same meow, different context). **Expect this to be the hardest**;
  audio often cannot resolve context. That's a finding, not a failure.
- MCQ option text should be human-readable: "being brushed" / "waiting for food" /
  "alone in an unfamiliar place".
- `data/catmeows/extras/{sequences,other_vocalizations}` (30 + 13): **exclude from the
  primary run** (multi-meow sequences / non-meow sounds); optional secondary.

### 3. `catsound_v2` — `data/catsound_v2/samples/CAT_SOUND_DB_SAMPLES/`
- **10 emotion/state classes**, label = parent folder (lowercased): `Paining, Happy,
  Mating, Warning, Angry, HuntingMind, Fighting, MotherCall, Resting, Defense`.
- **Only 50 `.mp3` (5/class)** → **exploratory/qualitative only**; per-class CIs will be
  enormous (n=5). Chance 10%. Report but do not over-interpret.
- **Cross-dataset contamination:** uses the SAME scrape packs as `cat_corpus`
  (`car_extcoll####.mp3` appears in both) with **conflicting labels** (a `car_extcoll`
  clip is `nyaaan` in cat_corpus, `Angry`/`Warning`/`Paining` here). So datasets are NOT
  independent — never pool them, and flag this in the writeup.

**Do NOT pool the three into one accuracy** — different taxonomies and chance levels.
Report each separately; the "overall" is a comparison table (see Outputs).

### Dataset registry (build this)
```python
DATASETS = [
  {"id":"cat_corpus", "root":"data/猫子语料", "ext":"mp3",
   "label_from":"folder", "folder_map":FOLDERS,  # folder basename -> canonical
   "classes":[...8...], "chance":0.125},
  {"id":"catmeows", "root":"data/catmeows/dataset/dataset", "ext":"wav",
   "label_from":"filename_prefix", "prefix_map":{"B":"brushing","F":"waiting_for_food","I":"isolation"},
   "option_text":{"brushing":"being brushed","waiting_for_food":"waiting for food","isolation":"alone in an unfamiliar place"},
   "classes":["brushing","waiting_for_food","isolation"], "chance":1/3},
  {"id":"catsound_v2", "root":"data/catsound_v2/samples/CAT_SOUND_DB_SAMPLES", "ext":"mp3",
   "label_from":"folder", "folder_map":"identity_lowercase",
   "classes":["paining","happy","mating","warning","angry","huntingmind","fighting","mothercall","resting","defense"], "chance":0.10},
]
```

---

## The method — MCQ + Group-A enhancements (mirror `eval_meow.py::extract_answer`, then strengthen)

Base = paper's MCQ over **all classes of the dataset** (8 / 3 / 10 options; chance 12.5% /
33% / 10%). On top of that, apply the three dataset-agnostic boosters below, plus
per-class **definitions** (config). Make each booster a toggle so we can ablate it.

**Per clip:**
1. **Audio load + cleanup:** load → 16 kHz mono float32; **trim leading/trailing silence**
   (`librosa.effects.trim`, e.g. top_db=30) so the model hears the vocalization, not dead air;
   then cap at 480000 samples (~30 s). Log original vs trimmed duration + `truncated`.
2. **Build the MCQ with definitions + randomized order** (seed per clip; randomize order to
   avoid letter-position bias). Each option shows the label **and a short acoustic definition**:
   ```
   <audio>./</audio>
   Listen to the cat audio and decide which option best matches the sound you hear.
   A) purr — a low, continuous rumble
   B) hiss — a sharp, aggressive exhale / noise burst
   ... (all classes, shuffled)
   First briefly describe the sound in one sentence, then on a new line write "Answer: X"
   (the single letter).
   ```
   wrap as `f"User: {prompt}\nAssistant:"`. (The "describe then answer" line is the **CoT**
   booster — it lets the model do what it's good at, *then* commit to a letter.)
3. **Self-consistency:** repeat steps 2–4 **K times** (default K=5) with a *different* random
   option order each time; collect the K predicted labels and **majority-vote**. Record the
   vote distribution and agreement = votes_for_winner / K (a free confidence signal). Use
   `do_sample=False` (the shuffles provide the variation); K=1 for fast smoke runs.
4. **Generate** (`max_new_tokens≈96` to allow the one-sentence CoT + the answer line).
5. **Extract answer** (CoT-aware, mirrors the paper's fallback): first look for
   `Answer:\s*([A-?])`; else a standalone letter in range; else substring-match an option's
   **label word** in the lowercased text (exactly one → use it); else `parse_status="none"`
   (counts wrong). Record `parse_status ∈ {answer_tag, letter, content, none}` + option order.
6. Map the voted letter→label, compare to gold.

**Definitions (config, per dataset).** cat_corpus (use these):
```python
DEFS_cat_corpus = {
 "purr":"a low, continuous rumble",
 "meow":"a typical 'meow' vocalization",
 "hiss":"a sharp, aggressive exhale / noise burst",
 "growl":"a low-pitched, rumbling threat growl",
 "chatter":"rapid stuttering 'ack-ack-ack' (often at prey)",
 "chirrup":"a short rising trill / chirp greeting",
 "nyaaan":"a drawn-out angry/fighting yowl",
 "caterwaul":"a loud, wailing mating yowl",
}
```
For **catmeows** (context, not acoustic — definitions describe the situation): brushing="meowing
while being brushed", waiting_for_food="meowing in anticipation of food", isolation="meowing while
alone in an unfamiliar place". For **catsound_v2** (10 emotions): implementer writes one short
definition per class (starter framing fine; flag they're approximate). Definitions go in the
dataset registry as a `definitions` field.

**Ablation (do this on cat_corpus so we learn what helps):** run bare-MCQ first, then
+definitions, +CoT, +self-consistency, reporting accuracy at each step. That tells us which
booster actually moved the needle (and is reusable for future datasets). Keep each a flag.

---

## Verified model API (discovered the hard way — DO NOT re-derive)
Load via the repo's **`src` classes**, NOT `AutoModel`/auto_map. The HF-weights copy of
`modeling_meow_omni_1.py` inherits `Qwen3PreTrainedModel` and has **no `.generate`**; the
`src/` copy inherits `MiniCPMO` and does. `eval_meow.py` uses the src classes.

```python
import sys, numpy as np, librosa, torch
sys.path.insert(0, "/workspace/Meow-Omni-1")
from src.modeling_meow_omni_1 import MeowOmni1ForCausalLM
from src.processing_meow_omni_1 import MeowOmni1Processor

WEIGHTS = "/workspace/Meow-Omni-1-weights"
proc  = MeowOmni1Processor.from_pretrained(WEIGHTS, trust_remote_code=True)
model = MeowOmni1ForCausalLM.from_pretrained(
    WEIGHTS, trust_remote_code=True, torch_dtype=torch.bfloat16).to("cuda").eval()

audio = librosa.load(path, sr=16000, mono=True)[0].astype(np.float32)[:480000]  # works for .wav AND .mp3
enc = proc(text=[f"User: {prompt}\nAssistant:"], images=None, audios=[audio],
           time_series_paths=None, time_series_sampling_rates=None,  # MUST be None, not [] (torch.stack([]) crash)
           ids=["x"], return_tensors="pt")
enc = dict(enc.data) if hasattr(enc, "data") else dict(enc.items())
def to_dev(x):
    if isinstance(x, torch.Tensor): return x.to("cuda")
    if isinstance(x, dict): return {k: to_dev(v) for k,v in x.items()}
    if isinstance(x, list): return [to_dev(v) for v in x]
    return x
enc = to_dev(enc); bs = enc["input_ids"].shape[0]
if enc.get("image_bound") is None:
    enc["image_bound"] = torch.zeros(bs, 0, 2, dtype=torch.long, device="cuda")
gk = {"input_ids":enc["input_ids"], "attention_mask":enc.get("attention_mask"),
      "tokenizer":proc.tokenizer, "max_new_tokens":64, "do_sample":False}
for k in ["pixel_values","tgt_sizes","image_bound","audio_features","audio_feature_lens","audio_bounds"]:
    if k in enc: gk[k] = enc[k]
output = model.generate(**gk)   # returns a TUPLE: (list_of_strings, GenerateDecoderOnlyOutput)
```
Decode: text is `output[0][0]`; use a robust decoder that also handles `.sequences`/Tensor/str
(see `scripts/cat_audio_score.py`, which already implements all of the above correctly).

**Gotchas already hit:** `transformers==4.57.6` pin (don't bump); don't load via auto_map
(no `.generate` + hyphen-dir dynamic-import bug); `None` not `[]` for unused modalities;
audio must be 16 kHz mono (processor does not resample).

---

## Prerequisites (already satisfied on this machine — no action needed from the user)
If you run on **this machine / same user**, everything needed is already set up and persists on disk:
- **RunPod auth:** `runpodctl` v2.3.0 installed + authed via `~/.runpod/config.toml`
  (the API key is also in `./.env` as `RUNPOD_API_KEY` if you need it). Balance **~$9.36**, spend limit $80.
- **SSH:** private key `~/.runpod/ssh/runpodctl-ssh-key` on disk; matching public key is registered on
  the RunPod account (`runpodctl ssh list-keys` → `runpodctl-ssh-key`), so it auto-injects into new pods.
- **Model is public** (`smgjch/Meow-Omni-1`, Apache-2.0) → **no HuggingFace token needed** to download.
- **Datasets + scripts** are in `data/` and `scripts/`. Local `python3` available (metrics use stdlib only).
- **No prior pod** (the old one was terminated) and the stale ssh alias was removed → create fresh, write a fresh alias.
> If you run in a *different* environment, you must copy over the RunPod API key and
> `~/.runpod/ssh/runpodctl-ssh-key`, and `pip install librosa soundfile` locally is NOT needed (eval runs on the pod).

## Infrastructure (RunPod, GPU required — not Mac-local)
`runpodctl` is installed/authed (`~/.runpod/config.toml`); key `~/.runpod/ssh/runpodctl-ssh-key` (ssh-rsa).
Prior pod `4b31f14rode0qe` is STOPPED and resume currently fails ("no free GPUs on host") —
**create a fresh pod**:
```bash
runpodctl pod create --name meow-omni-eval \
  --image "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04" \
  --gpu-id "NVIDIA L40S" --gpu-count 1 --cloud-type SECURE \
  --container-disk-in-gb 40 --volume-in-gb 60 --volume-mount-path /workspace \
  --ports '8000/http,22/tcp' --ssh --stop-after <ISO-3h-from-now>
```
- **If `pod create` fails** ("no free GPUs"/stock Low — we hit this): retry, then fall back across
  GPU types **L40S → A40 → A100 PCIe** (all 48–80 GB, all fine) and/or `--cloud-type COMMUNITY`.
  Don't burn time on one GPU type. Poll `runpodctl pod get <id>` until `runtime` populates (image
  pull can take a few min; a community node once hung ~16 min — if so, kill and recreate).
- TCP `ip:port` from `runpodctl pod get <id>` → `runtime.ports` (tcp, privatePort 22).
- ssh/scp need ssh-rsa enabled + the runpod key (direct TCP supports scp; the `ssh.runpod.io` proxy does not). `~/.ssh/config`:
  ```
  Host runpodpod
    HostName <ip>
    Port <port>
    User root
    IdentityFile ~/.runpod/ssh/runpodctl-ssh-key
    PubkeyAcceptedAlgorithms +ssh-rsa
    StrictHostKeyChecking accept-new
  ```
- Setup: run `scripts/runpod_setup.sh` (deps + clone `github.com/smgjch/Meow-Omni-1` +
  pip `requirements.txt` + download ~18 GB weights to `/workspace/Meow-Omni-1-weights`, ~10 min).
- **Upload all three datasets** to the pod (scp the `data/` subfolders, or zip+scp+extract).
  For any macOS-made zip with Chinese names, extract with the cp437→utf8 fix
  (`scripts/extract_fix.py`). Verify counts: cat_corpus 320, catmeows 440, catsound_v2 50.
- **Cost:** ~$0.86/hr; full 3-dataset run is ~minutes. **Stop the pod
  (`runpodctl pod stop <id>`) the instant the run finishes** and report spend. Don't leave a GPU on.

---

## Existing files to reuse (now under `scripts/`)
- `scripts/runpod_setup.sh` — pod env + weights. Reuse as-is.
- `scripts/extract_fix.py` — UTF-8-correct unzip for Chinese names.
- `scripts/cat_audio_score.py` — **correct** model load / processor / generate / decode
  plumbing (forced-label-likelihood). **Adapt into MCQ**: keep the loading; swap the
  scoring loop for build-MCQ → generate → extract_answer.
- `scripts/metrics_report.py` — Wilson CIs, per-class P/R/F1, macro/weighted F1,
  per-source accuracy, confusion. **Generalize it to take the label set from the dataset
  config** (it currently hard-codes the 8 cat_corpus labels). Run once per dataset.
- `scripts/smoke_test.py` — single-clip sanity check.
- Paper PDF: `docs/papers/2605.09152v1.pdf`. Prior method review: `docs/eval_plan_review.md`.

---

## Implementation steps
1. Create a fresh RunPod pod; wait for runtime; set up the ssh alias.
2. scp `scripts/` + the three `data/` datasets to `/workspace`; run `runpod_setup.sh`;
   verify dataset counts (320 / 440 / 50).
3. Build `scripts/cat_audio_mcq.py`: a **config-driven** runner over the dataset registry.
   For each dataset → each clip: build shuffled MCQ, generate, `extract_answer`, record
   `dataset_id, clip_path, gold_label, pred_label, parse_status, source_hint, duration_s,
   truncated, raw_output, option_order`.
4. **Smoke first** per dataset (3 clips/class for cat_corpus & catmeows; all 50 for
   catsound_v2): confirm letters are extracted and predictions aren't degenerate. Then full runs.
5. Write per-dataset `outputs/artifacts/<id>/predictions_mcq.csv`; run the generalized
   `metrics_report.py` per dataset → `outputs/artifacts/<id>/metrics_mcq.json`.
6. Build the **overall summary** (`scripts` step or inline): one row per dataset.
7. **Stop the pod**; report spend.

---

## Metrics & outputs
**Per dataset** (`outputs/artifacts/<id>/`):
- `predictions_mcq.csv` — per clip: `dataset_id, clip_path, gold_label, pred_label (voted),
  vote_distribution, agreement (votes/K), parse_status, source_hint, duration_s, trimmed_duration_s,
  truncated, raw_output`.
- `metrics_mcq.json` + console: accuracy + **Wilson 95% CI**, **majority-class baseline**,
  per-class P/R/F1 (+recall CIs), **macro & weighted F1**, **per-source accuracy**,
  **parse_status breakdown**, **confusion matrix**, and a **letter-position-bias check**
  (the K shuffles already give this — is any letter slot over-picked?).
- **cat_corpus ablation table:** bare-MCQ → +definitions → +CoT → +self-consistency, accuracy at each.

**Overall** (`outputs/artifacts/summary.md` + `summary.json`): one row per dataset —
`dataset | N | #classes | chance | majority | accuracy [95% CI] | macro-F1 | best class | worst class | parse-fail%`.
Plus a short narrative. **No single pooled number** (taxonomies/chance differ); say so explicitly.

## Deferred (not in this run)
- **Group B (coarse taxonomy):** per-dataset, separate design pass — define a hand-reviewed
  fine→coarse map per dataset and re-score. Biggest accuracy lever but changes the task; do after
  we see the fine-grained Group-A numbers.
- **Group C (embeddings/prototype, fine-tuned audio classifier):** highest ceiling, different
  system, needs training data — out of scope for now.

## Cost note
Self-consistency K=5 ≈ 5× the generations (~4000 total across the 3 datasets, ~30–40 min on an
L40S). Use K=1 for smoke/ablation-of-other-boosters, K=5 for the final numbers. Stop the pod after.

## GPU sharing / throughput (applies to all experiments)
- **VRAM utilization ≠ compute utilization.** One Meow-Omni uses only ~40% of the 45 GB card — that
  spare *memory* lets you hold more models, it does NOT mean compute is idle. Judge headroom by
  `nvidia-smi` GPU-util, not the VRAM bar.
- **Small models (AST, CLAP, MFCC, AST-finetune) — stack them**: run several concurrently on one GPU
  instead of serially; there's ample room.
- **Do NOT load two Meow-Omni (18 GB) copies on one 45 GB card** — OOMs as KV cache grows, ~1.3× at
  best. The throughput lever for the big model is **batching clips**, not a second copy.
- Prefer adding **pods** (cheap, data is tiny) over cramming two big models onto one GPU.

---

## Success criteria / how to read it
- **cat_corpus (8-way, chance 12.5%):** does MCQ beat the **30.3% scoring baseline**, and
  recover classes scoring collapsed (caterwaul, meow, hiss, growl)? Is purr still strong?
- **catmeows (3-way context, majority 50.2%):** headline is **macro-F1 vs majority baseline**,
  not raw accuracy. Expect this to be hard (context ≠ audible) — beating majority at all is notable.
- **catsound_v2 (10-way, n=5/class):** exploratory only — report with the huge-CI caveat.
- **Mandatory honesty in the writeup:** per-source accuracy (the within-dataset confound),
  the **cross-dataset source overlap** between catsound_v2 and cat_corpus, parse-fail rates,
  single-source classes (chirrup/caterwaul), and catmeows imbalance.
- These are small, confounded "starter/verification" datasets and one model — report numbers
  with CIs and caveats; don't over-claim. More datasets are coming, so keep it config-driven.
