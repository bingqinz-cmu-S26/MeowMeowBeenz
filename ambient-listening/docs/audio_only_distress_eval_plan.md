# Meow-Omni Audio-Only Folder-Label Evaluation Plan

## Goal

Evaluate whether Meow-Omni can classify the local cat-audio clips into the dataset's existing folder labels using audio only.

This plan is intentionally not about product alerts, distress notifications, pain detection, or deployment readiness. The only goal is to measure whether the model can map each clip to the correct dataset tab/class.

## Local Dataset

Dataset root:

```text
猫子语料/
```

The dataset is organized by folder label. Each folder contains 40 MP3 clips, for a total of 320 clips.

| Folder | Evaluation Label | Count | Avg Duration | Min | Max |
|---|---:|---:|---:|---:|---:|
| `chatter嘎嘎 兴奋捕猎状态` | `chatter` | 40 | 5.51s | 2.32s | 48.69s |
| `hiss哈气 defense` | `hiss` | 40 | 2.26s | 0.96s | 4.22s |
| `chirrup咕噜 交流` | `chirrup` | 40 | 3.08s | 1.23s | 6.05s |
| `nyaaan打架 暴怒` | `nyaaan` | 40 | 3.49s | 1.22s | 6.20s |
| `growl低吼 警告` | `growl` | 40 | 4.20s | 1.56s | 8.48s |
| `purr呼噜 舒适` | `purr` | 40 | 7.97s | 2.89s | 124.05s |
| `caterwaul老吴 cat-mate` | `caterwaul` | 40 | 4.27s | 2.12s | 7.88s |
| `meow喵 开心` | `meow` | 40 | 3.29s | 0.86s | 5.26s |

## Verified Facts (independent checks, do not re-litigate)

Three independent verification passes confirmed the following against the files on disk:

- **Counts/durations are exact.** 8 folders × 40 = 320 clips; all durations match the table above; all 320 decode cleanly.
- **Audio format is uniform:** 44.1 kHz, **stereo** MP3. Preprocessing must downmix to mono and resample (see Audio Preprocessing).
- **Source confound is a measured fact, not a hypothesis.** The dataset's own legend (`注释说明.PNG`) states: structured filenames (`<label><NN>_<age>_<sex>_<name>_<source>`) are self-recorded or YouTube clips; bare names (`catchatterNNN`, `Cat_HissNNNN`, `cat0N`, …) are web resource packs. Per-class source breakdown:
  - `chirrup`: **100% structured (YouTube)**
  - `caterwaul`: **100% structured** (≈75% YouTube, 25% recorded)
  - `hiss`, `nyaaan`, `meow`: **100% scraped packs**, each dominated by one scrape family
  - `chatter`, `growl`, `purr`: mixed (≈42–58% structured)
  - **Implication: source pattern ≈ label.** Per-source reporting and source-stratified splits are now MANDATORY, not optional (see Risks → Source Leakage).
- **Cat-identity overlap exists.** Named cats span multiple classes (白 in growl+chatter+purr; 娜 in chatter+purr; 琳 in caterwaul+purr). Any split must be grouped by `cat_hint` AND `source_hint`.
- **One malformed filename** in `growl`: `growl07_3M_F_白_recordedpurr17_3M_F_娜_recorded.mp3` (two names concatenated; audio is fine, it is the growl07/白 clip). Handle/rename before name-parsing.

## Key Corrections From Review

The review in `eval_plan_review.md` correctly points out that MeowBench is not the right benchmark for this task. MeowBench uses mostly locomotion/posture/maintenance labels, not the sound labels in this local dataset.

For this evaluation:

- Do not use MeowBench to claim accuracy on these eight sound classes.
- Do not collapse labels into product categories.
- Do not evaluate `distress`, `pain`, or `health_event`.
- Do not treat purr as proof of comfort or as proof of pain. Here, `purr` is only the dataset folder label.
- Do not report deployment-style confidence or alert reliability.

## Labels

Use exactly these eight labels for the first test:

```text
chatter
hiss
chirrup
nyaaan
growl
purr
caterwaul
meow
```

The Chinese folder names and descriptions are useful for human interpretation, but the model output should be normalized to the English label set above.

## Evaluation Question

Given one audio clip and the eight allowed labels, can Meow-Omni output the correct folder label?

This is a closed-set audio classification test.

Chance baseline:

```text
1 / 8 = 12.5%
```

Majority-class baseline:

```text
40 / 320 = 12.5%
```

Because the dataset is balanced, random and majority baselines are both 12.5%.

## Dataset Manifest

Create a manifest with one row per MP3.

Recommended fields:

```text
clip_id
audio_path
folder_name
label
duration_seconds
source_hint
cat_hint
split
```

Notes:

- `label` is derived from the parent folder.
- `source_hint` can be inferred from filenames when obvious, such as `youtube`, `recorded`, `flickr`, or `unknown`.
- `cat_hint` can be inferred only when filenames expose a repeated cat/person marker. Do not over-trust it.

## Splits

For the first zero-shot, single-prompt run, evaluate all 320 clips.

But **freeze the validation/test split now** (seeded, deterministic), so that the moment any tuning enters (the two-stage prompt, a confidence threshold, a parser alias map) there is no leakage and no temptation to pick the winner on the reported set:

- validation: 10 clips per class
- test: 30 clips per class

Split constraints (required, because of the measured confounds):

- **Group by `cat_hint`:** all clips from one named cat go to the same side of the split.
- **Stratify by `source_hint`:** keep each class's source mix as balanced as the data allows across val/test so the split itself doesn't amplify the source confound.
- The classes that are 100% single-source (`chirrup`, `caterwaul`) cannot be source-balanced — flag them explicitly; their numbers are source-confounded by construction.

Do not tune prompts on the same clips used for final reporting.

## Audio Preprocessing

Record preprocessing exactly.

Pinned first-pass settings (source files are uniformly 44.1 kHz stereo MP3):

- **Downmix to mono.**
- **Resample to 16 kHz** (the MiniCPM-o / Whisper-medium audio encoder expects 16 kHz). Confirm against the actual runtime once connected; if Meow-Omni's processor expects a different rate, match that and record it.
- Record the resampler and MP3 decoder used (decoders differ slightly; keep it deterministic).
- Preserve full clip for clips under the model's audio duration limit.
- For long clips, use the deterministic rule below.

Long-clip rule for first test:

- If a clip exceeds the model's practical audio window, evaluate the first 10 seconds.
- Also log that the clip was truncated.

Known duration outliers:

- `purr` has a max duration of 124.05s.
- `chatter` has a max duration of 48.69s.

These outliers should be tracked because truncation can affect accuracy.

## Scoring Path (read before Prompting)

Three of the eight labels — `nyaaan`, `chirrup`, `caterwaul` — are rare/idiosyncratic tokens a generic model may rarely emit free-form, while `meow`/`hiss`/`purr`/`growl` are common. Free-text generation therefore measures token familiarity as much as audio discrimination.

**Primary scoring = forced-label likelihood** (Confidence Option A below), whenever the runtime exposes per-token log-probs. The released Meow-Omni-1 is a local HuggingFace model, so this is available. Score all 8 labels under teacher forcing and pick the highest length-normalized sequence log-prob. This neutralizes the vocabulary confound.

**Secondary = free-text generation** with the prompt below, kept for interpretability and for any API-only runtime that cannot score. If only generation is available, that is a flagged limitation, not the intended primary result.

## Prompting

For the free-text (secondary) path, prompt Meow-Omni directly as a closed-set classifier.

Primary direct-label prompt:

```text
Listen to the cat audio and classify it as exactly one of:
chatter, hiss, chirrup, nyaaan, growl, purr, caterwaul, meow.

Return only the label.
```

Alternative two-stage prompt:

```text
Listen to the cat audio and briefly describe the cat sound.
Then classify it as exactly one of:
chatter, hiss, chirrup, nyaaan, growl, purr, caterwaul, meow.

Return JSON with keys: description, label.
```

**Pre-registration rule (avoid p-hacking):** the direct-label prompt is the single primary result, reported on the full set (or the frozen test split). The two-stage prompt is strictly exploratory — run it only on the validation split. Never select the headline number by comparing the two prompts on the reported set. If both must appear on test, use a paired McNemar test (same clips) and label two-stage as exploratory.

## Model Run

Run Meow-Omni with audio only.

Do not provide:

- video
- biometrics/time-series
- folder name
- filename-derived hints
- Chinese text from the folder name
- source label

Record:

```text
clip_id
audio_path
gold_label
prompt_version
model_version
generation_settings
raw_output
parsed_label
parse_status
duration_seconds
truncated
```

## Hosting Requirement

Yes: this evaluation needs hosted GPU inference if we want to test Meow-Omni itself.

The released Meow-Omni checkpoint is a HuggingFace custom-code model (`smgjch/Meow-Omni-1`, roughly 9B parameters). It is not a simple hosted API by default. Running it requires:

- CUDA GPU runtime.
- Enough VRAM for a 9B multimodal model; target at least 24 GB VRAM, with 40 GB safer.
- `trust_remote_code=True`.
- Model/code dependencies from the Meow-Omni repo and HuggingFace model card.
- Audio preprocessing before inference.

Do not plan to run Meow-Omni on a local laptop CPU for the 320-clip test. The correct path is a hosted GPU job or endpoint.

## RunPod-Backed Execution Path

Preferred hosting path:

```text
RunPod GPU Pod or Serverless endpoint
  -> load smgjch/Meow-Omni-1
  -> run audio-only evaluation over data/猫子语料/
  -> write outputs/artifacts/predictions.csv, outputs/artifacts/metrics.json, confusion_matrix.csv, eval_report.md
```

Use RunPod in one of two modes:

- **RunPod Pod + HTTP proxy:** fastest first path. Run a model server on the Pod, expose its HTTP port, and call it through `https://{pod_id}-{port}.proxy.runpod.net`.
- **RunPod Serverless:** cleaner endpoint path. Deploy a queue-based worker and call `https://api.runpod.ai/v2/{endpoint_id}/runsync` with `{"input": ...}`.

Minimum RunPod requirement:

```text
We need a hosted GPU environment capable of running HuggingFace custom-code model smgjch/Meow-Omni-1 for batch inference over 320 short MP3 clips.
```

Fallback if Meow-Omni hosting is blocked:

1. Run Qwen/MiniMax/MOSS-Audio API baselines on the same dataset.
2. Report those as sponsor-model baselines, not Meow-Omni results.
3. Keep the Meow-Omni result pending until a GPU host is available.

## Output Parsing

Normalize raw text to one of the eight labels.

Accepted labels:

```text
chatter
hiss
chirrup
nyaaan
growl
purr
caterwaul
meow
```

Parsing rules:

- Lowercase output.
- Strip whitespace and punctuation.
- Accept exact label matches.
- Accept obvious casing variants.
- If output contains multiple labels, mark `parse_status=ambiguous` and count it as incorrect unless a predeclared parser rule resolves it.
- If output is not one of the allowed labels, mark `parse_status=invalid` and count it as incorrect.

Do not silently map free-form guesses to labels after seeing the answer.

## Metrics

Report:

- Overall accuracy.
- Per-class precision.
- Per-class recall.
- Per-class F1.
- Macro F1.
- Weighted F1.
- Confusion matrix.
- Parse failure rate (per class — a class with high invalid rate is a vocabulary artifact, not a discrimination failure).
- **Accuracy by source hint (MANDATORY).** Report per-class accuracy split by structured vs scraped source. If a class scores high but is single-source, say so — that number is source-confounded.
- Accuracy on truncated vs non-truncated clips, **per affected class** (`purr` and `chatter` are the long ones, so truncation is class-correlated).
- **Two accuracies for the generation path:** strict (invalid/ambiguous = wrong; the headline) and a diagnostic "accuracy among parseable outputs."

### Required statistics (n is small — 40/class, 320 total)

- **Wilson 95% CIs** (not normal-approximation) on overall accuracy and every per-class precision/recall.
- **Bootstrap CI** (≥1000 resamples over clips) for macro-F1.
- Report `n` next to every rate.
- **Do not claim an interpretation band unless its CI clears the band boundary.** The bands below are coarser than the per-class CIs, so treat them as rough overall-accuracy guidance only.

### Human audio-only ceiling (do this once, early)

Folder labels encode emotional/behavioral context (excited-hunting, comfort, rage), not pure acoustic classes, so 100% audio-only accuracy is not achievable even in principle. Have one person re-label ~40 clips (5/class), audio-only, choosing from the 8 labels. **This human audio-only accuracy is the realistic ceiling and the honest comparison point — report the model against it, not only against 12.5% chance.**

Because the dataset is balanced, overall accuracy is meaningful, but per-class metrics are still necessary.

## Confidence

For this first test, confidence is optional.

If confidence is measured, do not assume the generated text probability is calibrated.

Preferred confidence methods:

### Option A: Forced Label Likelihood

Score each of the eight candidate labels under the model and choose the highest length-normalized sequence likelihood.

This avoids penalizing labels with more tokens or characters.

### Option B: Sampling Agreement

Run each clip multiple times with stochastic decoding and measure agreement.

Example:

- 10 generations
- count labels
- compute agreement rate and predictive entropy

Before using sampling agreement as confidence, verify on a validation split that agreement correlates with correctness.

## Result Interpretation

A successful result means Meow-Omni can classify these eight dataset labels from audio with accuracy meaningfully above the 12.5% baseline.

Suggested interpretation bands for this dataset only:

- `<25%`: weak; likely not useful for these labels.
- `25-50%`: above chance but unreliable.
- `50-70%`: useful signal, but class confusion needs inspection.
- `70-85%`: strong zero-shot result.
- `>85%`: very strong on this dataset; still verify for leakage/source confounds.

These bands are not deployment claims. They only describe performance on this folder-labeled dataset.

## Risks and Controls

### Source Leakage (confirmed severe — see Verified Facts)

This is the single biggest threat to validity. It is measured, not hypothetical: `chirrup` and `caterwaul` are 100% single-source; `hiss`/`nyaaan`/`meow` are 100% scraped. Source pattern ≈ label, so a model can score well without acoustic understanding.

Controls (required):

- Report per-class accuracy split by source bucket (structured vs scraped) — mandatory in the report.
- Group splits by `cat_hint` and stratify by `source_hint` (see Splits).
- Explicitly caveat `chirrup`/`caterwaul` numbers as source-confounded by construction.
- When future datasets arrive, prefer ones that break this confound (same sound class drawn from multiple sources) so the confound can be measured out.

### Clip Quality and Background Noise

Internet-sourced clips may contain music, speech, compression artifacts, or other animals.

Control:

- Track obvious noisy clips.
- Inspect errors manually.

### Long Clip Truncation

Long clips may contain silence or multiple sound events. Truncation can change the label evidence.

Control:

- Report truncated-clip accuracy separately.
- Consider sliding-window classification for long clips in a later test.

### Prompt Sensitivity

Text-output models can be sensitive to label wording.

Control:

- Freeze one prompt for the first test.
- Only compare alternate prompts on a validation split.

## Expected Outputs

The test should produce:

```text
outputs/artifacts/manifest.csv
outputs/artifacts/predictions.csv
outputs/artifacts/metrics.json
confusion_matrix.csv
eval_report.md
```

Minimum report contents:

- total clips evaluated
- class counts
- prompt used
- model version
- preprocessing settings
- overall accuracy
- macro F1
- per-class precision/recall/F1
- confusion matrix
- top observed confusions
- parse failure rate
- notes on source/truncation issues

## Extensibility (more datasets are coming)

This is a starter dataset; the harness must accept new datasets/label sets without code edits. Generalize three things now:

- **Dataset config / label registry** — one source of truth per dataset: `{label, folder_glob, aliases[], canonical_token, source_regex}`. Manifest, prompt, parser, and metrics all read from it.
- **Prompt-from-label-set** — build the classifier prompt by joining the registry's labels; never hand-type the label list into the prompt string.
- **Dataset-agnostic outputs** — add `dataset_id` and `n_classes` to the manifest and prediction store so multiple datasets coexist. Compute the chance baseline as `1 / n_classes`, not a hard-coded 12.5%.

## Implementation Target (for codex)

Planner→implementor handoff. The model **does appear to be released** (verified that the pages exist; not yet load-verified — treat the first run as a validation step):

- **Most faithful path:** `smgjch/Meow-Omni-1` on HuggingFace (~18 GB, Apache-2.0) + the GitHub repo `github.com/smgjch/Meow-Omni-1`, which ships `src/evaluation/eval_meow.py`. Backbone is MiniCPM-o 4.5 + a transplanted Intern-S1-Pro time-series encoder. Reuse/strip `eval_meow.py` to audio-only.
- **Audio-only message construction is undocumented** — all published examples are quad-modal/video. Read `processing_meow_omni_1.py` to confirm the chat template tolerates absent modalities, then pass `audios=[arr]` and omit image/time-series args. The paper says absent modalities are simply omitted, so this is architecturally supported.
- **Runtime requirements (NOT Mac-local):** CUDA, **≥24 GB VRAM**, `trust_remote_code=True`, likely `transformers==4.51.0` (MiniCPM-o pin). Use a hosted/rented GPU (one 24–40 GB card is plenty). Inference over 320 short clips is minutes. The 8×H200 in the paper was for training only.
- **Confirm at connect time:** does the inference path expose per-token log-probs / teacher-forced scoring? This determines whether the primary forced-label-likelihood scoring (see Scoring Path) is available. For a local HF model it should be.
- **Decoding:** greedy / temperature 0 for the headline run (matches the paper). Log all generation settings.
- **Fallback if the checkpoint misbehaves:** `openbmb/MiniCPM-o-4_5` (same backbone family, documented `model.chat` audio path, 16 kHz mono) — runnable, loses the feline fine-tuning, good as a smoke-test baseline. Last resort: generic audio taggers (AST/BEATs/PANNs/YAMNet) feeding a text LLM.

Once the runner exists and the log-prob question is answered, this dataset is ready for the first closed-set audio-only evaluation.
