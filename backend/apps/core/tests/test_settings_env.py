"""REL2: an empty `NAME=` in .env means «not set» — the stack must start (clean clone, 26.10)."""

from config.settings import env_int


def test_an_empty_integer_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("REL2_SIZE", "")
    assert env_int("REL2_SIZE", 30) == 30
    monkeypatch.setenv("REL2_SIZE", "  ")
    assert env_int("REL2_SIZE", 30) == 30


def test_a_set_integer_is_read(monkeypatch):
    monkeypatch.setenv("REL2_SIZE", "300")
    assert env_int("REL2_SIZE", 30) == 300
    monkeypatch.delenv("REL2_SIZE")
    assert env_int("REL2_SIZE", 30) == 30
