from django.db import migrations


class Migration(migrations.Migration):
    """Business → Company (docs/data-model.md). Data is kept; FKs follow the rename."""

    dependencies = [
        ("business", "0001_initial"),
        ("applications", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel("Business", "Company"),
    ]
