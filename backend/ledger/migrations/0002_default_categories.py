from django.db import migrations

EXPENSES = [
    ("Rent", "rent"),
    ("Electricity", "electricity"),
    ("Internet and Wi-Fi", "internet"),
    ("Salaries", "salaries"),
    ("Cleaning", "cleaning"),
    ("Repairs and maintenance", "repairs"),
    ("Water", "water"),
    ("Newspapers and magazines", "newspapers"),
    ("Stationery and printing", "stationery"),
    ("Other expense", "other-expense"),
]
INCOME = [
    ("Past fees (old Balance Sheet)", "past-fees"),
    ("Other income", "other-income"),
]


def add_categories(apps, schema_editor):
    Category = apps.get_model("ledger", "LedgerCategory")
    for kind, rows in (("EXPENSE", EXPENSES), ("INCOME", INCOME)):
        for order, (name, code) in enumerate(rows):
            Category.objects.get_or_create(
                code=code, defaults={"name": name, "kind": kind, "sort_order": order * 10}
            )


class Migration(migrations.Migration):
    dependencies = [("ledger", "0001_initial")]

    operations = [migrations.RunPython(add_categories, migrations.RunPython.noop)]
