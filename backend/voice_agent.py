"""Hands-free voice agent for MeowMeowBeenz (LiveKit Agents worker).

Pipeline: AssemblyAI STT (via LiveKit Inference)  ->  MiniMax M2 LLM (with moss retrieval as a tool)  ->  Cartesia TTS (via LiveKit Inference).
The LLM stays MiniMax; STT and TTS go through LiveKit Inference, billed on your LiveKit key.

This is a SEPARATE process from the FastAPI server (app.main). It connects to a LiveKit
room as an agent participant and talks to whoever joins (the mobile app).

Normally started automatically by `python run.py` (or `./run.sh`) when LIVEKIT_* is set.
Run standalone from backend/ for debugging (after pip install -r requirements-voice.txt):
    python voice_agent.py console   # talk in your terminal, no room needed (quick local test)
    python voice_agent.py dev       # joins LiveKit rooms, hot reload
    python voice_agent.py start     # production worker

Required env (see ../.env.example):
    MINIMAX_API_KEY, MINIMAX_MODEL, MINIMAX_API_URL   (brain + voice)
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET  (room connection + Inference STT)

STT uses LiveKit Inference (AssemblyAI), authenticated by your LiveKit credentials —
no separate Deepgram/AssemblyAI account. Requires LiveKit Cloud (Inference is not on self-hosted).
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from livekit.agents import Agent, AgentSession, JobContext, RunContext, WorkerOptions, cli, function_tool, inference
from livekit.plugins import silero

from app.services.minimax_llm import MiniMaxLLM

from app.config import settings
from app.services.agent import friendly_time
from app.services.cat_timeline import get_cats, reference_now
from app.services.retrieval import retrieve_events

# LiveKit worker CLI reads os.environ directly (not pydantic settings).
for key, value in {
    "LIVEKIT_URL": settings.livekit_url,
    "LIVEKIT_API_KEY": settings.livekit_api_key,
    "LIVEKIT_API_SECRET": settings.livekit_api_secret,
}.items():
    if value:
        os.environ.setdefault(key, value)

logger = logging.getLogger("cat-voice-agent")


def _minimax_base_url() -> str:
    """MiniMax exposes an OpenAI-compatible endpoint; the openai plugin wants the /v1 base."""
    url = settings.minimax_api_url or "https://api.minimax.io/v1/chat/completions"
    marker = "/v1"
    idx = url.find(marker)
    return url[: idx + len(marker)] if idx != -1 else "https://api.minimax.io/v1"


class CatWellnessAgent(Agent):
    def __init__(self) -> None:
        cats = get_cats()
        cat_names = ", ".join(cat["name"] for cat in cats) or "the household cats"
        cat_profiles = "; ".join(
            f"{cat['name']}: {cat.get('ageYears', 'unknown')} years old, device {cat.get('device') or 'unknown'}"
            for cat in cats
        ) or "No cat profiles available."
        super().__init__(
            instructions=(
                "You are Beenz, MeowMeowBeenz's calm cat-care voice assistant for pet owners. "
                f"The household cats are: {cat_names}. "
                f"Household cat profiles: {cat_profiles}. "
                "\n\nVoice style:"
                "\n- Speak like a helpful veterinary intake assistant, not like a cat."
                "\n- Use plain owner-friendly language."
                "\n- Keep answers to 1-3 short sentences."
                "\n- Do not use stage directions, animal sounds, jokes, roleplay, or dramatic phrasing."
                "\n\nGrounding rules:"
                "\n- If the owner asks a profile question such as age, birth date, or device, answer from the household cat profiles without calling lookup_cat_activity."
                "\n- If the owner asks about what a cat did, how a cat seems, health changes, or a time window, silently call lookup_cat_activity before answering."
                "\n- Answer only from returned observations. Mention concrete times, cat names, actions, moods, and confidence when available."
                "\n- Never invent observations, never diagnose disease, and never claim medical certainty."
                "\n- If observations suggest distress or discomfort, say it is worth monitoring and suggest checking the cat in person."
                "\n\nUnclear input rules:"
                "\n- If the owner's speech transcription is unclear, fragmented, or not a usable question, ask one short clarifying question."
                "\n- Good clarification: 'Which cat and what time should I check?'"
                "\n- Do not answer from a guessed question."
                "\n\nInvisible implementation rules:"
                "\n- Never speak or print tool names, XML tags, JSON, arguments, code fences, API keys, missing keys, tokens, backend access, or implementation details."
                "\n- If observations cannot be accessed, say exactly: I can't read the activity timeline clearly right now. Please try again in a moment."
            )
        )

    @function_tool
    async def lookup_cat_activity(
        self,
        context: RunContext,  # noqa: ARG002 - provided by the framework
        question: str,
        cat: str | None = None,
    ) -> dict:
        """Retrieve what a cat was doing from the observation timeline (moss retrieval).

        Call this whenever the owner asks about a cat's behavior, mood, or a time window.

        Args:
            question: The owner's question, e.g. "what was Mochi doing last night".
            cat: Optional cat name to focus on. Use one of the household cat names from the instructions.
        """
        events = await retrieve_events(question, cat=cat, limit=6)
        if not events:
            return {"observations": [], "note": "No matching observations found."}
        now = reference_now(events)
        return {
            "observations": [
                {
                    "cat": event["catName"],
                    "time": friendly_time(event["timestamp"], now) if event.get("timestamp") else "recently",
                    "mood": event["moodLabel"],
                    "action": event["action"],
                    "confidence": round(event["confidence"], 2),
                    "note": event.get("description") or None,
                }
                for event in events
            ]
        }


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    session = AgentSession(
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        llm=MiniMaxLLM(
            model=settings.minimax_model,
            base_url=_minimax_base_url(),
            api_key=settings.minimax_api_key,
            _strict_tool_schema=False,
        ),
        tts=inference.TTS(model="cartesia/sonic", voice=""),
        vad=silero.VAD.load(),
    )

    await session.start(agent=CatWellnessAgent(), room=ctx.room)
    await session.generate_reply(
        instructions="Greet the owner warmly in one sentence and offer to tell them what their cats have been up to."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
