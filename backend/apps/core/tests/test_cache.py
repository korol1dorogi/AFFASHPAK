"""Throttle counters are shared by all gunicorn workers: a database cache, created by `migrate`."""

import pytest
from django.db import connection

from config import settings as project_settings


def test_the_stand_shares_throttle_counters_between_workers():
    """LocMemCache keeps a counter per process: 3 workers would let 3× the limit through."""
    backend = project_settings.CACHES["default"]["BACKEND"]
    assert backend == "django.core.cache.backends.db.DatabaseCache"


@pytest.mark.django_db
def test_migrate_creates_the_cache_table():
    table = project_settings.CACHES["default"]["LOCATION"]
    assert table in connection.introspection.table_names()
