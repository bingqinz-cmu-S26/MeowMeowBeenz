"""Try a few prompt variants on a few clips (one model load) to see whether the
model can be coaxed into emitting a bare label vs. always describing."""
import sys, glob, numpy as np, librosa, torch
sys.path.insert(0, "/workspace/Meow-Omni-1")
from src.modeling_meow_omni_1 import MeowOmni1ForCausalLM
from src.processing_meow_omni_1 import MeowOmni1Processor

WEIGHTS = "/workspace/Meow-Omni-1-weights"
LABELS = ["chatter", "hiss", "chirrup", "nyaaan", "growl", "purr", "caterwaul", "meow"]
LIST = ", ".join(LABELS)

PROMPTS = {
    "P1_return_only": f"Listen to the cat audio and classify it as exactly one of: {LIST}. Return only the label.",
    "P2_one_word_strict": f"You are a strict classifier. Respond with EXACTLY ONE word chosen from this list and NOTHING else (no punctuation, no explanation): {LIST}.",
    "P3_single_token_q": f"Which single word from this list best matches the cat sound: {LIST}? Answer with only that one word.",
}

def to_dev(x, d="cuda"):
    if isinstance(x, torch.Tensor): return x.to(d)
    if isinstance(x, dict): return {k: to_dev(v, d) for k, v in x.items()}
    if isinstance(x, list): return [to_dev(v, d) for v in x]
    return x

def decode(o, tok):
    if isinstance(o, tuple) and o and isinstance(o[0], list) and o[0] and isinstance(o[0][0], str):
        return o[0][0]
    if hasattr(o, "sequences"): return tok.decode(o.sequences[0], skip_special_tokens=True)
    if isinstance(o, str): return o
    if isinstance(o, (list, tuple)) and o:
        return o[0] if isinstance(o[0], str) else tok.decode(o[0], skip_special_tokens=True)
    return str(o)

def classify(model, proc, audio, prompt):
    injected = "\n".join(["<audio>./</audio>", prompt])
    text = f"User: {injected}\nAssistant:"
    enc = proc(text=[text], images=None, audios=[audio], time_series_paths=None,
               time_series_sampling_rates=None, ids=["q"], return_tensors="pt")
    enc = dict(enc.data) if hasattr(enc, "data") else dict(enc.items())
    enc = to_dev(enc)
    bs = enc["input_ids"].shape[0]
    if enc.get("image_bound") is None:
        enc["image_bound"] = torch.zeros(bs, 0, 2, dtype=torch.long, device="cuda")
    gk = {"input_ids": enc["input_ids"], "attention_mask": enc.get("attention_mask"),
          "tokenizer": proc.tokenizer, "max_new_tokens": 12, "do_sample": False}
    for k in ["pixel_values", "tgt_sizes", "image_bound", "audio_features", "audio_feature_lens", "audio_bounds"]:
        if k in enc: gk[k] = enc[k]
    out = model.generate(**gk)
    t = decode(out, proc.tokenizer)
    if "Assistant:" in t: t = t.split("Assistant:")[-1]
    return t.strip()

def main():
    proc = MeowOmni1Processor.from_pretrained(WEIGHTS, trust_remote_code=True)
    model = MeowOmni1ForCausalLM.from_pretrained(WEIGHTS, trust_remote_code=True, torch_dtype=torch.bfloat16).to("cuda").eval()
    clips = []
    for lab in ["purr", "meow", "hiss"]:
        g = glob.glob(f"data/猫子语料/{lab}*/*.mp3")
        if g: clips.append((lab, sorted(g)[0]))
    for lab, path in clips:
        audio = librosa.load(path, sr=16000, mono=True)[0].astype(np.float32)[:480000]
        print(f"\n##### gold={lab}  ({path.split('/')[-1]})")
        for name, pr in PROMPTS.items():
            print(f"  [{name}] -> {classify(model, proc, audio, pr)!r}")

if __name__ == "__main__":
    main()
