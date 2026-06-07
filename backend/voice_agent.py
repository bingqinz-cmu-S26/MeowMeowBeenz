"""Hands-free voice agent for MeowMeowBeenz (LiveKit Agents worker).

Pipeline: AssemblyAI STT (via LiveKit Inference)  ->  MiniMax M2 LLM (with moss retrieval as a tool)  ->  MiniMax Speech-02 TTS.
The LLM stays MiniMax; only the "ears" (STT) are borrowed. STT goes through LiveKit
Inference, so it's billed on your LiveKit key with no separate STT account.

This is a SEPARATE process from the FastAPI server (app.main). It connects to a LiveKit
room as an agent participant and talks to whoever joins (the mobile app).

Run it (from the backend/ directory, after installing requirements-voice.txt):
    python voice_agent.py console   # talk in your terminal, no room needed (quick local test)
    python voice_agent.py dev       # dev mode: joins LiveKit rooms, hot reload
    python voice_agent.py start     # production worker

Required env (see ../.env.example):
    MINIMAX_API_KEY, MINIMAX_MODEL, MINIMAX_API_URL   (brain + voice)
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET  (room connection + Inference STT)

STT uses LiveKit Inference (AssemblyAI), authenticated by your LiveKit credentials —
no separate Deepgram/AssemblyAI account. Requires LiveKit Cloud (Inference is not on self-hosted).
"""

import logging

from livekit.agents import Agent, AgentSession, JobContext, RunContext, WorkerOptions, cli, function_tool, inference
from livekit.plugins import minimax, openai, silero

from app.config import settings
from app.services.agent import friendly_time
from app.services.cat_timeline import get_cats, reference_now
from app.services.retrieval import retrieve_events

logger = logging.getLogger("cat-voice-agent")


def _minimax_base_url() -> str:
    """MiniMax exposes an OpenAI-compatible endpoint; the openai plugin wants the /v1 base."""
    url = settings.minimax_api_url or "https://api.minimax.io/v1/chat/completions"
    marker = "/v1"
    idx = url.find(marker)
    return url[: idx + len(marker)] if idx != -1 else "https://api.minimax.io/v1"


class CatWellnessAgent(Agent):
    def __init__(self) -> None:
        cat_names = ", ".join(cat["name"] for cat in get_cats()) or "the household cats"
        super().__init__(
            instructions=(
                "You are Beenz, a warm and concise cat wellness voice assistant. "
                f"The household cats are: {cat_names}. "
                "When the owner asks what a cat was doing, how a cat is feeling, or about a time of day "
                "(this morning, last night, etc.), you MUST call the lookup_cat_activity tool and answer "
                "ONLY from what it returns. Reference specific times and moods from the results. "
                "Never invent observations that the tool did not return. Never diagnose disease or claim certainty. "
                "If an observation looks like distress or discomfort, gently suggest keeping an eye on it. "
                "Your replies are spoken aloud, so keep them to 1-3 short, natural sentences."
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
            cat: Optional cat name to focus on (e.g. Mochi, Luna, Tofu, Biscuit).
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
        llm=openai.LLM(
            model=settings.minimax_model,
            base_url=_minimax_base_url(),
            api_key=settings.minimax_api_key,
        ),
        tts=minimax.TTS(model="speech-02-turbo"),
        vad=silero.VAD.load(),
    )

    await session.start(agent=CatWellnessAgent(), room=ctx.room)
    await session.generate_reply(
        instructions="Greet the owner warmly in one sentence and offer to tell them what their cats have been up to."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
