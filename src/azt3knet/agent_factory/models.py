"""Data models describing population specifications and agent profiles."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Literal, Optional, Tuple, get_args
import uuid


Gender = Literal["female", "male", "non_binary", "unspecified"]
Cadence = Literal["hourly", "daily", "weekly", "monthly"]
Tone = Literal["casual", "formal", "enthusiastic", "sarcastic", "informative"]


_GENDER_VALUES = set(get_args(Gender))


@dataclass
class AgentProfile:
    """Representation of a generated agent."""

    id: uuid.UUID
    seed: str
    name: str
    username_hint: str
    country: str
    city: str
    locale: str
    timezone: str
    age: int
    gender: Gender
    interests: List[str]
    bio: str
    posting_cadence: Cadence
    tone: Tone
    behavioral_biases: List[str] = field(default_factory=list)

    def model_dump(self, mode: str | None = None) -> dict[str, object]:
        """Return a dictionary representation compatible with the tests."""

        payload = asdict(self)
        if mode == "json":
            payload = {**payload, "id": str(self.id)}
        return payload


@dataclass
class PopulationSpec:
    """Specification describing a requested population."""

    gender: Optional[Gender] = None
    count: int = 1
    country: str = ""
    city: Optional[str] = None
    age_range: Optional[Tuple[int, int]] = None
    interests: Optional[List[str]] = None
    seed: Optional[str] = None
    preview: Optional[int] = None
    persist: bool = False

    def __post_init__(self) -> None:
        if self.gender is not None and self.gender not in _GENDER_VALUES:
            allowed = ", ".join(sorted(_GENDER_VALUES))
            raise ValueError(f"gender must be one of: {allowed}")
        if self.count <= 0:
            raise ValueError("count must be greater than zero")
        if self.age_range:
            low, high = self.age_range
            if not (13 <= low <= high <= 90):
                raise ValueError("age_range must be within 13 and 90 and low <= high")
        if self.interests is not None and len(self.interests) == 0:
            raise ValueError("interests must contain at least one item if provided")
        if self.preview is not None and self.preview <= 0:
            raise ValueError("preview must be a positive integer")

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PopulationSpec":
        """Instantiate a ``PopulationSpec`` from request dictionaries."""

        copy = dict(data)
        age_range = copy.get("age_range")
        if isinstance(age_range, list) and len(age_range) == 2:
            copy["age_range"] = (int(age_range[0]), int(age_range[1]))
        interests = copy.get("interests")
        if isinstance(interests, list):
            copy["interests"] = [str(item) for item in interests]
        preview = copy.get("preview")
        if preview is not None:
            copy["preview"] = int(preview)
        count = copy.get("count")
        if count is not None:
            copy["count"] = int(count)
        return cls(**copy)


__all__ = ["AgentProfile", "PopulationSpec", "Gender", "Cadence", "Tone"]
