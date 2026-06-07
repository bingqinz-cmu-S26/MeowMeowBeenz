#!/usr/bin/env bash
# Run this ON the RunPod pod (web terminal or SSH), not on your Mac.
# It installs deps, clones the model repo, and downloads the weights.
set -euo pipefail

# /workspace is RunPod's persistent volume - keep weights here so a pod
# restart doesn't force an 18GB re-download.
cd /workspace

echo "== system deps =="
apt-get update -y && apt-get install -y git ffmpeg libsndfile1 unzip

echo "== clone model repo =="
if [ -d Meow-Omni-1 ]; then (cd Meow-Omni-1 && git pull); else git clone https://github.com/smgjch/Meow-Omni-1.git; fi
cd Meow-Omni-1

echo "== python deps (repo pins transformers==4.57.6, decord, soundfile) =="
pip install --upgrade pip
pip install -r requirements.txt
# audio + download helpers we'll need regardless
pip install soundfile librosa "huggingface_hub[cli]"

echo "== download weights (Apache-2.0, public) to a persistent path =="
huggingface-cli download smgjch/Meow-Omni-1 --local-dir /workspace/Meow-Omni-1-weights

echo
echo "DONE."
echo "Next, from this repo directory on the Pod, run:"
echo "  python scripts/smoke_test.py /path/to/one_clip.mp3"
echo
echo "If smoke_test.py works, start the HTTP server:"
echo "  PORT=8000 python scripts/cat_audio_runpod.py server"
echo
echo "Then call it through:"
echo "  https://<pod-id>-8000.proxy.runpod.net/classify"
