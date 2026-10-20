"""Deterministic random numbers: SHA-256 over "{seed}|{generator_version}|{scope}|{key}".

The seed string follows docs/data-spec.md §6.6; the generator itself is SHA-256 instead of
random.Random, so the output does not depend on the Python version (D7 allows that: only the
distributions must match). Each task draws from its own stream (`segments`, `company|{i}`, …),
so changing one part does not shift the others.
"""

import hashlib
from collections.abc import Sequence
from decimal import Decimal
from statistics import NormalDist

_BITS = 256
_FLOAT_BITS = 53


class Rng:
    def __init__(self, seed: int | str, generator_version: str, scope: str, key: str = "") -> None:
        if isinstance(seed, bool) or not isinstance(seed, int | str):
            raise ValueError("seed must be an int or a str")
        if isinstance(seed, int) and seed < 0:
            raise ValueError("seed must be >= 0")
        self.seed = seed
        self.generator_version = generator_version
        self.scope = scope
        self.key = key
        self._prefix = f"{seed}|{generator_version}|{scope}|{key}"
        self._counter = 0

    def stream(self, scope: str, key: str = "") -> "Rng":
        """Independent stream with the same seed and version."""
        return Rng(self.seed, self.generator_version, scope, key)

    def _next_block(self) -> int:
        data = f"{self._prefix}|{self._counter}".encode()
        self._counter += 1
        return int.from_bytes(hashlib.sha256(data).digest(), "big")

    def below(self, n: int) -> int:
        """Uniform int in [0, n), rejection sampling — no modulo bias."""
        if n <= 0:
            raise ValueError("n must be > 0")
        limit = (1 << _BITS) - (1 << _BITS) % n
        while True:
            value = self._next_block()
            if value < limit:
                return value % n

    def between(self, low: int, high: int) -> int:
        """Uniform int in [low, high], both ends included."""
        if high < low:
            raise ValueError("high must be >= low")
        return low + self.below(high - low + 1)

    def decimal_between(self, low: str, high: str, step: str = "0.01") -> Decimal:
        """Uniform value on the grid `step` inside [low, high]: no float on the way."""
        lo, hi, st = Decimal(low), Decimal(high), Decimal(step)
        steps = (hi - lo) / st
        if steps != steps.to_integral_value() or steps < 0:
            raise ValueError("[low, high] must be a whole number of steps")
        return lo + st * self.between(0, int(steps))

    def chance(self, probability: Decimal | str) -> bool:
        """True with the given probability, 4-digit resolution."""
        threshold = int(Decimal(probability) * 10_000)
        return self.below(10_000) < threshold

    def choice[T](self, items: Sequence[T]) -> T:
        if not items:
            raise ValueError("cannot choose from an empty sequence")
        return items[self.below(len(items))]

    def weighted[T](self, items: Sequence[T], weights: Sequence[Decimal | int | str]) -> T:
        """Choice with weights (Decimal-exact cumulative sums)."""
        if len(items) != len(weights) or not items:
            raise ValueError("items and weights must be non-empty and of equal length")
        scaled = [int(Decimal(w) * 10_000) for w in weights]
        if min(scaled) < 0 or sum(scaled) == 0:
            raise ValueError("weights must be >= 0 with a positive sum")
        point = self.below(sum(scaled))
        for item, weight in zip(items, scaled, strict=True):
            if point < weight:
                return item
            point -= weight
        raise AssertionError("unreachable")

    def shuffled[T](self, items: Sequence[T]) -> list[T]:
        """Fisher–Yates on a copy."""
        result = list(items)
        for i in range(len(result) - 1, 0, -1):
            j = self.below(i + 1)
            result[i], result[j] = result[j], result[i]
        return result

    def unit(self) -> float:
        """Uniform float in (0, 1). Only for D7's lognormal size and latent PD (§6.6)."""
        return (self.below(1 << _FLOAT_BITS) + 0.5) / (1 << _FLOAT_BITS)

    def normal(self) -> float:
        """Standard normal via the inverse CDF (pure-Python stdlib, deterministic)."""
        return NormalDist().inv_cdf(self.unit())
