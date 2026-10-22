import pytest


@pytest.fixture(autouse=True)
def _fast_password_hashing(settings):
    """PBKDF2 is deliberately slow; tests create hundreds of synthetic users."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _fresh_cache(settings):
    """Throttle counters live in the cache: one test must not throttle the next.

    The stand keeps them in a database table (settings.CACHES); tests use process memory, so
    clearing works in tests without the database too (apps/core/tests/test_cache.py checks the
    real setting).
    """
    from django.core.cache import cache

    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()
    yield
    cache.clear()
