from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Sum
from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from accounts.models import Role, User
from accounts.permissions import AdminArea
from audit import services as audit
from audit.mixins import AuditedViewSetMixin, snapshot
from billing.models import Payment
from billing.serializers import PaymentSerializer
from billing.services import record_payment
from library.branching import BranchScopedMixin, current_branch
from library.models import Seat, Shift

from .filters import MembershipFilter, StudentFilter, renewed_later
from .models import Membership, Student, WaitlistEntry
from .serializers import (
    AdmissionSerializer,
    MembershipSerializer,
    MembershipWriteSerializer,
    NewMembershipSerializer,
    PaymentInputSerializer,
    RenewSerializer,
    StudentSerializer,
    StudentWriteSerializer,
    WaitlistEntrySerializer,
)
from .services import create_student, renew_membership, save_membership


def memberships_with_totals():
    return Membership.objects.with_totals().select_related("seat", "shift", "plan", "student")


class StudentViewSet(BranchScopedMixin, AuditedViewSetMixin, ModelViewSet):
    queryset = Student.objects.all()
    permission_classes = [AdminArea]
    staff_actions = {"create", "update", "partial_update"}
    filterset_class = StudentFilter
    ordering_fields = ["roll_no", "full_name", "admission_date", "created_at"]
    ordering = ["roll_no"]
    audit_entity = "student"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(
                Prefetch("memberships", queryset=memberships_with_totals().order_by("-end_date"))
            )
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return StudentWriteSerializer
        return StudentSerializer

    def _read(self, student, status_code=status.HTTP_200_OK):
        fresh = self.get_queryset().get(pk=student.pk)
        return Response(
            StudentSerializer(fresh, context=self.get_serializer_context()).data, status=status_code
        )

    def create(self, request, *args, **kwargs):
        serializer = StudentWriteSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        student = create_student(
            branch=self.get_branch(), by=request.user, **serializer.validated_data
        )
        self.record_audit("created", student, after=snapshot(student))
        return self._read(student, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = StudentWriteSerializer(
            instance, data=request.data, partial=partial, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return self._read(instance)

    @action(detail=True, methods=["post"], url_path="reveal-aadhaar")
    def reveal_aadhaar(self, request, pk=None):
        """Full Aadhaar number, for the Super Admin only; every view is logged."""
        student = self.get_object()
        audit.record(request, "student.aadhaar_viewed", entity="student", entity_id=student.pk)
        return Response({"aadhaar": student.aadhaar})


class MembershipViewSet(
    BranchScopedMixin,
    AuditedViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    queryset = Membership.objects.with_totals().select_related("seat", "shift", "plan", "student")
    permission_classes = [AdminArea]
    staff_actions = {"create", "update", "partial_update", "renew"}
    filterset_class = MembershipFilter
    ordering_fields = ["end_date", "start_date", "created_at", "due_total"]
    ordering = ["-start_date", "-id"]
    audit_entity = "membership"

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return MembershipWriteSerializer
        return MembershipSerializer

    def _read(self, membership, status_code=status.HTTP_200_OK):
        fresh = self.get_queryset().get(pk=membership.pk)
        return Response(
            MembershipSerializer(fresh, context=self.get_serializer_context()).data,
            status=status_code,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = MembershipWriteSerializer(
            instance, data=request.data, partial=partial, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        before = snapshot(instance)
        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        save_membership(instance)
        after = snapshot(instance)
        changed = [k for k in after if after[k] != before.get(k) and k != "updated_at"]
        if changed:
            self.record_audit(
                "updated",
                instance,
                before={k: before.get(k) for k in changed},
                after={k: after[k] for k in changed},
            )
        return self._read(instance)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """A new membership for an existing student, with an optional first payment."""
        serializer = NewMembershipSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        payment_input = PaymentInputSerializer(data=request.data.get("payment") or None)
        payment_data = None
        if request.data.get("payment"):
            payment_input.is_valid(raise_exception=True)
            payment_data = payment_input.validated_data
        membership = save_membership(
            Membership(branch=self.get_branch(), created_by=request.user, **data)
        )
        self.record_audit("created", membership, after=snapshot(membership))
        if payment_data:
            payment = record_payment(
                student=membership.student, membership=membership, by=request.user, **payment_data
            )
            audit.record(
                request,
                "payment.created",
                entity="payment",
                entity_id=payment.pk,
                after=snapshot(payment),
            )
        return self._read(membership, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def renew(self, request, pk=None):
        previous = self.get_object()
        serializer = RenewSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        payment_data = data.pop("payment", None)
        renewal = renew_membership(previous, by=request.user, **data)
        self.record_audit(
            "renewed", renewal, after=snapshot(renewal), metadata={"from": previous.pk}
        )
        if payment_data:
            payment = record_payment(
                student=renewal.student, membership=renewal, by=request.user, **payment_data
            )
            audit.record(
                request,
                "payment.created",
                entity="payment",
                entity_id=payment.pk,
                after=snapshot(payment),
            )
        return self._read(renewal, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Super Admin only: frees the seat; payments stay on record."""
        membership = self.get_object()
        if membership.status == Membership.Status.CANCELLED:
            raise ValidationError({"detail": "This membership is already cancelled."})
        membership.status = Membership.Status.CANCELLED
        membership.save(update_fields=["status", "updated_at"])
        self.record_audit(
            "cancelled", membership, metadata={"reason": request.data.get("reason", "")}
        )
        return self._read(membership)


class AdmissionView(APIView):
    """New student, their first membership and (optionally) the first payment, in one step."""

    permission_classes = [AdminArea]
    staff_methods = {"POST"}

    @transaction.atomic
    def post(self, request):
        branch = current_branch(request)
        context = {"request": request, "branch": branch}
        serializer = AdmissionSerializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = create_student(branch=branch, by=request.user, **data["student"])
        audit.record(
            request,
            "student.created",
            entity="student",
            entity_id=student.pk,
            after=snapshot(student),
        )

        membership = save_membership(
            Membership(
                branch=branch, student=student, created_by=request.user, **data["membership"]
            )
        )
        audit.record(
            request,
            "membership.created",
            entity="membership",
            entity_id=membership.pk,
            after=snapshot(membership),
        )

        payment = None
        if data.get("payment"):
            payment = record_payment(
                student=student, membership=membership, by=request.user, **data["payment"]
            )
            audit.record(
                request,
                "payment.created",
                entity="payment",
                entity_id=payment.pk,
                after=snapshot(payment),
            )

        membership = memberships_with_totals().get(pk=membership.pk)
        student = Student.objects.prefetch_related(
            Prefetch("memberships", queryset=memberships_with_totals())
        ).get(pk=student.pk)
        return Response(
            {
                "student": StudentSerializer(student, context=context).data,
                "membership": MembershipSerializer(membership, context=context).data,
                "payment": PaymentSerializer(payment).data if payment else None,
            },
            status=status.HTTP_201_CREATED,
        )


class WaitlistViewSet(BranchScopedMixin, AuditedViewSetMixin, ModelViewSet):
    queryset = WaitlistEntry.objects.select_related("student", "preferred_shift")
    serializer_class = WaitlistEntrySerializer
    permission_classes = [AdminArea]
    staff_actions = {"create", "update", "partial_update"}
    filterset_fields = ["status", "preferred_shift"]
    pagination_class = None
    audit_entity = "waitlist"

    def get_save_kwargs(self) -> dict:
        kwargs = super().get_save_kwargs()
        if "position" not in self.request.data:
            top = (
                WaitlistEntry.objects.filter(branch=self.get_branch()).order_by("-position").first()
            )
            kwargs["position"] = (top.position if top else 0) + 1
        return kwargs


class SeatMapView(APIView):
    """Every seat with the bookings live on a given day, for the seat map screen."""

    permission_classes = [AdminArea]

    def get(self, request):
        branch = current_branch(request)
        try:
            day = (
                date.fromisoformat(request.query_params.get("date", ""))
                if request.query_params.get("date")
                else timezone.localdate()
            )
        except ValueError as exc:
            raise ValidationError({"date": "Use the format YYYY-MM-DD."}) from exc

        bookings = defaultdict(list)
        live = (
            Membership.objects.not_cancelled()
            .filter(branch=branch, seat__isnull=False, start_date__lte=day, end_date__gte=day)
            .select_related("student", "shift")
            .order_by("start_minute")
        )
        for m in live:
            bookings[m.seat_id].append(
                {
                    "membership": m.id,
                    "student": m.student_id,
                    "student_name": m.student.full_name,
                    "roll_no": m.student.roll_no,
                    "shift_name": m.shift.name if m.shift else None,
                    "time_label": m.time_label,
                    "start_minute": m.start_minute,
                    "end_minute": m.end_minute,
                    "end_date": m.end_date,
                    "days_left": (m.end_date - timezone.localdate()).days,
                }
            )

        seats = Seat.objects.filter(branch=branch).order_by("sort_key", "number")
        seat_rows = [
            {
                "id": s.id,
                "number": s.number,
                "is_active": s.is_active,
                "bookings": bookings.get(s.id, []),
            }
            for s in seats
        ]
        active = [s for s in seat_rows if s["is_active"]]
        return Response(
            {
                "date": day,
                "allow_seat_sharing": branch.allow_seat_sharing,
                "shifts": [
                    {
                        "id": sh.id,
                        "name": sh.name,
                        "time_label": sh.time_label,
                        "minutes": sh.minute_range,
                    }
                    for sh in Shift.objects.filter(branch=branch, is_active=True)
                ],
                "seats": seat_rows,
                "summary": {
                    "seats": len(active),
                    "occupied": sum(1 for s in active if s["bookings"]),
                    "free": sum(1 for s in active if not s["bookings"]),
                },
            }
        )


class DashboardView(APIView):
    """Numbers for the admin overview page."""

    permission_classes = [AdminArea]

    def get(self, request):
        branch = current_branch(request)
        today = timezone.localdate()
        month_start = today.replace(day=1)
        live = Membership.objects.current(today).filter(branch=branch)
        seats = Seat.objects.filter(branch=branch, is_active=True).count()
        occupied = live.filter(seat__isnull=False).values("seat").distinct().count()
        expiring = (
            Membership.objects.not_cancelled()
            .filter(branch=branch, end_date__gte=today, end_date__lte=today + timedelta(days=7))
            .filter(~renewed_later())
            .count()
        )
        # A sum of per-membership dues, each of which is itself a sum: add them up here.
        dues = sum(
            Membership.objects.not_cancelled()
            .filter(branch=branch)
            .with_totals()
            .filter(due_total__gt=0)
            .values_list("due_total", flat=True),
            start=Decimal("0"),
        )
        payments = Payment.objects.filter(branch=branch, is_void=False)
        users = {
            "students": User.objects.filter(role=Role.STUDENT, is_active=True).count(),
            "staff": User.objects.filter(role=Role.STAFF, is_active=True).count(),
            "super_admins": User.objects.filter(role=Role.SUPER_ADMIN, is_active=True).count(),
        }
        return Response(
            {
                "users": users,
                "library": {
                    "active_members": live.values("student").distinct().count(),
                    "seats": seats,
                    "occupied_seats": occupied,
                    "occupancy_percent": round(100 * occupied / seats) if seats else 0,
                    "expiring_in_7_days": expiring,
                    "outstanding_dues": float(dues),
                    "collected_today": float(
                        payments.filter(paid_on=today).aggregate(t=Sum("amount"))["t"] or 0
                    ),
                    "collected_this_month": float(
                        payments.filter(paid_on__gte=month_start).aggregate(t=Sum("amount"))["t"]
                        or 0
                    ),
                    "waiting": WaitlistEntry.objects.filter(
                        branch=branch, status=WaitlistEntry.Status.WAITING
                    ).count(),
                },
            }
        )
