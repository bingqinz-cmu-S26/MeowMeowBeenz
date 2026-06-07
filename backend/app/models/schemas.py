from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["normal", "watch", "review"]
ReportRange = Literal["day", "week", "month"]
ActivityFilter = Literal["all", "activity", "eating", "litter", "vocal", "warnings"]


class CatProfile(BaseModel):
    id: str
    name: str
    initials: str
    age: str
    breed: str
    room: str
    routine: str
    accent: str


class TimelineEvent(BaseModel):
    id: str
    time: str
    source: str
    state: str
    intent: str
    behaviorLabel: str
    soundType: str
    confidence: float
    riskLevel: RiskLevel
    signals: list[str]
    summary: str
    suggestion: str


class Alert(BaseModel):
    signal: str
    level: RiskLevel
    title: str
    evidence: list[str]
    suggestion: str
    confidence: float


class EventCounts(BaseModel):
    eating: int = 0
    litter: int = 0
    active: int = 0
    resting: int = 0
    grooming: int = 0
    vocal: int = 0
    review: int = 0


class HealthReport(BaseModel):
    dateLabel: str
    range: ReportRange
    totalEvents: int
    counts: EventCounts
    alerts: list[Alert]
    overall: RiskLevel
    summary: str


class AgentRequest(BaseModel):
    question: str
    timeline: list[TimelineEvent] = Field(default_factory=list)
    report: HealthReport | dict = Field(default_factory=dict)


class LiveKitTokenRequest(BaseModel):
    room: str | None = None
    identity: str | None = None


class ApiResponse(BaseModel):
    ok: bool
    error: str | None = None


class AuthRegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthUser(BaseModel):
    id: str
    username: str
    displayName: str
    createdAt: str | None = None
