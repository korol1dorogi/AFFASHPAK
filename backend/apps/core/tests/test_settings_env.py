from config.settings import env_int


def test_empty_int_variable_takes_the_default(monkeypatch):
    """REL1: .env.example ships DEMO_QUEUE_SIZE= («empty — 30»); after `cp .env.example .env`
    the empty value crashed the settings import and `docker compose up` never started."""
    monkeypatch.setenv("DEMO_QUEUE_SIZE", "")
    assert env_int("DEMO_QUEUE_SIZE", 0) == 0

    monkeypatch.setenv("DEMO_QUEUE_SIZE", "  ")
    assert env_int("DEMO_QUEUE_SIZE", 7) == 7


def test_int_variable_is_read_when_set(monkeypatch):
    monkeypatch.setenv("DEMO_QUEUE_SIZE", "300")
    assert env_int("DEMO_QUEUE_SIZE", 0) == 300

    monkeypatch.delenv("DEMO_QUEUE_SIZE")
    assert env_int("DEMO_QUEUE_SIZE", 30) == 30
