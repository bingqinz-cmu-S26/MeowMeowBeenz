"""
Acceptance gate: confirm Meow-Omni-1 loads and emits a sane label for ONE clip.

Loads via the repo's src classes (the MiniCPMO-based MeowOmni1ForCausalLM that has
.generate), NOT the HF auto_map weights version (which inherits Qwen3PreTrainedModel
and lacks .generate). This mirrors src/evaluation/eval_meow.py exactly.

Usage (run from anywhere on the pod):  python smoke_test.py <clip.mp3>
"""
import sys
import numpy as np
import librosa
import torch

REPO = "/workspace/Meow-Omni-1"
WEIGHTS = "/workspace/Meow-Omni-1-weights"
sys.path.insert(0, REPO)
from src.modeling_meow_omni_1 import MeowOmni1ForCausalLM
from src.processing_meow_omni_1 import MeowOmni1Processor

LABELS = ["chatter", "hiss", "chirrup", "nyaaan", "growl", "purr", "caterwaul", "meow"]
PROMPT = (
    "Listen to the cat audio and classify it as exactly one of: "
    + ", ".join(LABELS)
    + ". Return only the label."
)


def to_dev(x, dev):
    if isinstance(x, torch.Tensor):
        return x.to(dev)
    if isinstance(x, dict):
        return {k: to_dev(v, dev) for k, v in x.items()}
    if isinstance(x, list):
        return [to_dev(v, dev) for v in x]
    return x


def main(clip):
    print(f"loading audio: {clip}")
    audio, _ = librosa.load(clip, sr=16000, mono=True)  # source is 44.1k stereo -> 16k mono
    audio = audio.astype(np.float32)[:480000]

    print("loading processor + model (bf16, cuda)...")
    proc = MeowOmni1Processor.from_pretrained(WEIGHTS, trust_remote_code=True)
    model = MeowOmni1ForCausalLM.from_pretrained(
        WEIGHTS, trust_remote_code=True, torch_dtype=torch.bfloat16
    ).to("cuda").eval()

    injected = "\n".join(["<audio>./</audio>", PROMPT])
    prompt = f"User: {injected}\nAssistant:"

    enc = proc(
        text=[prompt], images=None, audios=[audio],
        time_series_paths=None, time_series_sampling_rates=None,
        ids=["smoke"], return_tensors="pt",
    )
    enc = dict(enc.data) if hasattr(enc, "data") else dict(enc.items())
    enc = to_dev(enc, "cuda")
    bs = enc["input_ids"].shape[0]
    if enc.get("image_bound") is None:
        enc["image_bound"] = torch.zeros(bs, 0, 2, dtype=torch.long, device="cuda")
    if not enc.get("audio_feature_lens"):
        enc["audio_feature_lens"] = [torch.tensor([0], device="cuda") for _ in range(bs)]
    if not enc.get("audio_bounds"):
        enc["audio_bounds"] = [[] for _ in range(bs)]

    input_len = enc["input_ids"].shape[1]
    gen_kwargs = {
        "input_ids": enc["input_ids"],
        "attention_mask": enc.get("attention_mask"),
        "tokenizer": proc.tokenizer,
        "max_new_tokens": 16,
        "do_sample": False,
    }
    for k in ["pixel_values", "tgt_sizes", "image_bound", "audio_features", "audio_feature_lens", "audio_bounds"]:
        if k in enc:
            gen_kwargs[k] = enc[k]

    output = model.generate(**gen_kwargs)
    print("DEBUG output type:", type(output), "->", repr(output)[:200])

    tok = proc.tokenizer

    def robust_decode(o):
        if hasattr(o, "sequences"):
            return tok.decode(o.sequences[0], skip_special_tokens=True)
        if isinstance(o, torch.Tensor):
            return tok.decode(o[0] if o.ndim > 1 else o, skip_special_tokens=True)
        if isinstance(o, str):
            return o
        if isinstance(o, (list, tuple)) and len(o) > 0:
            first = o[0]
            if isinstance(first, str):
                return first
            if isinstance(first, torch.Tensor):
                return tok.decode(first[0] if first.ndim > 1 else first, skip_special_tokens=True)
            return str(first)
        return str(o)

    txt = robust_decode(output)
    if "Assistant:" in txt:
        txt = txt.split("Assistant:")[-1]

    print("\n=== RAW MODEL OUTPUT ===")
    print(repr(txt.strip()))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python smoke_test.py <clip.mp3>"); sys.exit(1)
    main(sys.argv[1])
