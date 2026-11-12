"""
Online payments through Razorpay payment links, against a fake Razorpay API. Signatures are
computed here independently, so a wrong formula in the app would fail these tests.
"""

import hashlib
import hmac
import json
import time
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import checks
from django.utils import timezone
from rest_framework.test import APIClient

from audit.models import AuditLog
from automation.models import JobRun
from billing import razorpay
from billing.models import OnlinePayment, Payment
from billing.services import record_payment
from billing.tasks import check_online_payments
from members.models import Membership
from members.services import create_student, default_end_date, save_membership

pytestmark = pytest.mark.django_db

KEY_SECRET = "test-key-secret"
WEBHOOK_SECRET = "test-webhook-secret"


class FakeRazorpay:
    """Enough of Razorpay's payment-links API for the app's calls."""

    def __init__(self):
        self.links: dict[str, dict] = {}
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "POST" and path == "payment_links":
            link_id = f"plink_{len(self.links) + 1:04d}"
            self.links[link_id] = {
                "id": link_id,
                "short_url": f"https://rzp.io/i/{link_id}",
                "status": "created",
                "amount": body["amount"],
                "currency": "INR",
                "reference_id": body["reference_id"],
                "payments": None,
            }
            return self.links[link_id]
        link_id = path.split("/")[1]
        link = self.links[link_id]
        if path.endswith("/cancel"):
            if link["status"] == "paid":
                raise razorpay.RazorpayError("Payment link is already paid")
            link["status"] = "cancelled"
        return link

    def pay(self, link_id, *, method="upi", amount=None):
        link = self.links[link_id]
        payment_id = f"pay_{link_id[-4:]}{len(link.get('payments') or [])}"
        link["status"] = "paid"
        link["payments"] = [
            {
                "payment_id": payment_id,
                "amount": amount if amount is not None else link["amount"],
                "method": method,
                "status": "captured",
                "created_at": int(time.time()),
            }
        ]
        return payment_id


@pytest.fixture
def fake(settings, monkeypatch):
    settings.RAZORPAY_KEY_ID = "rzp_test_example"
    settings.RAZORPAY_KEY_SECRET = KEY_SECRET
    settings.RAZORPAY_WEBHOOK_SECRET = WEBHOOK_SECRET
    api = FakeRazorpay()
    monkeypatch.setattr(razorpay, "_request", api)
    return api


@pytest.fixture
def open_branch(branch):
    branch.allow_online_payments = True
    branch.save()
    return branch


@pytest.fixture
def asha(open_branch, seats, shifts, day_plan):
    """Asha's month started 25 days ago; ₹300 of ₹450 is paid."""
    student = create_student(branch=open_branch, full_name="Asha Kumari", mobile="9876543210")
    start = timezone.localdate() - timedelta(days=25)
    membership = save_membership(
        Membership(
            branch=open_branch,
            student=student,
            plan=day_plan,
            shift=shifts["day"],
            seat=seats[0],
            start_date=start,
            end_date=default_end_date(start, 1),
            price=Decimal("450"),
        )
    )
    record_payment(student=student, membership=membership, amount=Decimal("300"), mode="UPI")
    return student, membership


def client_for(student) -> APIClient:
    client = APIClient()
    client.force_login(student.account)
    return client


def callback_params(fake, attempt, payment_id, status="paid", secret=KEY_SECRET):
    message = f"{attempt.link_id}|{attempt.reference}|{status}|{payment_id}"
    return {
        "razorpay_payment_id": payment_id,
        "razorpay_payment_link_id": attempt.link_id,
        "razorpay_payment_link_reference_id": attempt.reference,
        "razorpay_payment_link_status": status,
        "razorpay_signature": hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest(),
    }


def webhook(api, event: dict, secret=WEBHOOK_SECRET):
    body = json.dumps(event).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return api.post(
        "/api/payments/razorpay/webhook/",
        data=body,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=signature,
    )


def paid_event(fake, attempt):
    link = fake.links[attempt.link_id]
    paid = link["payments"][0]
    return {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {"entity": {"id": link["id"], "status": "paid"}},
            "payment": {
                "entity": {
                    "id": paid["payment_id"],
                    "amount": paid["amount"],
                    "currency": "INR",
                    "status": "captured",
                    "method": paid["method"],
                    "created_at": paid["created_at"],
                }
            },
        },
    }


def test_dues_paid_online_get_one_receipt_however_often_razorpay_reports_it(fake, asha):
    student, membership = asha
    api = client_for(student)

    offer = api.get(f"/api/portal/students/{student.pk}/online/").json()
    assert offer["available"] is True and offer["test_mode"] is True
    assert offer["dues"] == [
        {
            "membership": membership.pk,
            "amount": 150.0,
            "start_date": membership.start_date.isoformat(),
            "end_date": membership.end_date.isoformat(),
        }
    ]

    started = api.post(
        f"/api/portal/students/{student.pk}/online/",
        {"purpose": "DUES", "membership": membership.pk, "amount": 1},  # amount is ignored
    )
    assert started.status_code == 201
    attempt = OnlinePayment.objects.get(pk=started.json()["id"])
    assert started.json()["url"] == f"https://rzp.io/i/{attempt.link_id}"
    _, _, body = fake.calls[-1]
    assert body["amount"] == 15000  # paise, from the server's own balance
    assert body["reference_id"] == attempt.reference
    assert body["callback_url"].endswith("/portal/pay/return")
    assert body["customer"] == {"name": "Asha Kumari", "contact": "+919876543210"}

    payment_id = fake.pay(attempt.link_id, method="upi")
    result = api.post(
        "/api/portal/online/confirm/", callback_params(fake, attempt, payment_id)
    ).json()
    assert result["status"] == "PAID" and result["receipt_no"] is not None
    assert result["needs_desk"] is False

    payment = Payment.objects.get(pk=result["receipt"])
    assert (payment.amount, payment.mode, payment.source) == (Decimal("150"), "UPI", "ONLINE")
    assert payment.reference == payment_id and payment.collected_by is None
    assert Membership.objects.with_totals().get(pk=membership.pk).due_total == 0

    # The webhook, a second return and the checking job all report it again: still one.
    assert webhook(APIClient(), paid_event(fake, attempt)).status_code == 200
    api.post("/api/portal/online/confirm/", callback_params(fake, attempt, payment_id))
    check_online_payments()
    assert Payment.objects.filter(source="ONLINE").count() == 1
    assert AuditLog.objects.filter(action="payment.online").count() == 1
    receipts = api.get(f"/api/portal/students/{student.pk}/").json()["payments"]
    assert receipts[0]["source"] == "ONLINE" and receipts[0]["mode_label"] == "UPI"


def test_online_renewal_extends_the_membership_with_the_same_seat(fake, asha, day_plan):
    student, membership = asha
    api = client_for(student)
    renewal = api.get(f"/api/portal/students/{student.pk}/online/").json()["renewal"]
    assert renewal["membership"] == membership.pk and renewal["seat_number"] == "1"
    [option] = renewal["options"]
    start = membership.end_date + timedelta(days=1)
    assert option == {
        "plan": day_plan.pk,
        "plan_name": "1 month · Day",
        "months": 1,
        "start_date": start.isoformat(),
        "end_date": default_end_date(start, 1).isoformat(),
        "price": 450.0,
        "discount": 0.0,
        "amount": 450.0,
        "unavailable": "",
    }

    started = api.post(
        f"/api/portal/students/{student.pk}/online/",
        {"purpose": "RENEWAL", "membership": membership.pk, "plan": day_plan.pk},
    ).json()
    attempt = OnlinePayment.objects.get(pk=started["id"])
    fake.pay(attempt.link_id, method="card")
    # This time only the webhook reports it (the student closed the tab).
    assert webhook(APIClient(), paid_event(fake, attempt)).json() == {"result": "paid"}

    attempt.refresh_from_db()
    new = attempt.renewal
    assert attempt.status == "PAID" and attempt.problem == ""
    assert (new.renewed_from_id, new.seat_id, new.shift_id) == (
        membership.pk,
        membership.seat_id,
        membership.shift_id,
    )
    assert (new.start_date, new.price, new.notes) == (start, Decimal("450"), "Renewed online")
    assert attempt.payment.membership_id == new.pk and attempt.payment.mode == "CARD"
    status = api.get(f"/api/portal/online/{attempt.pk}/").json()
    assert status["renewal_end"] == new.end_date.isoformat()
    # Renewed, so there is nothing more to renew until the new month starts.
    assert api.get(f"/api/portal/students/{student.pk}/online/").json()["renewal"] is None
    [profile] = api.get("/api/portal/home/").json()["profiles"]
    assert profile["renewed_until"] == new.end_date.isoformat()
    assert profile["current_membership"]["id"] == membership.pk


def test_a_seat_taken_meanwhile_keeps_the_money_as_an_advance_for_the_desk(
    fake, asha, day_plan, shifts, owner_api, staff_api
):
    student, membership = asha
    api = client_for(student)
    attempt = OnlinePayment.objects.get(
        pk=api.post(
            f"/api/portal/students/{student.pk}/online/",
            {"purpose": "RENEWAL", "membership": membership.pk, "plan": day_plan.pk},
        ).json()["id"]
    )
    # While Asha pays, the desk gives her seat to someone else for next month.
    other = create_student(branch=student.branch, full_name="Ravi Kumar", mobile="9470000009")
    save_membership(
        Membership(
            branch=student.branch,
            student=other,
            shift=shifts["day"],
            seat=membership.seat,
            start_date=attempt.renewal_start,
            end_date=attempt.renewal_end,
            price=Decimal("450"),
        )
    )
    payment_id = fake.pay(attempt.link_id)
    result = api.post(
        "/api/portal/online/confirm/", callback_params(fake, attempt, payment_id)
    ).json()
    assert result["status"] == "PAID" and result["needs_desk"] is True
    attempt.refresh_from_db()
    assert attempt.renewal is None and attempt.payment.membership is None
    assert "renewal could not be made" in attempt.problem
    assert "Ravi" not in json.dumps(result)  # the student is not told who has the seat

    listed = staff_api.get("/api/admin/payments/online/?needs_attention=true").json()["results"]
    assert [row["id"] for row in listed] == [attempt.pk]
    assert owner_api.get("/api/admin/overview/").json()["library"]["online_to_check"] == 1
    url = f"/api/admin/payments/online/{attempt.pk}/sorted/"
    assert staff_api.post(url, {}).status_code == 403
    assert owner_api.post(url, {"note": "Gave seat 2"}).json()["problem"] == ""
    assert AuditLog.objects.filter(action="online_payment.sorted").exists()


def test_renewal_is_refused_up_front_when_the_seat_is_already_booked(fake, asha, day_plan, shifts):
    student, membership = asha
    other = create_student(branch=student.branch, full_name="Ravi Kumar", mobile="9470000009")
    start = membership.end_date + timedelta(days=5)
    save_membership(
        Membership(
            branch=student.branch,
            student=other,
            shift=shifts["day"],
            seat=membership.seat,
            start_date=start,
            end_date=start + timedelta(days=29),
            price=Decimal("450"),
        )
    )
    api = client_for(student)
    [option] = api.get(f"/api/portal/students/{student.pk}/online/").json()["renewal"]["options"]
    assert option["unavailable"].startswith("Seat 1 is booked from")
    assert "Ravi" not in option["unavailable"]
    refused = api.post(
        f"/api/portal/students/{student.pk}/online/",
        {"purpose": "RENEWAL", "membership": membership.pk, "plan": day_plan.pk},
    )
    assert refused.status_code == 400 and not fake.calls


def test_wrong_amounts_and_forged_callbacks_are_never_recorded(fake, asha):
    student, membership = asha
    api = client_for(student)
    attempt = OnlinePayment.objects.get(
        pk=api.post(
            f"/api/portal/students/{student.pk}/online/",
            {"purpose": "DUES", "membership": membership.pk},
        ).json()["id"]
    )
    # A callback signed with the wrong secret is refused before anything is asked.
    payment_id = fake.pay(attempt.link_id, amount=100)  # ₹1 instead of ₹150
    forged = callback_params(fake, attempt, payment_id, secret="guess")
    assert api.post("/api/portal/online/confirm/", forged).status_code == 400
    # A real callback, but Razorpay says only ₹1 arrived: not recorded, flagged for the desk.
    result = api.post(
        "/api/portal/online/confirm/", callback_params(fake, attempt, payment_id)
    ).json()
    assert result["status"] == "FLAGGED" and result["needs_desk"] is True
    attempt.refresh_from_db()
    assert attempt.payment is None and "Razorpay received ₹1" in attempt.problem
    assert not Payment.objects.filter(source="ONLINE").exists()
    # Once the owner has sorted it out, the checking job and repeat reports leave it alone.
    attempt.problem = ""
    attempt.save()
    check_online_payments()
    api.post("/api/portal/online/confirm/", callback_params(fake, attempt, payment_id))
    attempt.refresh_from_db()
    assert attempt.status == "FLAGGED" and attempt.problem == ""


def test_webhooks_need_razorpays_signature(fake, asha):
    student, membership = asha
    attempt = OnlinePayment.objects.get(
        pk=client_for(student)
        .post(
            f"/api/portal/students/{student.pk}/online/",
            {"purpose": "DUES", "membership": membership.pk},
        )
        .json()["id"]
    )
    fake.pay(attempt.link_id)
    forged = webhook(APIClient(), paid_event(fake, attempt), secret="guess")
    assert forged.status_code == 400
    assert not Payment.objects.filter(source="ONLINE").exists()

    expired = {
        "event": "payment_link.expired",
        "payload": {"payment_link": {"entity": {"id": attempt.link_id}}},
    }
    fake.links[attempt.link_id]["status"] = "expired"
    assert webhook(APIClient(), expired).json() == {"result": "payment_link.expired"}
    attempt.refresh_from_db()
    assert attempt.status == "EXPIRED"


def test_students_can_only_pay_their_own_memberships(fake, asha, open_branch):
    student, membership = asha
    stranger = create_student(branch=open_branch, full_name="Someone Else", mobile="9470000008")
    api = client_for(stranger)
    assert api.get(f"/api/portal/students/{student.pk}/online/").status_code == 404
    refused = api.post(
        f"/api/portal/students/{stranger.pk}/online/",
        {"purpose": "DUES", "membership": membership.pk},
    )
    assert refused.status_code == 400 and not fake.calls


def test_off_until_the_server_has_keys_and_the_owner_turns_it_on(settings, asha, monkeypatch):
    student, membership = asha
    calls = []
    monkeypatch.setattr(razorpay, "_request", lambda *a, **k: calls.append(a))
    api = client_for(student)
    assert api.get(f"/api/portal/students/{student.pk}/online/").json()["available"] is False
    start = {"purpose": "DUES", "membership": membership.pk}
    assert api.post(f"/api/portal/students/{student.pk}/online/", start).status_code == 400

    settings.RAZORPAY_KEY_ID = "rzp_test_example"
    settings.RAZORPAY_KEY_SECRET = KEY_SECRET
    settings.RAZORPAY_WEBHOOK_SECRET = WEBHOOK_SECRET
    student.branch.allow_online_payments = False
    student.branch.save()
    assert api.get(f"/api/portal/students/{student.pk}/online/").json()["available"] is False
    assert api.post(f"/api/portal/students/{student.pk}/online/", start).status_code == 400
    assert not calls


def test_a_new_attempt_cancels_the_last_unpaid_link(fake, asha):
    student, membership = asha
    api = client_for(student)
    url = f"/api/portal/students/{student.pk}/online/"
    first = api.post(url, {"purpose": "DUES", "membership": membership.pk}).json()["id"]
    second = api.post(url, {"purpose": "DUES", "membership": membership.pk}).json()["id"]
    assert OnlinePayment.objects.get(pk=first).status == "CANCELLED"
    assert OnlinePayment.objects.get(pk=second).status == "PENDING"
    assert fake.links[OnlinePayment.objects.get(pk=first).link_id]["status"] == "cancelled"


def test_the_checking_job_records_payments_whose_webhook_never_came(fake, asha):
    student, membership = asha
    attempt = OnlinePayment.objects.get(
        pk=client_for(student)
        .post(
            f"/api/portal/students/{student.pk}/online/",
            {"purpose": "DUES", "membership": membership.pk},
        )
        .json()["id"]
    )
    fake.pay(attempt.link_id, method="netbanking")
    assert check_online_payments() == {"checked": 1, "paid": 1, "errors": 0, "expired": 0}
    attempt.refresh_from_db()
    assert attempt.status == "PAID" and attempt.payment.mode == "BANK"
    assert JobRun.objects.get(name="online-payments").ok is True


def test_deploy_checks_refuse_test_keys_in_production_and_half_set_keys(settings):
    settings.IS_DEPLOYED = True
    settings.ENVIRONMENT = "production"
    settings.RAZORPAY_KEY_ID = "rzp_test_example"
    settings.RAZORPAY_KEY_SECRET = KEY_SECRET
    settings.RAZORPAY_WEBHOOK_SECRET = WEBHOOK_SECRET
    ids = {e.id for e in checks.run_checks()}
    assert "core.E007" in ids and "core.E006" not in ids

    settings.ENVIRONMENT = "staging"
    settings.RAZORPAY_WEBHOOK_SECRET = ""
    ids = {e.id for e in checks.run_checks()}
    assert "core.E006" in ids and "core.E007" not in ids


def test_a_payment_that_never_came_back_is_found_instead_of_charging_twice(fake, asha):
    """A UPI app that never returns to the site, and no webhook yet: the student tries again."""
    student, membership = asha
    api = client_for(student)
    url = f"/api/portal/students/{student.pk}/online/"
    first = OnlinePayment.objects.get(
        pk=api.post(url, {"purpose": "DUES", "membership": membership.pk}).json()["id"]
    )
    fake.pay(first.link_id)
    again = api.post(url, {"purpose": "DUES", "membership": membership.pk})
    assert again.status_code == 409
    assert again.json()["code"] == "already_paid" and again.json()["receipt_no"] is not None
    assert OnlinePayment.objects.count() == 1  # no second link
    assert Payment.objects.filter(source="ONLINE").count() == 1
    assert Membership.objects.with_totals().get(pk=membership.pk).due_total == 0


def test_a_membership_cancelled_during_payment_keeps_the_money_as_an_advance(fake, asha, day_plan):
    student, membership = asha
    api = client_for(student)
    attempt = OnlinePayment.objects.get(
        pk=api.post(
            f"/api/portal/students/{student.pk}/online/",
            {"purpose": "RENEWAL", "membership": membership.pk, "plan": day_plan.pk},
        ).json()["id"]
    )
    membership.status = Membership.Status.CANCELLED  # the owner cancels meanwhile
    membership.save()
    payment_id = fake.pay(attempt.link_id)
    api.post("/api/portal/online/confirm/", callback_params(fake, attempt, payment_id))
    attempt.refresh_from_db()
    assert attempt.status == "PAID" and attempt.renewal is None
    assert attempt.payment.membership is None and "was cancelled" in attempt.problem
    assert not Membership.objects.filter(renewed_from=membership).exists()


def test_test_keys_on_a_deployed_server_only_work_for_the_test_numbers(settings, fake, asha):
    student, membership = asha
    settings.IS_DEPLOYED = True
    api = client_for(student)
    url = f"/api/portal/students/{student.pk}/online/"
    assert api.get(url).json()["available"] is False
    assert api.post(url, {"purpose": "DUES", "membership": membership.pk}).status_code == 400
    settings.RAZORPAY_TEST_MOBILES = ["98765 43210"]
    assert api.get(url).json()["available"] is True
    settings.RAZORPAY_KEY_ID = "rzp_live_example"  # live keys: everyone can pay
    settings.RAZORPAY_TEST_MOBILES = []
    assert api.get(url).json()["available"] is True


def test_garbled_signatures_are_refused_cleanly(fake, asha):
    student, membership = asha
    api = client_for(student)
    attempt = OnlinePayment.objects.get(
        pk=api.post(
            f"/api/portal/students/{student.pk}/online/",
            {"purpose": "DUES", "membership": membership.pk},
        ).json()["id"]
    )
    payment_id = fake.pay(attempt.link_id)
    params = {**callback_params(fake, attempt, payment_id), "razorpay_signature": "ü"}
    assert api.post("/api/portal/online/confirm/", params).status_code == 400
    hook = APIClient().post(
        "/api/payments/razorpay/webhook/",
        data=b"{}",
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE="ü",
    )
    assert hook.status_code == 400


def test_renewed_until_follows_renewals_not_other_memberships(asha, seats, shifts):
    student, membership = asha
    api = client_for(student)
    # A second seat in the evening, starting next week: not a renewal.
    start = timezone.localdate() + timedelta(days=7)
    save_membership(
        Membership(
            branch=student.branch,
            student=student,
            shift=shifts["evening"],
            seat=seats[1],
            start_date=start,
            end_date=default_end_date(start, 1),
            price=Decimal("450"),
        )
    )
    [profile] = api.get("/api/portal/home/").json()["profiles"]
    assert profile["renewed_until"] is None
