"""Modelos Pydantic para agentes Azt3kNet."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AgentIdentity(BaseModel):
    given_name: str
    family_name: str
    username_hint: str
    email_localpart: str
    country_iso2: str
    city: str
    locale: str
    timezone: str
    age: int
    gender: str
    interests: List[str]
    bio: str


class AgentTraits(BaseModel):
    posting_cadence: int = Field(..., ge=0, le=50)
    tone: str
    behavioral_biases: dict[str, float]


class Agent(BaseModel):
    id: Optional[int] = None
    seed: int
    identity: AgentIdentity
    traits: AgentTraits
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PopulationSpec(BaseModel):
    count: int = 1
    gender: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    age_range: tuple[int, int] | None = None
    interests: Optional[List[str]] = None
    seed: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True
