from datetime import timedelta
from decimal import Decimal

import django_filters
from django.db.models import Exists, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from billing.models import Payment

from .models import MONEY, Membership, Student


def renewed_later():
    """A live membership for the same student that starts after this one ends."""
    return Exists(
        Membership.objects.not_cancelled().filter(
            student=OuterRef("student"), start_date__gt=OuterRef("end_date")
        )
    )


def search(queryset, value: str, prefix: str = ""):
    value = value.strip()
    if not value:
        return queryset
    if value.isdigit():
        # Up to 4 digits is a roll number; longer is (part of) a mobile number.
        if len(value) <= 4:
            condition = Q(**{f"{prefix}roll_no": int(value)})
        else:
            condition = Q(**{f"{prefix}mobile__contains": value})
    else:
        condition = Q(**{f"{prefix}full_name__icontains": value}) | Q(
            **{f"{prefix}father_name__icontains": value}
        )
    return queryset.filter(condition)


def student_due_subquery():
    fees = (
        Membership.objects.not_cancelled()
        .filter(student=OuterRef("pk"))
        .values("student")
        .annotate(total=Sum(F("price") - F("discount")))
        .values("total")
    )
    paid = (
        Payment.objects.filter(student=OuterRef("pk"), is_void=False)
        .exclude(membership__status=Membership.Status.CANCELLED)
        .values("student")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    zero = Value(Decimal("0"))
    return Coalesce(Subquery(fees, output_field=MONEY), zero) - Coalesce(
        Subquery(paid, output_field=MONEY), zero
    )


class StudentFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="filter_q", label="Name, father's name, mobile or roll no."
    )
    shift = django_filters.NumberFilter(method="filter_shift")
    expiring_within = django_filters.NumberFilter(method="filter_expiring")
    has_due = django_filters.BooleanFilter(method="filter_has_due")
    without_membership = django_filters.BooleanFilter(method="filter_without_membership")

    class Meta:
        model = Student
        fields = ["status", "gender"]

    def filter_q(self, queryset, name, value):
        return search(queryset, value)

    def filter_shift(self, queryset, name, value):
        current = Membership.objects.current().filter(student=OuterRef("pk"), shift_id=value)
        return queryset.filter(Exists(current))

    def filter_expiring(self, queryset, name, value):
        today = timezone.localdate()
        ending = (
            Membership.objects.not_cancelled()
            .filter(
                student=OuterRef("pk"),
                end_date__gte=today,
                end_date__lte=today + timedelta(days=int(value)),
            )
            .filter(~renewed_later())
        )
        return queryset.filter(Exists(ending))

    def filter_has_due(self, queryset, name, value):
        annotated = queryset.annotate(due=student_due_subquery())
        return annotated.filter(due__gt=0) if value else annotated.filter(due__lte=0)

    def filter_without_membership(self, queryset, name, value):
        current = Membership.objects.current().filter(student=OuterRef("pk"))
        return queryset.filter(~Exists(current)) if value else queryset.filter(Exists(current))


class MembershipFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    state = django_filters.ChoiceFilter(choices=Membership.State.choices, method="filter_state")
    expiring_within = django_filters.NumberFilter(method="filter_expiring")
    has_due = django_filters.BooleanFilter(method="filter_has_due")

    class Meta:
        model = Membership
        fields = ["student", "shift", "seat", "plan", "status"]

    def filter_q(self, queryset, name, value):
        return search(queryset, value, prefix="student__")

    def filter_state(self, queryset, name, value):
        today = timezone.localdate()
        live = queryset.exclude(status=Membership.Status.CANCELLED)
        return {
            Membership.State.ACTIVE: live.filter(start_date__lte=today, end_date__gte=today),
            Membership.State.UPCOMING: live.filter(start_date__gt=today),
            Membership.State.EXPIRED: live.filter(end_date__lt=today),
            Membership.State.CANCELLED: queryset.filter(status=Membership.Status.CANCELLED),
        }[value]

    def filter_expiring(self, queryset, name, value):
        today = timezone.localdate()
        return (
            queryset.not_cancelled()
            .filter(end_date__gte=today, end_date__lte=today + timedelta(days=int(value)))
            .filter(~renewed_later())
        )

    def filter_has_due(self, queryset, name, value):
        live = queryset.not_cancelled()
        return live.filter(due_total__gt=0) if value else live.filter(due_total__lte=0)
