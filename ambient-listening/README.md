# ambient-listening

Cat-audio data collection and evaluation workspace for MeowMeowBeenz — scripts for capturing, labeling, and scoring cat vocalizations (AST probes, frontier APIs, Meow-Omni MCQ).

## Layout

- `scripts/` - runnable evaluation, scoring, setup, and utility scripts
- `docs/` - evaluation notes and reference papers
- `data/猫子语料/` - local raw cat-audio corpus
- `data/catmeows/` - CatMeows verification dataset
- `data/catsound_v2/` - CatSound V2 verification dataset
- `outputs/artifacts/` - generated manifests, predictions, metrics, and reports

## MCQ evaluation

Run on a GPU pod after `scripts/runpod_setup.sh` has installed Meow-Omni and weights under `/workspace`.

Smoke-sized run with the final Group-A prompt settings:

```bash
python scripts/cat_audio_mcq.py --dataset cat_corpus --per-class 3 --definitions --cot --k 1
python scripts/cat_audio_mcq.py --dataset catmeows --per-class 3 --definitions --cot --k 1
python scripts/cat_audio_mcq.py --dataset catsound_v2 --definitions --cot --k 1
```

Full Group-A run with self-consistency:

```bash
python scripts/cat_audio_mcq.py --dataset all --definitions --cot --k 5
python scripts/metrics_report.py --all
python scripts/summary_report.py
```

cat_corpus ablation ladder:

```bash
python scripts/cat_audio_mcq.py --ablate-cat-corpus
python scripts/metrics_report.py --ablation-table
```

Per-dataset outputs are written to `outputs/artifacts/<dataset_id>/`. The cross-dataset summary is written to `outputs/artifacts/summary.md` and `outputs/artifacts/summary.json`.

## Previous forced-label scoring

```bash
python scripts/cat_audio_score.py --per-class 0 --out outputs/artifacts/predictions.csv
python scripts/metrics_report.py --dataset cat_corpus --pred outputs/artifacts/predictions.csv --out outputs/artifacts/cat_corpus
```

RunPod setup script:

```bash
bash scripts/runpod_setup.sh
```
