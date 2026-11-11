from django.db import migrations


def create_default_branch(apps, schema_editor):
    Branch = apps.get_model("library", "Branch")
    if not Branch.objects.exists():
        Branch.objects.create(name="Manju Library", code="main", allow_seat_sharing=True)


class Migration(migrations.Migration):
    dependencies = [("library", "0001_initial")]
    operations = [migrations.RunPython(create_default_branch, migrations.RunPython.noop)]
