from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from audit.models import AuditLog
from automation import tasks
from automation.models import AutomationSettings, Reminder
from automation.services import build_reminders, rupees, send_by_sms, tidy_reminders
from billing.services import record_payment
from core.sms import LocmemSMSBackend, reminder_ready
from imports.models import ImportJob, ImportRow
from members.models import Membership, Student, WaitlistEntry
from members.services import create_student, renew_membership, save_membership

pytestmark = pytest.mark.django_db


def today():
    return timezone.localdate()


def days(n: int):
    return today() + timedelta(days=n)


def student(branch, name, mobile, **fields):
    return create_student(branch=branch, full_name=name, mobile=mobile, **fields)


def member(person, *, start, end, shift, seat=None, price=450):
    return save_membership(
        Membership(
            branch=person.branch,
            student=person,
            shift=shift,
            seat=seat,
            start_date=start,
            end_date=end,
            price=Decimal(price),
        )
    )


@pytest.fixture
def library(branch, shifts, seats):
    """Who needs a reminder today, and who does not."""
    day = shifts["day"]
    people = {
        "soon": student(branch, "Asha Kumari", "9876543210"),
        "today": student(branch, "Ravi Kumar", "9876500001"),
        "owes": student(branch, "Neha Singh", "9876500002"),
        "renewed": student(branch, "Amit Das", "9876500003"),
        "later": student(branch, "Pooja Rani", "9876500004"),
    }
    ms = {
        "soon": member(people["soon"], start=days(-28), end=days(2), shift=day, seat=seats[0]),
        "today": member(people["today"], start=days(-29), end=today(), shift=day, seat=seats[1]),
        "owes": member(people["owes"], start=days(-5), end=days(25), shift=day, seat=seats[2]),
        "renewed": member(people["renewed"], start=days(-28), end=days(2), shift=day),
        "later": member(people["later"], start=days(-20), end=days(10), shift=day),
    }
    for key in ("soon", "today", "renewed", "later"):
        record_payment(student=people[key], membership=ms[key], amount=Decimal("450"))
    record_payment(student=people["owes"], membership=ms["owes"], amount=Decimal("200"))
    renew_membership(ms["renewed"])
    return people, ms


def test_reminders_are_made_once_and_say_the_right_thing(library):
    people, ms = library
    branch = people["soon"].branch
    assert build_reminders(branch) == 3
    assert build_reminders(branch) == 0  # the hourly job may run again: nothing doubles

    made = {r.kind: r for r in Reminder.objects.all()}
    assert set(made) == {"EXPIRING_SOON", "EXPIRES_TODAY", "DUES"}
    soon = made["EXPIRING_SOON"]
    assert soon.student == people["soon"] and soon.mobile == "9876543210"
    end = ms["soon"].end_date
    assert soon.message.startswith(
        f"Hello Asha, your Day membership at Manju Library ends on {end.day} {end:%b %Y}."
    )
    assert made["DUES"].message.startswith("Hello Neha, ₹250 of your fees")
    assert made["DUES"].details["amount"] == "250.00"


def test_the_same_reminder_cannot_be_made_twice_on_one_day(library):
    """The hourly job and someone opening the page may run at once; the database decides."""
    from automation.services import _create, placeholder_values

    people, ms = library
    conf = AutomationSettings.for_branch(people["owes"].branch)
    args = dict(values=placeholder_values(conf.branch, people["owes"], ms["owes"]), details={})
    assert _create(conf, "DUES", people["owes"], today(), membership=ms["owes"], **args) == 1
    assert _create(conf, "DUES", people["owes"], today(), membership=ms["owes"], **args) == 0
    assert _create(conf, "DUES", people["owes"], days(1), membership=ms["owes"], **args) == 1


def test_reminders_close_themselves(library):
    people, ms = library
    branch = people["soon"].branch
    build_reminders(branch)
    renew_membership(ms["soon"])
    record_payment(student=people["owes"], membership=ms["owes"], amount=Decimal("250"))
    assert tidy_reminders(branch) == 2
    closed = dict(Reminder.objects.filter(status="SKIPPED").values_list("kind", "note"))
    assert closed == {"EXPIRING_SOON": "Renewed.", "DUES": "Paid."}


def test_dues_reminders_repeat_after_the_chosen_days(library):
    people, _ = library
    branch = people["soon"].branch
    build_reminders(branch)
    dues = Reminder.objects.get(kind="DUES")
    Reminder.objects.filter(pk=dues.pk).update(for_date=days(-3))
    assert build_reminders(branch) == 0
    Reminder.objects.filter(pk=dues.pk).update(for_date=days(-7))
    assert build_reminders(branch) == 1
    conf = AutomationSettings.for_branch(branch)
    conf.dues_repeat_days = 0  # remind once only
    conf.save()
    for n, reminder in enumerate(Reminder.objects.filter(kind="DUES")):
        Reminder.objects.filter(pk=reminder.pk).update(for_date=days(-60 - n))
    assert build_reminders(branch) == 0


def test_settings_turn_reminders_off(library):
    people, _ = library
    conf = AutomationSettings.for_branch(people["soon"].branch)
    conf.days_before_expiry = 0
    conf.remind_on_expiry_day = False
    conf.save()
    assert build_reminders(conf.branch) == 1  # dues only
    conf.reminders_enabled = False
    conf.save()
    Reminder.objects.all().delete()
    assert build_reminders(conf.branch) == 0


def test_free_seats_go_to_the_waiting_list_in_order(branch, shifts, seats):
    for n, seat in enumerate(seats[:4]):
        holder = student(branch, f"Holder {n}", f"98765100{n:02d}")
        member(holder, start=days(-1), end=days(60), shift=shifts["morning"], seat=seat)
    first, second, third = (
        student(branch, name, mobile)
        for name, mobile in (
            ("Kiran", "9876520001"),
            ("Sonu", "9876520002"),
            ("Meena", "9876520003"),
        )
    )
    for position, (person, shift) in enumerate(
        ((first, "morning"), (second, "morning"), (third, "day")), start=1
    ):
        WaitlistEntry.objects.create(
            branch=branch, student=person, preferred_shift=shifts[shift], position=position
        )

    assert build_reminders(branch) == 2  # one Morning seat is free: only the first in line
    offers = {r.student.full_name: r.details for r in Reminder.objects.filter(kind="WAITLIST")}
    assert offers == {
        "Kiran": {
            "seat": "5",
            "shift": "Morning",
            "position": 1,
            "variables": offers["Kiran"]["variables"],
        },
        "Meena": {
            "seat": "1",
            "shift": "Day",
            "position": 3,
            "variables": offers["Meena"]["variables"],
        },
    }
    assert "free in the Morning shift" in Reminder.objects.get(student=first).message

    member(first, start=today(), end=days(30), shift=shifts["morning"], seat=seats[4])
    assert WaitlistEntry.objects.get(student=first).status == "SEATED"  # given a seat
    tidy_reminders(branch)
    assert Reminder.objects.get(student=first).note == "No longer on the waiting list."


def test_sms_goes_out_only_when_turned_on_and_possible(library):
    people, _ = library
    branch = people["soon"].branch
    build_reminders(branch)
    LocmemSMSBackend.outbox.clear()
    assert send_by_sms(branch) == {"sent": 0, "failed": 0}  # off by default

    conf = AutomationSettings.for_branch(branch)
    conf.send_sms = True
    conf.save()
    with override_settings(SMS_BACKEND="core.sms.ConsoleSMSBackend"):
        assert not reminder_ready("DUES")  # the console only logs: never counts as sent
        assert send_by_sms(branch) == {"sent": 0, "failed": 0}
    msg91 = {
        "SMS_BACKEND": "core.sms.Msg91SMSBackend",
        "MSG91_AUTH_KEY": "test",
        "MSG91_OTP_TEMPLATE_ID": "otp",
        "MSG91_REMINDER_TEMPLATES": {"DUES": "dues-template"},
    }
    with override_settings(**msg91):
        assert reminder_ready("DUES") and not reminder_ready("EXPIRING_SOON")

    assert send_by_sms(branch) == {"sent": 3, "failed": 0}
    assert {m.mobile for m in LocmemSMSBackend.outbox} == {"9876543210", "9876500001", "9876500002"}
    assert set(Reminder.objects.values_list("status", "channel")) == {("SENT", "SMS")}


def test_the_front_desk_works_through_the_list(library, staff_api, owner_api):
    response = staff_api.post("/api/admin/reminders/refresh/")
    assert response.json() == {"closed": 0, "created": 3}
    listed = staff_api.get("/api/admin/reminders/?open=1").json()["results"]
    assert [r["kind"] for r in listed] == ["DUES", "EXPIRES_TODAY", "EXPIRING_SOON"]
    first = listed[0]
    assert first["whatsapp_url"].startswith("https://wa.me/919876500002?text=Hello%20Neha")

    url = f"/api/admin/reminders/{first['id']}/"
    sent = staff_api.post(f"{url}sent/", {"channel": "WHATSAPP"}, format="json").json()
    assert (sent["status"], sent["channel"], sent["sent_by_name"]) == (
        "SENT",
        "WHATSAPP",
        "Front Desk",
    )
    assert staff_api.post(f"{url}sent/", {"channel": "CALL"}, format="json").status_code == 400
    assert staff_api.post(f"{url}reopen/").json()["status"] == "PENDING"
    assert staff_api.post(f"{url}sent/", {"channel": "SMS"}, format="json").status_code == 400
    assert (
        staff_api.post(f"{url}skip/", {"note": "Paying tomorrow"}, format="json").json()["note"]
        == "Paying tomorrow"
    )
    done = staff_api.get("/api/admin/reminders/?done=1").json()["results"]
    assert [r["note"] for r in done] == ["Paying tomorrow"]
    summary = staff_api.get("/api/admin/reminders/summary/").json()
    assert summary == {"open": 2, "by_kind": {"EXPIRES_TODAY": 1, "EXPIRING_SOON": 1}}
    overview = owner_api.get("/api/admin/overview/").json()
    assert overview["library"]["reminders_to_send"] == 2


def test_only_the_owner_changes_the_settings(staff_api, owner_api):
    conf = staff_api.get("/api/admin/automation/").json()
    assert conf["days_before_expiry"] == 3 and conf["send_sms"] is False
    assert conf["sms"] == {
        "EXPIRING_SOON": True,
        "EXPIRES_TODAY": True,
        "DUES": True,
        "WAITLIST": True,
    }
    assert "{name}" not in conf["placeholders"] and "name" in conf["placeholders"]
    body = {"days_before_expiry": 5, "text_dues": "Namaste {name}, ₹{amount} baaki hai."}
    assert staff_api.patch("/api/admin/automation/", body, format="json").status_code == 403
    saved = owner_api.patch("/api/admin/automation/", body, format="json").json()
    assert saved["days_before_expiry"] == 5 and saved["text_dues"].startswith("Namaste")
    too_many = owner_api.patch("/api/admin/automation/", {"days_before_expiry": 99}, format="json")
    assert too_many.json() == {"days_before_expiry": ["Use a number from 0 to 30."]}
    blank = owner_api.patch("/api/admin/automation/", {"text_waitlist": " "}, format="json")
    assert "text_waitlist" in blank.json()
    assert AuditLog.objects.filter(action="automation.settings_updated").count() == 1


def test_students_are_marked_left_only_when_turned_on(branch, shifts):
    gone = student(branch, "Gone Away", "9876530001")
    member(gone, start=days(-100), end=days(-70), shift=shifts["day"])
    waiting = student(branch, "Still Waiting", "9876530002")
    WaitlistEntry.objects.create(branch=branch, student=waiting, position=1)
    Student.objects.update(created_at=timezone.now() - timedelta(days=120))

    assert tasks.mark_students_left() == 0  # off unless chosen
    conf = AutomationSettings.for_branch(branch)
    conf.mark_left_after_days = 60
    conf.save()
    assert tasks.mark_students_left() == 1
    gone.refresh_from_db()
    assert gone.status == "LEFT"
    assert Student.objects.get(pk=waiting.pk).status == "ACTIVE"
    assert AuditLog.objects.get(action="student.marked_left").metadata["students"] == [gone.pk]

    member(gone, start=today(), end=days(30), shift=shifts["day"])
    gone.refresh_from_db()
    assert gone.status == "ACTIVE"  # back again


def test_old_import_files_and_rows_are_deleted_after_the_undo_window(branch):
    old, recent = (
        ImportJob.objects.create(
            branch=branch, file_name=name, file_hash="0" * 64, file_format="xlsx", content=b"PK.."
        )
        for name in ("old.xlsx", "recent.xlsx")
    )
    for job in (old, recent):
        ImportRow.objects.create(
            job=job,
            row_number=2,
            raw={"Aadhaar": "1234 5678"},
            values={"aadhaar": "12345678"},
            result="READY",
            warnings=["Aadhaar '1234 5678' is not 12 digits, so it was left out."],
        )
    ImportJob.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=8))

    assert tasks.purge_old_import_data() == 1
    old.refresh_from_db()
    row = ImportRow.objects.get(job=old)
    assert old.content is None and row.raw == {} and row.values == {}
    assert row.warnings == ["Aadhaar (number removed) is not 12 digits, so it was left out."]
    assert ImportRow.objects.get(job=recent).raw == {"Aadhaar": "1234 5678"}


def test_free_seats_for_the_waiting_list(staff_api, branch, shifts, seats):
    holder = student(branch, "Holder", "9876540001")
    member(holder, start=today(), end=days(60), shift=shifts["morning"], seat=seats[0])
    free = staff_api.get("/api/admin/waitlist/free-seats/").json()
    assert free[str(shifts["morning"].pk)] == ["2", "3", "4", "5"]
    assert free[str(shifts["day"].pk)] == ["1", "2", "3", "4", "5"]  # shared seats allowed


def test_every_scheduled_job_exists_and_runs(library):
    from config.celery import app

    app.loader.import_default_modules()
    for entry in settings.CELERY_BEAT_SCHEDULE.values():
        assert entry["task"] in app.tasks, entry["task"]
    summary = tasks.run_reminders.delay().get()
    assert summary["main"] == {"closed": 0, "created": 3, "sent": 0, "failed": 0}
    tasks.clear_expired_sessions.delay()


def test_rupees_use_indian_grouping():
    assert [rupees(Decimal(n)) for n in ("450", "1250.50", "125000", "10000000")] == [
        "450",
        "1,250",
        "1,25,000",
        "1,00,00,000",
    ]
