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
    MINIMAX_API_KEY, MINIMAX_MODEL, MINIMAX_API_URL   (brain — prefer MiniMax-M2 for tool use)
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
from app.services.cat_timeline import reference_now
from app.services.retrieval import retrieve_events
from app.services.voice_prompt import (
    greeting_instruction,
    tool_answer_instructions,
    voice_agent_instructions,
)

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


def _observation_lines(events: list[dict], now) -> list[dict]:
    return [
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


class CatWellnessAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=voice_agent_instructions())

    @function_tool
    async def lookup_cat_activity(
        self,
        context: RunContext,  # noqa: ARG002 - provided by the framework
        question: str,
        cat: str | None = None,
    ) -> dict:
        """Fetch logged cat activity from the household timeline.

        REQUIRED for any question about behavior, mood, what a cat did, or a time window
        (today, yesterday, last night, this morning, etc.).

        Args:
            question: Copy the owner's question verbatim, e.g. "How was Luna yesterday?"
            cat: The cat's name if mentioned — "Luna", "Milo", or "Saffron".
                 Must not be null when the owner names a cat. Use null only for whole-household questions.
        """
        events = await retrieve_events(question, cat=cat, limit=6)
        if not events:
            logger.info(
                "lookup_cat_activity returned no observations (question=%r, cat=%r)",
                question,
                cat,
            )
            return {
                "observations": [],
                "count": 0,
                "matched_cats": [],
                "instruction": tool_answer_instructions(count=0, matched_cats=[], empty=True),
            }

        now = reference_now(events)
        observations = _observation_lines(events, now)
        matched_cats = sorted({event["catName"] for event in events if event.get("catName")})
        logger.info(
            "lookup_cat_activity returned %d observation(s) for question=%r cat=%r",
            len(observations),
            question,
            cat,
        )
        return {
            "observations": observations,
            "matched_cats": matched_cats,
            "count": len(observations),
            "instruction": tool_answer_instructions(
                count=len(observations),
                matched_cats=matched_cats,
                empty=False,
            ),
        }


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    if settings.minimax_model.strip().lower() in {"m2-her", "m2her"}:
        logger.warning(
            "MINIMAX_MODEL=%s is optimized for roleplay, not tool calling. "
            "Set MINIMAX_MODEL=MiniMax-M2 in .env for smarter voice answers.",
            settings.minimax_model,
        )

    session = AgentSession(
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        llm=MiniMaxLLM(
            model=settings.minimax_model,
            base_url=_minimax_base_url(),
            api_key=settings.minimax_api_key,
            _strict_tool_schema=False,
            temperature=0.7,
            max_completion_tokens=512,
        ),
        tts=inference.TTS(model="cartesia/sonic", voice=""),
        vad=silero.VAD.load(),
    )

    await session.start(agent=CatWellnessAgent(), room=ctx.room)
    await session.generate_reply(instructions=greeting_instruction())


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
