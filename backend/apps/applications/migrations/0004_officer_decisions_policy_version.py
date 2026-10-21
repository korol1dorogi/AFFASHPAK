"""Officer decisions stored «officer» as policy_version; it is the version of the rules
(decision-model.md), and who decided is in decided_by. Data only, no schema change."""

from django.db import migrations

POLICY_VERSION = "2026.10-v1"  # CURRENT_POLICY_VERSION when this migration was written


def forwards(apps, schema_editor):
    Decision = apps.get_model("applications", "Decision")
    Decision.objects.filter(policy_version="officer").update(policy_version=POLICY_VERSION)


class Migration(migrations.Migration):
    dependencies = [("applications", "0003_applicationevent_check_decision_disbursement_and_more")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
