from typing import Optional
from pydantic import BaseModel, Field


class Signal(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    reliability: float = Field(ge=0, le=1)
    note: str = ""


class Haptic(BaseModel):
    pattern: list[int]
    amplitudes: list[int]
    label: str


class Verdict(BaseModel):
    check_id: str
    kind: str
    tier: str
    p: float
    confidence: str
    haptic: Haptic
    say: str
    headline: str
    evidence: list[str]
    signals: list[Signal]
    seen_before: Optional[dict] = None
    factchecks: list[dict] = []
    region: Optional[list[int]] = None
    region_kind: Optional[str] = None
    phash: Optional[str] = None
    lang: str = "en"
    quick: bool = False
    decisive: bool = True
    feedback_recorded: bool = False
    ms: int


class Feedback(BaseModel):
    check_id: str
    label: str


class TextCheck(BaseModel):
    text: str
    source_app: str = ""
    device: str = ""
    lang: str = ""


class PushRegistration(BaseModel):
    token: str
    platform: str = "ios"
    device: str = ""
