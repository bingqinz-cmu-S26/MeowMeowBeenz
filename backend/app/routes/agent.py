from fastapi import APIRouter, HTTPException

from app.models.schemas import AgentRequest
from app.services.agent import ask_agent

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("")
async def agent_chat(payload: AgentRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    timeline = [event.model_dump() for event in payload.timeline]
    report = payload.report.model_dump() if hasattr(payload.report, "model_dump") else payload.report
    result = ask_agent(question, timeline, report if isinstance(report, dict) else None)
    return {"ok": True, "answer": result["text"], "provider": result["provider"]}
