import pytest

from apps.demo_data.rng import Rng


def draw(rng: Rng, count: int = 20) -> list[int]:
    return [rng.below(1_000_000) for _ in range(count)]


def test_same_seed_and_namespace_give_same_stream():
    assert draw(Rng(42, "x")) == draw(Rng(42, "x"))


def test_seed_and_namespace_change_the_stream():
    base = draw(Rng(42, "x"))
    assert draw(Rng(43, "x")) != base
    assert draw(Rng(42, "y")) != base


def test_pinned_values_do_not_drift_between_python_versions():
    # SHA-256 based: these numbers must never change, or every generated file changes.
    assert draw(Rng(42, "pin"), 3) == [265768, 103792, 37823]
    assert Rng(0).digits(12) == "807008952571"


def test_child_is_independent_of_parent_progress():
    parent = Rng(1)
    first = draw(parent.child("a"))
    draw(parent)
    assert draw(parent.child("a")) == first


def test_ranges():
    rng = Rng(5)
    values = [rng.between(3, 6) for _ in range(400)]
    assert set(values) == {3, 4, 5, 6}
    assert rng.choice(["only"]) == "only"
    assert len(rng.digits(9)) == 9


@pytest.mark.parametrize("seed", [-1, 1.5, True, "1"])
def test_bad_seed(seed):
    with pytest.raises(ValueError):
        Rng(seed)


def test_bad_arguments():
    rng = Rng(1)
    with pytest.raises(ValueError):
        rng.below(0)
    with pytest.raises(ValueError):
        rng.between(2, 1)
    with pytest.raises(ValueError):
        rng.choice([])
