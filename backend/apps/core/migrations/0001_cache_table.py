"""The cache table for DatabaseCache (settings.CACHES): throttle counters shared by all workers.

A migration rather than a separate `createcachetable` step, so every `migrate` (init container,
deploy, a teammate's local run) brings it. Idempotent: an existing table is left as is.
"""

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
