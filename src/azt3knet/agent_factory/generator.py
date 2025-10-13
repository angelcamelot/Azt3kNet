"""Synthetic agent generator for the first sprint."""

from __future__ import annotations

import uuid
import re
from typing import Iterable, List

from .models import AgentProfile, PopulationSpec
from ..core.config import resolve_seed
from ..core.seeds import SeedSequence, cycle_choices, shuffle_iterable
from ..llm.adapter import LLMAdapter, LLMRequest, LocalLLMAdapter

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


_NAME_PROMPT_TEMPLATE = (
    "You are DeepSeek, generating synthetic agent identities for research. "
    "Return one distinctive first name for a {gender_desc} persona engaging "
    "with audiences in {location_desc}. Respond with the name only."
)

_GENDER_DESCRIPTORS = {
    "female": "feminine",
    "male": "masculine",
    "non_binary": "non-binary",
    "unspecified": "gender-neutral",
}

_NAME_TOKEN_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ']+")


def _gender_descriptor(value: str | None) -> str:
    if not value:
        return _GENDER_DESCRIPTORS["unspecified"]
    return _GENDER_DESCRIPTORS.get(value, _GENDER_DESCRIPTORS["unspecified"])


def _location_descriptor(spec: PopulationSpec) -> str:
    parts: List[str] = []
    if spec.city:
        parts.append(spec.city)
    if spec.country:
        parts.append(spec.country.upper())
    if not parts:
        return "global communities"
    return "/".join(parts)


def _sanitize_name(value: str) -> str:
    tokens = _NAME_TOKEN_PATTERN.findall(value)
    if not tokens:
        return ""
    primary = tokens[0].capitalize()
    if len(tokens) == 1:
        return primary
    secondary = tokens[1].capitalize()
    return f"{primary} {secondary}"


def _fallback_name(sequence: SeedSequence, index: int, used: set[str]) -> str:
    attempt = 0
    while True:
        candidate_number = sequence.derive("fallback-name", str(index), str(attempt)) % 10_000
        candidate = f"Agent {candidate_number:04d}"
        if candidate.lower() not in used:
            return candidate
        attempt += 1


def _generate_agent_name(
    *,
    llm: LLMAdapter,
    spec: PopulationSpec,
    gender: str,
    sequence: SeedSequence,
    index: int,
    used: set[str],
) -> str:
    gender_desc = _gender_descriptor(gender)
    location_desc = _location_descriptor(spec)
    base_prompt = _NAME_PROMPT_TEMPLATE.format(
        gender_desc=gender_desc,
        location_desc=location_desc,
    )
    for attempt in range(3):
        seed_value = sequence.derive("name", str(index), str(attempt))
        response = llm.generate_field(
            LLMRequest(
                prompt=f"{base_prompt} (option {attempt + 1})",
                seed=seed_value,
                field_name="agent_name",
            )
        )
        sanitized = _sanitize_name(response)
        if sanitized and sanitized.lower() not in used:
            used.add(sanitized.lower())
            return sanitized
    fallback = _fallback_name(sequence, index, used)
    used.add(fallback.lower())
    return fallback


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


def generate_agents(spec: PopulationSpec, *, llm: LLMAdapter | None = None) -> List[AgentProfile]:
    """Generate deterministic agents from a specification."""

    seed = resolve_seed(spec.seed)
    seed_sequence = SeedSequence(seed)
    interests = _normalize_interests(spec.interests)
    gender = spec.gender or "unspecified"
    rng_for_cadence = seed_sequence.random("cadence")
    cadences = cycle_choices(POSTING_CADENCES, spec.count, rng_for_cadence)
    rng_for_tone = seed_sequence.random("tone")
    tones = cycle_choices(TONES, spec.count, rng_for_tone)
    adapter = llm or LocalLLMAdapter()
    used_names: set[str] = set()

    agents: List[AgentProfile] = []
    for idx in range(spec.count):
        name = _generate_agent_name(
            llm=adapter,
            spec=spec,
            gender=gender,
            sequence=seed_sequence,
            index=idx,
            used=used_names,
        )
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
