"""Provider adapters for frontier multimodal audio classification."""
import abc
import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
import wave


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def usage_to_dict(usage):
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "dict"):
        return usage.dict()
    return {k: getattr(usage, k) for k in dir(usage) if k.endswith("tokens")}


class Provider(abc.ABC):
    name = ""
    model = ""
    env = ""
    accepts_audio = True
    price_per_1m_input_tokens = 0.0
    price_per_1m_output_tokens = 0.0
    price_per_1m_audio_input_tokens = 0.0
    preferred_sample_rate = 16000
    max_requests_per_minute = 0

    def __init__(self, model, env, name=None, accepts_audio=True):
        self.model = model
        self.env = env
        self.name = name or model
        self.accepts_audio = accepts_audio

    def has_key(self):
        return bool(os.getenv(self.env))

    def missing_reason(self):
        if not self.accepts_audio:
            return f"{self.name} is registered as accepts_audio=False"
        if not self.has_key():
            return f"missing {self.env}"
        return ""

    @abc.abstractmethod
    def classify(self, audio_wav_bytes, sr, prompt):
        """Return {"raw": str, "usage": dict, "latency_s": float}."""

    def estimate_cost(self, usage):
        usage = usage or {}
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        input_audio_tokens = 0
        output_audio_tokens = 0
        details = usage.get("prompt_tokens_details") or usage.get("input_token_details") or {}
        if isinstance(details, dict):
            input_audio_tokens = details.get("audio_tokens") or details.get("audio") or 0
        details = usage.get("completion_tokens_details") or usage.get("output_token_details") or {}
        if isinstance(details, dict):
            output_audio_tokens = details.get("audio_tokens") or details.get("audio") or 0
        return (
            input_tokens * self.price_per_1m_input_tokens
            + output_tokens * self.price_per_1m_output_tokens
            + input_audio_tokens * self.price_per_1m_audio_input_tokens
            + output_audio_tokens * getattr(self, "price_per_1m_audio_output_tokens", 0.0)
        ) / 1_000_000


class OpenAIAudioProvider(Provider):
    price_per_1m_input_tokens = 2.50
    price_per_1m_output_tokens = 10.00
    price_per_1m_audio_input_tokens = 32.00
    price_per_1m_audio_output_tokens = 64.00

    def classify(self, audio_wav_bytes, sr, prompt):
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv(self.env))
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=self.model,
            modalities=["text", "audio"],
            audio={"voice": "alloy", "format": "wav"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(audio_wav_bytes).decode("ascii"),
                                "format": "wav",
                            },
                        },
                    ],
                }
            ],
            max_completion_tokens=96,
        )
        message = response.choices[0].message
        raw = message.content or ""
        audio = getattr(message, "audio", None)
        if not raw and audio is not None:
            raw = getattr(audio, "transcript", "") or ""
            if not raw and isinstance(audio, dict):
                raw = audio.get("transcript", "") or ""
        usage = usage_to_dict(getattr(response, "usage", None))
        return {"raw": raw, "usage": usage, "latency_s": time.perf_counter() - started}


class OpenAIRealtime2Provider(OpenAIAudioProvider):
    price_per_1m_input_tokens = 4.00
    price_per_1m_output_tokens = 24.00
    price_per_1m_audio_input_tokens = 32.00
    price_per_1m_audio_output_tokens = 64.00
    preferred_sample_rate = 24000

    def classify(self, audio_wav_bytes, sr, prompt):
        import websocket

        started = time.perf_counter()
        with wave.open(io.BytesIO(audio_wav_bytes), "rb") as wav:
            pcm = wav.readframes(wav.getnframes())
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        ws = websocket.create_connection(
            url,
            header=[
                f"Authorization: Bearer {os.getenv(self.env)}",
                "OpenAI-Safety-Identifier: cat-audio-eval",
            ],
            timeout=30,
        )
        try:
            ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "instructions": "You classify cat audio. Do not explain your reasoning. Output only the requested Answer and Confidence lines.",
                    "output_modalities": ["text"],
                    "audio": {"input": {"format": {"type": "audio/pcm", "rate": sr}}},
                },
            }))
            ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_audio", "audio": base64.b64encode(pcm).decode("ascii")},
                    ],
                },
            }))
            ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "instructions": "Output exactly two lines and no other text: Answer: X and Confidence: Y.",
                    "max_output_tokens": 200,
                },
            }))
            chunks = []
            final_texts = []
            usage = {}
            while True:
                event = json.loads(ws.recv())
                etype = event.get("type")
                if etype == "response.output_text.delta":
                    chunks.append(event.get("delta", ""))
                elif etype == "response.output_text.done":
                    if event.get("text"):
                        final_texts.append(event.get("text"))
                elif etype in {"response.content_part.done", "response.output_item.done"}:
                    text = extract_text(event)
                    if text:
                        final_texts.append(text)
                elif etype == "response.done":
                    usage = ((event.get("response") or {}).get("usage") or {})
                    text = extract_text(event.get("response") or {})
                    if text:
                        final_texts.append(text)
                    break
                elif etype == "error":
                    raise RuntimeError(json.dumps(event.get("error") or event, ensure_ascii=False))
            raw = final_texts[-1] if final_texts else "".join(chunks)
            return {"raw": raw, "usage": usage, "latency_s": time.perf_counter() - started}
        finally:
            ws.close()


class GeminiProvider(Provider):
    price_per_1m_input_tokens = 0.0
    price_per_1m_output_tokens = 0.0

    def estimate_cost(self, usage):
        usage = usage or {}
        prompt_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("totalTokenCount", 0) - prompt_tokens
        return (
            prompt_tokens * self.price_per_1m_input_tokens
            + max(0, output_tokens) * self.price_per_1m_output_tokens
        ) / 1_000_000

    def classify(self, audio_wav_bytes, sr, prompt):
        started = time.perf_counter()
        generation_config = {
            "maxOutputTokens": 256,
            "temperature": 0,
        }
        if "flash" in self.model:
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "audio/wav",
                                "data": base64.b64encode(audio_wav_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": generation_config,
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={os.getenv(self.env)}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            retry_after = exc.headers.get("Retry-After")
            if exc.code == 429:
                retry_hint = retry_after or extract_gemini_retry_delay(body)
                raise RuntimeError(f"Gemini HTTP 429 retry_after={retry_hint or ''}: {body[:500]}") from exc
            raise RuntimeError(f"Gemini HTTP {exc.code}: {body[:500]}") from exc
        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
        raw = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict))
        return {"raw": raw, "usage": data.get("usageMetadata") or {}, "latency_s": time.perf_counter() - started}


class QwenOmniProvider(Provider):
    base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    def classify(self, audio_wav_bytes, sr, prompt):
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv(self.env), base_url=self.base_url)
        started = time.perf_counter()
        stream = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": f"data:;base64,{base64.b64encode(audio_wav_bytes).decode('ascii')}",
                                "format": "wav",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            modalities=["text", "audio"],
            audio={"voice": "Ethan", "format": "wav"},
            max_tokens=96,
            stream=True,
            stream_options={"include_usage": True},
        )
        chunks = []
        usage = {}
        for chunk in stream:
            if getattr(chunk, "choices", None):
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    chunks.append(content)
            else:
                usage = usage_to_dict(getattr(chunk, "usage", None))
        return {"raw": "".join(chunks), "usage": usage, "latency_s": time.perf_counter() - started}


class QwenWorkspaceProvider(QwenOmniProvider):
    def __init__(self, model, env, workspace_env, region_host, name=None):
        super().__init__(model=model, env=env, name=name)
        self.workspace_env = workspace_env
        self.region_host = region_host

    @property
    def base_url(self):
        workspace_id = os.getenv(self.workspace_env, "").strip()
        if not workspace_id:
            return ""
        return f"https://{workspace_id}.{self.region_host}/compatible-mode/v1"

    def missing_reason(self):
        if not self.accepts_audio:
            return f"{self.name} is registered as accepts_audio=False"
        if not self.has_key():
            return f"missing {self.env}"
        if not os.getenv(self.workspace_env):
            return f"missing {self.workspace_env}"
        return ""


class QwenOmniChinaProvider(QwenOmniProvider):
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class QwenOmniUSProvider(QwenOmniProvider):
    base_url = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"


class MiniMaxAudioProvider(Provider):
    base_url = "https://api.minimax.io/v1/chat/completions"
    price_per_1m_input_tokens = 1.00
    price_per_1m_output_tokens = 8.00

    def classify(self, audio_wav_bytes, sr, prompt):
        payload = {
            "model": self.model,
            "thinking": {"type": "disabled"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(audio_wav_bytes).decode("ascii"),
                                "format": "wav",
                            },
                        },
                    ],
                }
            ],
            "max_completion_tokens": 96,
        }
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {os.getenv(self.env)}", "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"MiniMax HTTP {exc.code}: {body[:500]}") from exc
        message = (data.get("choices") or [{}])[0].get("message") or {}
        return {
            "raw": message.get("content") or "",
            "usage": data.get("usage") or {},
            "latency_s": time.perf_counter() - started,
        }


class UnsupportedAudioProvider(Provider):
    def classify(self, audio_wav_bytes, sr, prompt):
        raise RuntimeError(self.missing_reason())


load_dotenv()


def extract_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for part in (extract_text(item) for item in value) if part)
    if not isinstance(value, dict):
        return ""
    texts = []
    for key in ("text", "transcript"):
        if isinstance(value.get(key), str):
            texts.append(value[key])
    for key in ("content", "parts", "output"):
        nested = extract_text(value.get(key))
        if nested:
            texts.append(nested)
    return "\n".join(texts)


def extract_gemini_retry_delay(body):
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return ""
    for detail in (data.get("error") or {}).get("details") or []:
        if isinstance(detail, dict) and "retryDelay" in detail:
            return str(detail["retryDelay"])
    return ""

PROVIDERS = {
    "gpt-audio": OpenAIAudioProvider(model="gpt-audio", env="OPENAI_API_KEY", name="gpt-audio"),
    "gpt-audio-1.5": OpenAIAudioProvider(model="gpt-audio-1.5", env="OPENAI_API_KEY", name="gpt-audio-1.5"),
    "gpt-4o-audio": OpenAIAudioProvider(model="gpt-4o-audio-preview", env="OPENAI_API_KEY", name="gpt-4o-audio"),
    "gpt-5.5": UnsupportedAudioProvider(model="gpt-5.5", env="OPENAI_API_KEY", name="gpt-5.5", accepts_audio=False),
    "gpt-realtime": OpenAIAudioProvider(model="gpt-realtime", env="OPENAI_API_KEY", name="gpt-realtime"),
    "gpt-realtime-2": OpenAIRealtime2Provider(model="gpt-realtime-2", env="OPENAI_API_KEY", name="gpt-realtime-2"),
    "gemini-2.5-pro": GeminiProvider(model="gemini-2.5-pro", env="GEMINI_API_KEY", name="gemini-2.5-pro"),
    "gemini-3-pro": GeminiProvider(model="gemini-3-pro-preview", env="GEMINI_API_KEY", name="gemini-3-pro"),
    "gemini-3-flash": GeminiProvider(model="gemini-3-flash-preview", env="GEMINI_API_KEY", name="gemini-3-flash"),
    "gemini-3.1-pro": GeminiProvider(model="gemini-3.1-pro-preview", env="GEMINI_API_KEY", name="gemini-3.1-pro"),
    "gemini-3.5-flash": GeminiProvider(model="gemini-3.5-flash", env="GEMINI_API_KEY", name="gemini-3.5-flash"),
    "minimax-3": UnsupportedAudioProvider(model="MiniMax-M3", env="MINIMAX_API_KEY", name="minimax-3", accepts_audio=False),
    "minimax-m3": UnsupportedAudioProvider(model="MiniMax-M3", env="MINIMAX_API_KEY", name="minimax-m3", accepts_audio=False),
    "minimax-speech-2.8-hd": UnsupportedAudioProvider(model="speech-2.8-hd", env="MINIMAX_API_KEY", name="minimax-speech-2.8-hd", accepts_audio=False),
    "minimax-speech-2.8-turbo": UnsupportedAudioProvider(model="speech-2.8-turbo", env="MINIMAX_API_KEY", name="minimax-speech-2.8-turbo", accepts_audio=False),
    "qwen3.7-plus": UnsupportedAudioProvider(model="qwen3.7-plus", env="DASHSCOPE_API_KEY", name="qwen3.7-plus", accepts_audio=False),
    "qwen3.5-omni-plus": QwenOmniProvider(model="qwen3.5-omni-plus", env="QWEN_API_KEY", name="qwen3.5-omni-plus"),
    "qwen3.5-omni-plus-cn": QwenOmniChinaProvider(model="qwen3.5-omni-plus", env="QWEN_API_KEY", name="qwen3.5-omni-plus-cn"),
    "qwen3-omni-flash": QwenOmniProvider(model="qwen3-omni-flash", env="QWEN_API_KEY", name="qwen3-omni-flash"),
    "qwen3.6-plus-us": QwenOmniUSProvider(model="qwen3.6-plus", env="QWEN_API_KEY", name="qwen3.6-plus-us"),
}

PROVIDERS["gemini-3.1-pro"].price_per_1m_input_tokens = 2.00
PROVIDERS["gemini-3.1-pro"].price_per_1m_output_tokens = 12.00
PROVIDERS["gemini-3.1-pro"].max_requests_per_minute = 24
PROVIDERS["gemini-3.5-flash"].price_per_1m_input_tokens = 1.50
PROVIDERS["gemini-3.5-flash"].price_per_1m_output_tokens = 9.00
