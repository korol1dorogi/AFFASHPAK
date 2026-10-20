import pytest


@pytest.fixture(autouse=True)
def _fast_password_hashing(settings):
    """PBKDF2 is deliberately slow; tests create hundreds of synthetic users."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Throttle counters live in the cache: one test must not throttle the next."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
