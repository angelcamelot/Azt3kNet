"""Synthetic agent generator for the first sprint."""

from __future__ import annotations

import itertools
import uuid
from typing import Iterable, List, Sequence

from .models import AgentProfile, PopulationSpec
from ..core.config import resolve_seed
from ..core.seeds import SeedSequence, cycle_choices, shuffle_iterable

COUNTRY_TIMEZONES = {
    "MX": "America/Mexico_City",
    "US": "America/New_York",
    "ES": "Europe/Madrid",
}

COUNTRY_LOCALES = {
    "MX": "es_MX",
    "US": "en_US",
    "ES": "es_ES",
}

NAMES_BY_GENDER = {
    "female": ["Avery", "Luna", "Harper", "Zoe", "Maya"],
    "male": ["Ethan", "Leo", "Miles", "Luca", "Kai"],
    "non_binary": ["Alex", "River", "Rowan", "Sky", "Phoenix"],
    "unspecified": ["Sam", "Taylor", "Morgan", "Hayden", "Parker"],
}

DEFAULT_BEHAVIORS = [
    "community_builder",
    "early_adopter",
    "fact_checker",
    "trend_responder",
]

POSTING_CADENCES = ["hourly", "daily", "weekly", "monthly"]
TONES = ["casual", "formal", "enthusiastic", "sarcastic", "informative"]


def _normalize_interests(interests: Iterable[str] | None) -> List[str]:
    if interests is None:
        return ["digital culture", "local news", "creative tech"]
    return [interest.strip().lower() for interest in interests if interest.strip()]


def _choose_name(gender: str | None, index: int) -> str:
    options: Sequence[str]
    if gender and gender in NAMES_BY_GENDER:
        options = NAMES_BY_GENDER[gender]
    else:
        options = list(itertools.chain.from_iterable(NAMES_BY_GENDER.values()))
    return options[index % len(options)]


def _build_bio(name: str, interests: List[str], city: str | None) -> str:
    interests_text = ", ".join(interests[:3])
    location = f" from {city}" if city else ""
    return f"{name}{location} exploring {interests_text} with synthetic curiosity."


def _username_hint(name: str, city: str | None, rng: SeedSequence, index: int) -> str:
    slug = name.lower().replace(" ", "_")
    city_hint = (city or "global").lower().replace(" ", "")[:6]
    suffix = rng.derive(slug, city_hint, str(index)) % 10_000
    return f"{slug}_{city_hint}{suffix:04d}"


def _age_range(spec: PopulationSpec, rng: SeedSequence, index: int) -> int:
    if spec.age_range:
        low, high = spec.age_range
    else:
        low, high = 18, 45
    span = high - low
    if span == 0:
        return low
    return low + (rng.derive("age", str(index)) % (span + 1))


def _posting_cadence(rng: SeedSequence, index: int) -> str:
    idx = rng.derive("cadence", str(index)) % len(POSTING_CADENCES)
    return POSTING_CADENCES[idx]


def _tone(rng: SeedSequence, index: int) -> str:
    idx = rng.derive("tone", str(index)) % len(TONES)
    return TONES[idx]


def _behaviors(interests: List[str], rng: SeedSequence, index: int) -> List[str]:
    base = shuffle_iterable(DEFAULT_BEHAVIORS, rng.random("behaviors", str(index)))
    derived = [f"affinity_{interest.replace(' ', '_')}" for interest in interests[:2]]
    return list(dict.fromkeys(base[:2] + derived))


def _time_zone(country: str) -> str:
    return COUNTRY_TIMEZONES.get(country.upper(), "Etc/UTC")


def _locale(country: str) -> str:
    return COUNTRY_LOCALES.get(country.upper(), "en_US")


def generate_agents(spec: PopulationSpec) -> List[AgentProfile]:
    """Generate deterministic agents from a specification."""

    seed = resolve_seed(spec.seed)
    seed_sequence = SeedSequence(seed)
    interests = _normalize_interests(spec.interests)
    gender = spec.gender or "unspecified"
    rng_for_cadence = seed_sequence.random("cadence")
    cadences = cycle_choices(POSTING_CADENCES, spec.count, rng_for_cadence)
    rng_for_tone = seed_sequence.random("tone")
    tones = cycle_choices(TONES, spec.count, rng_for_tone)

    agents: List[AgentProfile] = []
    for idx in range(spec.count):
        name = _choose_name(gender, idx)
        username_hint = _username_hint(name, spec.city, seed_sequence, idx)
        agent = AgentProfile(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"azt3knet://agents/{seed}/{idx}"),
            seed=f"{seed}:{idx}",
            name=name,
            username_hint=username_hint,
            country=spec.country.upper(),
            city=spec.city or "",  # keep simple for now
            locale=_locale(spec.country),
            timezone=_time_zone(spec.country),
            age=_age_range(spec, seed_sequence, idx),
            gender=gender,  # type: ignore[arg-type]
            interests=interests,
            bio=_build_bio(name, interests, spec.city),
            posting_cadence=cadences[idx],  # type: ignore[index]
            tone=tones[idx],  # type: ignore[index]
            behavioral_biases=_behaviors(interests, seed_sequence, idx),
        )
        agents.append(agent)
    return agents


__all__ = ["generate_agents"]
