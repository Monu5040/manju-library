import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from audit.models import AuditLog
from billing.services import record_payment
from ledger.models import CashClosing, LedgerCategory, LedgerEntry
from members.services import create_student

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate


def category(code):
    return LedgerCategory.objects.get(code=code)


def add_entry(client, **fields):
    body = {"category": category("electricity").pk, "amount": "1200", "mode": "CASH", **fields}
    return client.post("/api/admin/ledger/entries/", body, format="json")


# --- expenses and other income --------------------------------------------------------


def test_staff_record_expenses_but_see_only_their_own(owner_api, staff_api):
    assert add_entry(staff_api, details="Bijli bill").status_code == 201
    assert add_entry(owner_api, category=category("salaries").pk, amount="9000").status_code == 201

    staff_list = staff_api.get("/api/admin/ledger/entries/").json()["results"]
    assert [e["details"] for e in staff_list] == ["Bijli bill"]  # the salary stays private
    assert staff_list[0]["created_by_name"] == "Front Desk"
    owner_list = owner_api.get("/api/admin/ledger/entries/").json()["results"]
    assert {e["category_name"] for e in owner_list} == {"Electricity", "Salaries"}
    assert AuditLog.objects.filter(action="ledger_entry.created").count() == 2


def test_only_the_owner_edits_and_voids(owner_api, staff_api):
    entry = add_entry(staff_api).json()
    url = f"/api/admin/ledger/entries/{entry['id']}/"
    assert staff_api.patch(url, {"amount": "1"}, format="json").status_code == 403
    assert staff_api.post(f"{url}void/", {"reason": "x"}, format="json").status_code == 403

    assert owner_api.patch(url, {"amount": "1250"}, format="json").json()["amount"] == 1250
    voided = owner_api.post(f"{url}void/", {"reason": "Entered twice"}, format="json").json()
    assert voided["is_void"] and voided["void_reason"] == "Entered twice"
    assert owner_api.patch(url, {"amount": "5"}, format="json").status_code == 400

    summary = owner_api.get("/api/admin/ledger/entries/summary/").json()
    assert summary["expenses"] == 0  # void entries are left out of totals
    assert AuditLog.objects.filter(action="ledger_entry.voided").exists()


def test_entries_are_checked(owner_api):
    future = (TODAY() + timedelta(days=1)).isoformat()
    assert "entry_date" in add_entry(owner_api, entry_date=future).json()
    assert "amount" in add_entry(owner_api, amount="0").json()
    off = category("water")
    off.is_active = False
    off.save()
    assert "category" in add_entry(owner_api, category=off.pk).json()


def test_summary_adds_up_every_entry(owner_api):
    yesterday = (TODAY() - timedelta(days=1)).isoformat()
    add_entry(owner_api, category=category("rent").pk, amount="8000", entry_date=yesterday)
    add_entry(owner_api, amount="1200")
    add_entry(owner_api, amount="300")
    add_entry(owner_api, category=category("other-income").pk, amount="250")
    summary = owner_api.get("/api/admin/ledger/entries/summary/").json()
    assert (summary["expenses"], summary["other_income"], summary["count"]) == (9500, 250, 4)
    by_category = {row["name"]: row["total"] for row in summary["by_category"]}
    assert by_category == {"Rent": 8000, "Electricity": 1500, "Other income": 250}


def test_summary_and_export_follow_the_filters(owner_api):
    add_entry(owner_api, amount="1200", details="Bijli")
    add_entry(owner_api, category=category("other-income").pk, amount="300", details="Lockers")
    summary = owner_api.get("/api/admin/ledger/entries/summary/?kind=EXPENSE").json()
    assert summary["expenses"] == 1200 and summary["other_income"] == 0

    response = owner_api.get("/api/admin/ledger/entries/export/?file_type=csv&kind=INCOME")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][:4] == ["Date", "Type", "Category", "Amount"]
    assert [r[2] for r in rows[1:]] == ["Other income"]


def test_categories_are_owned_by_the_super_admin(owner_api, staff_api):
    listed = staff_api.get("/api/admin/ledger/categories/").json()
    expenses = [c["name"] for c in listed if c["kind"] == "EXPENSE"]
    assert expenses[:3] == ["Rent", "Electricity", "Internet and Wi-Fi"]
    assert expenses[-1] == "Other expense"
    body = {"name": "Generator diesel", "kind": "EXPENSE"}
    assert staff_api.post("/api/admin/ledger/categories/", body, format="json").status_code == 403
    created = owner_api.post("/api/admin/ledger/categories/", body, format="json")
    assert created.status_code == 201
    again = owner_api.post("/api/admin/ledger/categories/", body, format="json")
    assert again.json()["name"] == ["A category with this name already exists."]

    used = category("rent")
    add_entry(owner_api, category=used.pk)
    response = owner_api.delete(f"/api/admin/ledger/categories/{used.pk}/")
    assert response.status_code == 400  # the app relies on it, and it has entries
    unused = created.json()["id"]
    assert owner_api.delete(f"/api/admin/ledger/categories/{unused}/").status_code == 204


# --- the ledger, day by day -----------------------------------------------------------


def test_daily_ledger_replaces_the_balance_sheet(owner_api, staff_api, branch):
    today = TODAY()
    asha = create_student(branch=branch, full_name="Asha Kumari", mobile="9876543210")
    ravi = create_student(branch=branch, full_name="Ravi Kumar", mobile="9876500001")
    record_payment(student=asha, amount=Decimal("450"))
    record_payment(student=asha, amount=Decimal("50"))
    record_payment(student=ravi, amount=Decimal("500"), mode="UPI")
    add_entry(owner_api, amount="1200")
    add_entry(owner_api, category=category("other-income").pk, amount="100")
    start = (today - timedelta(days=2)).isoformat()

    assert staff_api.get("/api/admin/ledger/daily/").status_code == 403
    ledger = owner_api.get(f"/api/admin/ledger/daily/?from={start}&to={today}").json()
    assert len(ledger["days"]) == 3
    assert ledger["days"][0]["income"] == 0  # quiet days are listed too
    last = ledger["days"][-1]
    assert (last["students"], last["fees"], last["other_income"]) == (2, 1000, 100)
    assert (last["expenses"], last["balance"]) == (1200, -100)
    assert ledger["totals"]["balance"] == -100

    response = owner_api.get(f"/api/admin/ledger/daily/?from={start}&to={today}&file_type=csv")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == [
        "Date",
        "Students Paid",
        "Fees",
        "Other Income",
        "Total Income",
        "Expenses",
        "Balance",
    ]
    assert rows[-1][0] == "Total" and rows[-1][-1] == "-100"


# --- cash -----------------------------------------------------------------------------


def test_cash_closing_counts_the_drawer(owner_api, staff_api, branch):
    today = TODAY()
    asha = create_student(branch=branch, full_name="Asha Kumari", mobile="9876543210")
    record_payment(student=asha, amount=Decimal("450"))  # cash
    record_payment(student=asha, amount=Decimal("500"), mode="UPI")  # not in the drawer
    add_entry(staff_api, amount="120", details="Water cans")

    preview = staff_api.get(f"/api/admin/cash-closings/preview/?day={today}").json()
    assert preview["opening"] is None and preview["can_close"]
    assert (preview["cash_in"], preview["cash_out"]) == (450, 120)

    url = "/api/admin/cash-closings/"
    first = staff_api.post(url, {"day": today.isoformat(), "counted": "1300"}, format="json")
    assert "opening" in first.json()  # the first closing needs the starting cash
    body = {"day": today.isoformat(), "opening": "1000", "counted": "1300", "removed": "0"}
    closing = staff_api.post(url, body, format="json").json()
    assert closing["expected"] == 1330 and closing["difference"] == -30

    again = staff_api.post(url, {**body, "counted": "1330"}, format="json")
    assert again.json()["day"] == "This day is already closed."
    assert staff_api.delete(f"{url}{closing['id']}/").status_code == 403
    assert owner_api.delete(f"{url}{closing['id']}/").status_code == 204
    assert AuditLog.objects.filter(action="cash_closing.reopened").exists()


def test_a_closing_covers_every_day_since_the_last_one(owner_api, branch, super_admin):
    today = TODAY()
    asha = create_student(branch=branch, full_name="Asha Kumari", mobile="9876543210")
    CashClosing.objects.create(
        branch=branch,
        day=today - timedelta(days=3),
        period_start=today - timedelta(days=3),
        opening=0,
        cash_in=0,
        cash_out=0,
        expected=0,
        counted=Decimal("2000"),
        closed_by=super_admin,
    )
    record_payment(student=asha, amount=Decimal("400"), paid_on=today - timedelta(days=2))
    record_payment(student=asha, amount=Decimal("300"), paid_on=today)
    LedgerEntry.objects.create(
        branch=branch, category=category("rent"), amount=Decimal("1500"), mode="CASH"
    )

    preview = owner_api.get(f"/api/admin/cash-closings/preview/?day={today}").json()
    assert preview["period_start"] == (today - timedelta(days=2)).isoformat()
    assert (preview["opening"], preview["cash_in"], preview["cash_out"]) == (2000, 700, 1500)
    body = {"day": today.isoformat(), "counted": "200", "removed": "1000", "opening": "5"}
    closing = owner_api.post("/api/admin/cash-closings/", body, format="json").json()
    assert closing["opening"] == 2000  # carried over: the typed opening is ignored
    assert closing["expected"] == 200 and closing["difference"] == 0

    earlier = (today - timedelta(days=1)).isoformat()
    late = owner_api.post("/api/admin/cash-closings/", {**body, "day": earlier}, format="json")
    assert late.json()["day"] == "A later day is already closed. Days are closed in order."
    tomorrow = (today + timedelta(days=1)).isoformat()
    preview = owner_api.get(f"/api/admin/cash-closings/preview/?day={tomorrow}").json()
    assert not preview["can_close"]
