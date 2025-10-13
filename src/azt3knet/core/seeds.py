"""Deterministic helpers for seeds and pseudo-random choices."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class SeedSequence:
    """Utility class that derives deterministic integers from string seeds."""

    seed: str

    def derive(self, *extra: str) -> int:
        """Return an integer derived from the base seed and extra components."""

        payload = "::".join((self.seed, *extra))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return int(digest, 16) % (2**32)

    def random(self, *extra: str) -> random.Random:
        """Return a ``random.Random`` instance seeded from the derivation."""

        return random.Random(self.derive(*extra))


def cycle_choices(options: Sequence[str], count: int, rng: random.Random) -> List[str]:
    """Return ``count`` options cycling deterministically over the sequence."""

    if not options:
        return []
    return [options[(rng.randrange(len(options)) + idx) % len(options)] for idx in range(count)]


def shuffle_iterable(values: Iterable[str], rng: random.Random) -> List[str]:
    """Return a shuffled list without mutating the original iterable."""

    items = list(values)
    rng.shuffle(items)
    return items


__all__ = ["SeedSequence", "cycle_choices", "shuffle_iterable"]
