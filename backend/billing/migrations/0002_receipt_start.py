from django.db import migrations

# The paper/Excel receipts went up to 1106, so the website continues from 1107.
FIRST_RECEIPT_NUMBER = 1107


def start_receipts(apps, schema_editor):
    Branch = apps.get_model("library", "Branch")
    ReceiptSequence = apps.get_model("billing", "ReceiptSequence")
    for branch in Branch.objects.all():
        ReceiptSequence.objects.get_or_create(
            branch=branch, defaults={"next_number": FIRST_RECEIPT_NUMBER}
        )


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial"), ("library", "0002_default_branch")]
    operations = [migrations.RunPython(start_receipts, migrations.RunPython.noop)]
