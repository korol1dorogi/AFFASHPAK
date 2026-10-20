from decimal import Decimal

import pytest

from apps.demo_data.rng import Rng

V = "datagen-test"


def draw(rng: Rng, count: int = 20) -> list[int]:
    return [rng.below(1_000_000) for _ in range(count)]


def test_seed_string_follows_data_spec():
    rng = Rng(2026, "datagen-2026.10-v1", "company", "17")
    assert rng._prefix == "2026|datagen-2026.10-v1|company|17"


def test_same_inputs_give_same_stream():
    assert draw(Rng(42, V, "x", "1")) == draw(Rng(42, V, "x", "1"))


@pytest.mark.parametrize(
    "other",
    [
        Rng(43, V, "x", "1"),
        Rng(42, "datagen-other", "x", "1"),
        Rng(42, V, "y", "1"),
        Rng(42, V, "x", "2"),
    ],
)
def test_any_part_of_the_seed_changes_the_stream(other):
    assert draw(other) != draw(Rng(42, V, "x", "1"))


def test_pinned_values_do_not_drift_between_python_versions():
    # SHA-256 based: these numbers must never change, or every generated file changes.
    assert draw(Rng(2026, V, "pin"), 3) == PINNED


PINNED = [349353, 149839, 125304]


def test_stream_is_independent_of_parent_progress():
    parent = Rng(1, V, "root")
    first = draw(parent.stream("a", "1"))
    draw(parent)
    assert draw(parent.stream("a", "1")) == first


def test_ranges_and_helpers():
    rng = Rng(5, V, "helpers")
    assert {rng.between(3, 6) for _ in range(400)} == {3, 4, 5, 6}
    values = {rng.decimal_between("0.06", "0.08") for _ in range(300)}
    assert values == {Decimal("0.06"), Decimal("0.07"), Decimal("0.08")}
    assert rng.choice(["only"]) == "only"
    assert {rng.weighted(["a", "b"], ["1", "0"]) for _ in range(50)} == {"a"}
    assert sorted(rng.shuffled(range(10))) == list(range(10))
    assert all(0 < rng.unit() < 1 for _ in range(100))
    assert -6 < rng.normal() < 6
    hits = sum(rng.chance("0.25") for _ in range(4000))
    assert 850 < hits < 1150


@pytest.mark.parametrize("seed", [-1, 1.5, True, None])
def test_bad_seed(seed):
    with pytest.raises(ValueError):
        Rng(seed, V, "x")


def test_bad_arguments():
    rng = Rng(1, V, "x")
    with pytest.raises(ValueError):
        rng.below(0)
    with pytest.raises(ValueError):
        rng.between(2, 1)
    with pytest.raises(ValueError):
        rng.choice([])
    with pytest.raises(ValueError):
        rng.decimal_between("0.1", "0.155")
    with pytest.raises(ValueError):
        rng.weighted(["a"], ["0"])
