"""PATCH /api/company used to write the short name into Company.name — the registry's legal
name — so a renamed company lost it everywhere (bank card included). Now the label lives in
short_name: move it there and bring the legal name back from the registry (synthetic, by INN).
Companies that already have an account snapshot (seeded ones) count as «счёт подключён»."""

from django.db import migrations


def forwards(apps, schema_editor):
    Company = apps.get_model("business", "Company")
    CompanyIntegration = apps.get_model("business", "CompanyIntegration")
    FinancialSnapshot = apps.get_model("business", "FinancialSnapshot")
    if not Company.objects.exists():
        return
    try:
        from apps.business.registry import lookup  # the same synthetic registry as the API
    except ImportError:  # pragma: no cover - a future registry over HTTP
        lookup = None
    for company in Company.objects.all():
        record = lookup(company.inn) if lookup else None
        if record and record["name"] != company.name:
            company.short_name = company.name
            company.name = record["name"]
            company.save(update_fields=["name", "short_name"])
    with_statement = FinancialSnapshot.objects.values_list("company_id", flat=True).distinct()
    for company_id in with_statement:
        CompanyIntegration.objects.get_or_create(company_id=company_id, source="bank_account")


class Migration(migrations.Migration):
    dependencies = [("business", "0004_company_short_name_integrations")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
