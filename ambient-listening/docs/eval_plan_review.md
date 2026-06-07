# Review: Audio-Only Cat Distress Validation Pipeline

Reviewed against `audio_only_distress_eval_plan.md` (revised, "Audio-Only Cat
Distress Validation Pipeline") and the Meow-Omni 1 paper (`docs/papers/2605.09152v1.pdf`).

## Verdict

The revision is a major improvement and absorbed the prior review correctly: it
pivots off MeowBench, demotes it to a pipeline sanity check, acknowledges the
locomotion/posture taxonomy, adds random/majority/abstain baselines, separates
accuracy from high-confidence precision, and adds a dedicated-classifier
fallback. The methodology is now largely honest and correct.

The remaining risk has **shifted from "wrong benchmark" to "the metrics, as
specified, will look better than reality."** Balanced-set base rates,
clip-vs-stream framing, the purr aliasing, and unquantified decision gates can
each turn a passing evaluation into a product that misfires in the home. Fix #1,
#2, and #6 below before treating any number from this pipeline as a ship signal.

---

## Critical (invalidates the product claim even if every step executes)

### 1. The plan is blocked on a dataset that may not exist — and "distress" proxies likely aren't product distress

The pipeline assumes a labeled distress set will appear later but names no source
and never checks feasibility. The realistic public candidates (CatMeows /
Ntalampiras [7], Freesound, `taozi555/cat_class`) are dominated by **mild context
labels** — brushing, *isolation*, waiting-for-food — plus staged/dubbed Freesound
"fight" clips. The plan's own mapping example does `isolation distress ->
distress`. But "cat alone in an unfamiliar room" is **not** veterinary distress or
pain. So the `distress` positives would largely be a construct proxy that doesn't
represent the actual product event (a sick or in-pain cat at home), and precision
measured against that gold won't transfer to deployment.

**Action:** add an explicit feasibility gate before the pipeline runs — *does any
obtainable data contain genuine distress/pain positives, and how many?* If the
answer is "only isolation/fight proxies," say so and scope the claim down to what
those proxies actually support.

### 2. Per-clip metrics ignore the two hardest deployment problems: base rate and streaming

**Base-rate shift.** Distress in a real home is rare (perhaps one event per many
hours). Precision on a balanced eval set massively overstates deployed precision —
a model at 90% eval-precision can produce mostly false alarms once the real prior
collapses. The plan reports per-clip false-positive rate, but FPR is not the
deployed false-alert rate, and the prior version's **"false alerts per hour/day"**
metric was *dropped* in this rewrite. That per-time false-alarm number is the
single most decision-relevant figure for an always-on app.

**Streaming / detection gap.** The dataset is pre-segmented clean clips;
deployment is continuous audio that needs VAD + "is there even a cat sound here"
event detection *before* classification. The pipeline evaluates
classification-given-a-clean-clip and silently assumes detection away. Perfect
clip metrics will not predict product behaviour.

**Action:** report precision at a realistic deployment base rate (prior-adjusted),
and report (or at least design for) alerts-per-hour on continuous unlabeled audio.
Make the streaming/detection stage an explicit out-of-scope note rather than an
implicit assumption.

### 3. Mapping `purr -> comfort_affiliation` hard-codes the benign reading of the paper's flagship aliasing example

The paper's central motivation is that a purr can mean contentment **or** pain /
respiratory distress (§1, "semantic aliasing"). For a distress-detection product,
confidently labeling purr as comfort is exactly the failure mode that gets a sick
cat missed. Audio-only, purr should lean `unknown` / ambiguous, not `comfort`.

---

## Significant (metrics will be misleading or unquantified)

### 4. `unknown` plays three incompatible roles with no scoring policy

`unknown` is simultaneously a prompt option the model emits, a gold label, and a
baseline. The plan never defines: is gold-`unknown` predicted `unknown` a "correct
classification" (which inflates accuracy)? Is predicting `unknown` on a true
distress clip a misclassification, or an abstention (a missed alert)?

**Action:** define abstention as a **coverage** cost separate from
misclassification, and report **selective accuracy + coverage** rather than a
blended accuracy that an always-`unknown` model can game.

### 5. Both confidence options are under-specified for this task

- **Option A (token logits):** a label like `hunger_attention` is several tokens,
  so you need a length-normalized sequence log-prob per candidate label via
  constrained / forced scoring of each option — not "the softmax score." The plan
  glosses this; without length normalization the longer label names are penalized.
- **Option B (sampling agreement):** the output is a forced single short label, so
  a confidently-wrong model agrees 10/10 precisely when it is wrong. Agreement
  measures sampling stochasticity, not correctness, and over a 6-way label it is
  too coarse (only ~11 levels) for smooth calibration bands.

**Action:** for Option B, **validate on the val set that agreement actually
correlates with correctness** before trusting it as confidence; otherwise it is an
overconfidence generator. For Option A, specify per-option length-normalized
likelihood scoring.

### 6. Every acceptance bar is a non-number

"High-confidence distress precision is high," "FPR low enough," "reasonable macro
F1" are all unquantified. For a document whose purpose is rigor, the ship / no-ship
gates must be numeric **and** carry a minimum-N / confidence interval. "Tens of
distress positives" yields a precision 95% CI of roughly ±15–18 points — wide
enough that a lucky point estimate could trip a ship decision.

**Action:** state the numeric precision threshold, the minimum number of distress
positives, and the CI requirement that the estimate must clear.

---

## Worth fixing

### 7. Source confound / leakage beyond `cat_id`

Pulling distress from one source and normals from another lets the model learn the
**recording domain** rather than the cat's state. The split rule covers cat /
session leakage but not source leakage. Stratify by source, ensure each product
class spans multiple sources, and report per-source performance.

### 8. The direct-label prompt is off-distribution for how the model was trained

Per the paper (Appendix A.3), Meow-Omni was trained to **not** emit an intent label
from standalone audio — it produces a caption. Forcing "return only the label" is
off-distribution for its audio branch. A two-stage **caption → map-to-label**
approach may align better with the model; worth A/B-ing against the direct prompt.

### 9. `health_event` (cough/gag/vomit) feasibility is even worse than distress

Cat-vocalization datasets are meow-centric and will have near-zero cough / vomit
positives. The plan treats `health_event` as co-equal with `distress` for
alerting; it should be down-scoped or given its own dedicated data source, with a
stated minimum-N.

### 10. Audio preprocessing is "recorded" but not "matched"

Sample rate, mono, and clip length must match the encoder's training regime
(WavLM-based audio stream, AudioSet / AST verification rates) or zero-shot degrades
silently. Specify the target preprocessing, don't just log whatever was used.

---

## What the plan now gets right

- Correctly treats MeowBench as a plumbing check (reproduce 51.88%), not a
  distress metric.
- Separates accuracy from high-confidence precision, and refuses overall-accuracy-
  only reporting.
- Adds random, majority-class, and always-`unknown` baselines.
- `unknown` / abstention as a product feature; precision-over-recall for alerts.
- Validation-then-frozen-test discipline and a fallback to a dedicated audio
  classifier (AST / BEATs / PANNs / YAMNet) if Meow-Omni underperforms.
- Empirical, non-medical alert wording.

---

## Bottom line

The methodology is sound. The danger is now optimistic *measurement*: the numbers
this pipeline produces will look better than the deployed product unless you (1)
confirm real distress positives exist, (2) report base-rate-adjusted precision and
per-hour false alerts on streaming audio, and (3) set numeric, CI-backed ship
gates. Until then, treat every output as a lower bound on difficulty, not evidence
of readiness.
