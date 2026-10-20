"""Deterministic random numbers: SHA-256 over (seed, namespace, counter).

Unlike random.Random, the output does not depend on the Python version. Each entity draws from
its own namespace (rng.child("persona:coffee_shop")), so adding a new kind of data later does not
shift the numbers of the existing ones.
"""

import hashlib
from collections.abc import Sequence

_BITS = 256


class Rng:
    def __init__(self, seed: int, namespace: str = "root") -> None:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative int")
        self.seed = seed
        self.namespace = namespace
        self._counter = 0

    def child(self, name: str) -> "Rng":
        """Independent stream; does not advance this one."""
        return Rng(self.seed, f"{self.namespace}/{name}")

    def _next_block(self) -> int:
        data = f"{self.seed}\x1f{self.namespace}\x1f{self._counter}".encode()
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

    def digits(self, count: int) -> str:
        return "".join(str(self.below(10)) for _ in range(count))

    def choice[T](self, items: Sequence[T]) -> T:
        if not items:
            raise ValueError("cannot choose from an empty sequence")
        return items[self.below(len(items))]
