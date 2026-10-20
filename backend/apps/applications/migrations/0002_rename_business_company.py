from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0001_initial"),
        ("business", "0002_rename_business_company"),
    ]

    operations = [
        migrations.RenameField("application", "business", "company"),
    ]
