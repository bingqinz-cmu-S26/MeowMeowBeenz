from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["normal", "watch", "review"]
ReportRange = Literal["day", "week", "month"]
ActivityFilter = Literal["all", "activity", "eating", "litter", "vocal", "warnings"]


class CatProfile(BaseModel):
    id: str
    ownerId: str | None = None
    ownerUsername: str | None = None
    name: str
    initials: str
    age: str
    birthDate: str
    device: str | None = None
    accent: str


class CreateCatRequest(BaseModel):
    name: str
    birth_date: str
    device: str | None = None


class UpdateCatRequest(BaseModel):
    name: str
    birth_date: str
    device: str | None = None


class TimelineEvent(BaseModel):
    id: str
    catId: str | None = None
    catName: str | None = None
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


class AgentHistoryMessage(BaseModel):
    role: str
    text: str


class AgentRequest(BaseModel):
    question: str
    timeline: list[TimelineEvent] = Field(default_factory=list)
    report: HealthReport | dict = Field(default_factory=dict)
    history: list[AgentHistoryMessage] = Field(default_factory=list)


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


class ClipFileInfo(BaseModel):
    name: str
    type: str
    size: int


class ClipAnalysisResponse(BaseModel):
    ok: bool
    provider: str
    text: str
    rawText: str | None = None
    file: ClipFileInfo
    event: TimelineEvent | None = None
    analysis: TimelineEvent | None = None
