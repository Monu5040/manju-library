from django.db import migrations


def protect(apps, schema_editor):
    # Uses the current models on purpose: it must encrypt with the app's own scheme.
    from imports.maintenance import protect_legacy_import_data

    protect_legacy_import_data()


class Migration(migrations.Migration):
    dependencies = [("imports", "0001_initial")]

    operations = [migrations.RunPython(protect, migrations.RunPython.noop)]
