from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Role
from conftest import valid_aadhaar
from core.validators import validate_aadhaar, verhoeff_is_valid
from library.models import ranges_overlap
from members.models import Membership
from members.services import (
    add_months,
    create_student,
    default_end_date,
    renew_membership,
    save_membership,
)

pytestmark = pytest.mark.django_db


def membership(student, *, seat, shift=None, start, months=1, **extra):
    m = Membership(
        branch=student.branch,
        student=student,
        seat=seat,
        shift=shift,
        start_date=start,
        end_date=default_end_date(start, months),
        price=Decimal("450"),
        **extra,
    )
    return save_membership(m)


@pytest.fixture
def two_students(branch):
    return (
        create_student(branch=branch, full_name="Asha Kumari", mobile="9876543210"),
        create_student(branch=branch, full_name="Ravi Kumar", mobile="9876543211"),
    )


# --- dates and numbers -------------------------------------------------------


def test_plan_end_dates_follow_the_library_rule():
    assert default_end_date(date(2025, 7, 28), 1) == date(2025, 8, 27)
    assert default_end_date(date(2025, 6, 12), 3) == date(2025, 9, 11)
    assert add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)


def test_overnight_ranges_overlap_across_midnight():
    night = (22 * 60 + 45, 24 * 60 + 6 * 60)  # 10:45 PM - 6:00 AM
    early = (5 * 60, 9 * 60)  # 5:00 AM - 9:00 AM next morning
    morning = (6 * 60, 10 * 60)
    assert ranges_overlap(night, early)
    assert not ranges_overlap(night, morning)


def test_aadhaar_checksum():
    number = valid_aadhaar()
    assert verhoeff_is_valid(number)
    validate_aadhaar(f"{number[:4]} {number[4:8]} {number[8:]}")
    wrong = number[:-1] + str((int(number[-1]) + 1) % 10)
    with pytest.raises(ValidationError):
        validate_aadhaar(wrong)
    with pytest.raises(ValidationError):
        validate_aadhaar("123456789012")  # cannot start with 1


# --- students ------------------------------------------------------------------


def test_students_get_roll_numbers_encrypted_aadhaar_and_a_login(branch):
    first = create_student(
        branch=branch, full_name="Asha", mobile="9876543210", aadhaar=valid_aadhaar()
    )
    second = create_student(branch=branch, full_name="Ravi", mobile="9876543211")
    assert (first.roll_no, second.roll_no) == (1, 2)
    assert first.aadhaar_last4 == valid_aadhaar()[-4:]
    assert first.aadhaar_masked == f"XXXX-XXXX-{valid_aadhaar()[-4:]}"
    assert first.account.role == Role.STUDENT

    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT aadhaar FROM members_student WHERE id = %s", [first.pk])
        stored = cursor.fetchone()[0]
    assert stored.startswith("enc:v1:") and valid_aadhaar()[:4] not in stored


def test_siblings_share_one_login(branch):
    sister = create_student(branch=branch, full_name="Kavya", mobile="9470000001")
    brother = create_student(branch=branch, full_name="Satya", mobile="9470000001")
    assert sister.account_id == brother.account_id


def test_staff_mobile_is_not_turned_into_a_student_login(branch, staff):
    student = create_student(branch=branch, full_name="Desk relative", mobile=staff.mobile)
    assert student.account is None


# --- seats -------------------------------------------------------------------------


def test_seat_can_be_shared_by_shifts_that_do_not_overlap(two_students, seats, shifts):
    asha, ravi = two_students
    today = timezone.localdate()
    membership(asha, seat=seats[0], shift=shifts["morning"], start=today)
    membership(ravi, seat=seats[0], shift=shifts["day"], start=today)
    assert Membership.objects.filter(seat=seats[0]).count() == 2


def test_overlapping_times_on_one_seat_are_refused(two_students, seats, shifts):
    asha, ravi = two_students
    today = timezone.localdate()
    membership(asha, seat=seats[0], shift=shifts["day"], start=today)
    with pytest.raises(ValidationError) as error:
        membership(
            ravi,
            seat=seats[0],
            custom_start_time=shifts["day"].start_time,
            custom_end_time=shifts["evening"].end_time,
            start=today,
        )
    assert "Seat 1 is already given to Asha Kumari" in str(error.value)


def test_overnight_shift_clash_is_caught(two_students, seats, shifts):
    from datetime import time

    asha, ravi = two_students
    today = timezone.localdate()
    membership(asha, seat=seats[0], shift=shifts["night"], start=today)
    with pytest.raises(ValidationError):
        membership(
            ravi,
            seat=seats[0],
            custom_start_time=time(5, 0),
            custom_end_time=time(9, 0),
            start=today,
        )


def test_no_sharing_branch_gives_a_seat_to_one_student(two_students, seats, shifts, branch):
    branch.allow_seat_sharing = False
    branch.save()
    asha, ravi = two_students
    today = timezone.localdate()
    membership(asha, seat=seats[0], shift=shifts["morning"], start=today)
    with pytest.raises(ValidationError):
        membership(ravi, seat=seats[0], shift=shifts["evening"], start=today)


def test_back_to_back_and_cancelled_memberships_do_not_block(two_students, seats, shifts):
    asha, ravi = two_students
    today = timezone.localdate()
    first = membership(asha, seat=seats[0], shift=shifts["day"], start=today)
    membership(ravi, seat=seats[0], shift=shifts["day"], start=first.end_date + timedelta(days=1))
    first.status = Membership.Status.CANCELLED
    first.save()
    membership(
        ravi, seat=seats[0], shift=shifts["day"], start=today, months=1, notes=""
    )  # would clash if live


def test_database_refuses_double_booking_even_without_the_service(two_students, seats, shifts):
    asha, ravi = two_students
    today = timezone.localdate()
    membership(asha, seat=seats[0], shift=shifts["day"], start=today)
    clash = Membership(
        branch=ravi.branch,
        student=ravi,
        seat=seats[0],
        shift=shifts["day"],
        start_date=today,
        end_date=today,
        price=Decimal("1"),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        clash.save()


# --- renewals ------------------------------------------------------------------------


def test_renewal_continues_after_the_old_end_with_the_same_seat(
    two_students, seats, shifts, day_plan
):
    asha, _ = two_students
    start = timezone.localdate() - timedelta(days=20)
    first = membership(asha, seat=seats[2], shift=shifts["day"], start=start, plan=day_plan)
    renewal = renew_membership(first)
    assert renewal.start_date == first.end_date + timedelta(days=1)
    assert renewal.end_date == default_end_date(renewal.start_date, 1)
    assert (renewal.seat_id, renewal.shift_id, renewal.price) == (
        seats[2].id,
        shifts["day"].id,
        Decimal("450"),
    )
    assert renewal.renewed_from_id == first.id


def test_lapsed_membership_renews_from_today(two_students, seats, shifts, day_plan):
    asha, _ = two_students
    old = membership(
        asha,
        seat=seats[2],
        shift=shifts["day"],
        start=timezone.localdate() - timedelta(days=90),
        plan=day_plan,
    )
    assert old.state == Membership.State.EXPIRED
    assert renew_membership(old).start_date == timezone.localdate()
