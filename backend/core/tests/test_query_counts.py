"""
The busiest pages must not run one query per row: with 30 students they should need about
as many queries as with 3. A failure here means a list started querying inside a loop.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from billing.services import record_payment
from members.models import Membership
from members.services import create_student, save_membership

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate


@pytest.fixture
def busy_library(branch, shifts, seats):
    """30 students, each with two terms, payments, and some dues."""
    from library.models import Seat

    extra = [Seat.objects.create(branch=branch, number=str(n)) for n in range(6, 31)]
    all_seats = seats + extra
    people = []
    for n in range(30):
        person = create_student(branch=branch, full_name=f"Student {n}", mobile=f"98765{n:05d}")
        start = TODAY() - timedelta(days=40)
        for _term in range(2):
            m = save_membership(
                Membership(
                    branch=branch,
                    student=person,
                    shift=shifts["day"],
                    seat=all_seats[n],
                    start_date=start,
                    end_date=start + timedelta(days=29),
                    price=Decimal("450"),
                )
            )
            record_payment(student=person, membership=m, amount=Decimal(450 if n % 3 else 200))
            start = m.end_date + timedelta(days=1)
        people.append(person)
    return people


PAGES = {
    "/api/admin/overview/": 20,
    "/api/admin/students/?status=ACTIVE&page_size=25": 10,
    "/api/admin/payments/?page_size=50": 10,
    "/api/admin/memberships/?page_size=50": 10,
    "/api/admin/seat-map/": 10,
    "/api/admin/waitlist/": 8,
    "/api/admin/reminders/?open=1": 8,
    "/api/admin/analytics/": 30,
}


@pytest.mark.parametrize(("url", "limit"), PAGES.items())
def test_admin_pages_use_a_fixed_number_of_queries(
    busy_library, owner_api, django_assert_max_num_queries, url, limit
):
    owner_api.get("/api/auth/me/")  # warm the session and permission lookups
    with django_assert_max_num_queries(limit):
        assert owner_api.get(url).status_code == 200


def test_the_portal_uses_a_fixed_number_of_queries(busy_library, django_assert_max_num_queries):
    from rest_framework.test import APIClient

    client = APIClient()
    student = busy_library[0]
    client.force_login(student.account)
    with django_assert_max_num_queries(10):
        assert client.get("/api/portal/home/").status_code == 200
    with django_assert_max_num_queries(8):
        assert client.get(f"/api/portal/students/{student.pk}/").status_code == 200
