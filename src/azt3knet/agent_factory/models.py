"""Pydantic schemas describing population specifications and agent profiles."""

from __future__ import annotations

from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, UUID4, conint, model_validator


Gender = Literal["female", "male", "non_binary", "unspecified"]
Cadence = Literal["hourly", "daily", "weekly", "monthly"]
Tone = Literal["casual", "formal", "enthusiastic", "sarcastic", "informative"]


class AgentProfile(BaseModel):
    id: UUID4
    seed: str
    name: str
    username_hint: str
    country: str
    city: str
    locale: str
    timezone: str
    age: conint(ge=13, le=90)
    gender: Gender
    interests: List[str]
    bio: str
    posting_cadence: Cadence
    tone: Tone
    behavioral_biases: List[str]


class PopulationSpec(BaseModel):
    gender: Optional[Gender] = None
    count: int = Field(..., gt=0)
    country: str
    city: Optional[str] = None
    age_range: Optional[Tuple[int, int]] = Field(
        default=None, description="Inclusive lower and upper bounds for agent ages."
    )
    interests: Optional[List[str]] = None
    seed: Optional[str] = None
    preview: Optional[int] = None
    persist: bool = False

    @model_validator(mode="after")
    def validate_age_range(self) -> "PopulationSpec":
        if self.age_range:
            low, high = self.age_range
            if not (13 <= low <= high <= 90):
                raise ValueError("age_range must be within 13 and 90 and low <= high")
        return self

    @model_validator(mode="after")
    def validate_interests(self) -> "PopulationSpec":
        if self.interests is not None and len(self.interests) == 0:
            raise ValueError("interests must contain at least one item if provided")
        return self

    @model_validator(mode="after")
    def validate_preview(self) -> "PopulationSpec":
        if self.preview is not None and self.preview <= 0:
            raise ValueError("preview must be a positive integer")
        return self


__all__ = ["AgentProfile", "PopulationSpec", "Gender", "Cadence", "Tone"]
