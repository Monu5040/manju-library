"""
Student portal API (/api/portal/...). A login (one mobile number) can own several student
profiles, for example siblings; every query is limited to the profiles of that login.
"""

from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from accounts.permissions import AdminArea, IsStudent
from accounts.throttles import OnlinePaymentThrottle
from audit import services as audit
from audit.mixins import AuditedViewSetMixin, snapshot
from billing import online, razorpay
from billing.models import OnlinePayment, Payment
from library.branching import BranchScopedMixin
from library.models import Plan, Shift
from members.models import Membership, Student

from .models import Notice
from .serializers import (
    NoticeSerializer,
    OnlinePaymentStartSerializer,
    PortalMembershipSerializer,
    PortalNoticeSerializer,
    PortalPaymentSerializer,
    PortalPlanSerializer,
    PortalProfileUpdateSerializer,
    PortalShiftSerializer,
    PortalStudentSerializer,
)


def my_students(user):
    memberships = Membership.objects.with_totals().select_related("seat", "shift", "plan")
    return (
        Student.objects.filter(account=user)
        .select_related("branch")
        .prefetch_related(Prefetch("memberships", queryset=memberships.order_by("-end_date")))
        .order_by("roll_no")
    )


def my_student(user, pk) -> Student:
    student = my_students(user).filter(pk=pk).first()
    if student is None:
        raise Http404
    return student


class PortalHomeView(APIView):
    """Everything the dashboard needs in one call."""

    permission_classes = [IsStudent]

    def get(self, request):
        students = list(my_students(request.user))
        branch = students[0].branch if students else None
        library = None
        notices, shifts, plans = [], [], []
        if branch is not None:
            library = {"name": branch.name, "address": branch.address, "phone": branch.phone}
            notices = PortalNoticeSerializer(
                Notice.objects.filter(branch=branch).live(), many=True
            ).data
            shifts = PortalShiftSerializer(
                Shift.objects.filter(branch=branch, is_active=True), many=True
            ).data
            plans = PortalPlanSerializer(
                Plan.objects.filter(branch=branch, is_active=True).select_related("shift"),
                many=True,
            ).data
        return Response(
            {
                "profiles": PortalStudentSerializer(students, many=True).data,
                "library": library,
                "notices": notices,
                "shifts": shifts,
                "plans": plans,
            }
        )


class PortalStudentView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        student = my_student(request.user, pk)
        payments = Payment.objects.filter(student=student).order_by("-paid_on", "-receipt_no")
        return Response(
            {
                **PortalStudentSerializer(student).data,
                "memberships": PortalMembershipSerializer(
                    [
                        m
                        for m in student.memberships.all()
                        if m.status != Membership.Status.CANCELLED
                    ],
                    many=True,
                ).data,
                "payments": PortalPaymentSerializer(payments, many=True).data,
            }
        )

    def patch(self, request, pk):
        student = my_student(request.user, pk)
        before = snapshot(student)
        serializer = PortalProfileUpdateSerializer(student, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        changed = {
            k: v for k, v in snapshot(student).items() if before.get(k) != v and k != "updated_at"
        }
        if changed:
            audit.record(
                request,
                "portal.profile_updated",
                entity="student",
                entity_id=student.pk,
                before={k: before.get(k) for k in changed},
                after=changed,
            )
        return Response(PortalStudentSerializer(my_student(request.user, pk)).data)


class PortalReceiptView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        payment = (
            Payment.objects.filter(pk=pk, student__account=request.user)
            .select_related("student", "branch")
            .first()
        )
        if payment is None:
            raise Http404
        branch = payment.branch
        return Response(
            {
                **PortalPaymentSerializer(payment).data,
                "student_name": payment.student.full_name,
                "roll_no": payment.student.roll_no,
                "library": {"name": branch.name, "address": branch.address, "phone": branch.phone},
            },
            status=status.HTTP_200_OK,
        )


def _status(attempt: OnlinePayment) -> dict:
    """What the student sees about one online payment. The desk's notes stay internal."""
    payment = attempt.payment
    return {
        "id": attempt.pk,
        "status": attempt.status,
        "purpose": attempt.purpose,
        "amount": float(attempt.amount),
        "receipt": payment.pk if payment else None,
        "receipt_no": payment.receipt_no if payment else None,
        "renewal_end": attempt.renewal.end_date if attempt.renewal_id else None,
        "needs_desk": bool(attempt.problem)
        and attempt.status in {OnlinePayment.Status.PAID, OnlinePayment.Status.FLAGGED},
    }


class PortalOnlineView(APIView):
    """What a student can pay online (GET), and starting a payment (POST)."""

    permission_classes = [IsStudent]
    throttle_classes = [OnlinePaymentThrottle]

    def get(self, request, pk):
        student = my_student(request.user, pk)
        if not online.is_open(student.branch, student):
            return Response({"available": False, "test_mode": False, "dues": [], "renewal": None})
        dues = [
            {
                "membership": m.pk,
                "amount": float(m.due_total),
                "start_date": m.start_date,
                "end_date": m.end_date,
            }
            for m in student.memberships.all()
            if m.status != Membership.Status.CANCELLED and m.due_total > 0
        ]
        choices = online.renewal_options(student)
        renewal = None
        if choices:
            previous = choices["membership"]
            renewal = {
                "membership": previous.pk,
                "seat_number": previous.seat.number if previous.seat else None,
                "shift_name": previous.shift.name if previous.shift else None,
                "time_label": previous.time_label,
                "end_date": previous.end_date,
                "options": [
                    {
                        "plan": o["plan"].pk,
                        "plan_name": o["plan"].name,
                        "months": o["plan"].duration_months,
                        "start_date": o["start_date"],
                        "end_date": o["end_date"],
                        "price": float(o["price"]),
                        "discount": float(o["discount"]),
                        "amount": float(o["amount"]),
                        "unavailable": o["reason"],
                    }
                    for o in choices["options"]
                ],
            }
        return Response(
            {"available": True, "test_mode": razorpay.test_mode(), "dues": dues, "renewal": renewal}
        )

    def post(self, request, pk):
        student = my_student(request.user, pk)
        serializer = OnlinePaymentStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        base = (
            settings.SITE_URL.rstrip("/")
            if settings.SITE_URL
            else request.build_absolute_uri("/").rstrip("/")
        )
        try:
            attempt = online.start_payment(
                student=student,
                purpose=data["purpose"],
                membership_id=data["membership"],
                plan_id=data.get("plan"),
                user=request.user,
                callback_url=f"{base}/portal/pay/return",
            )
        except online.AlreadyPaid as paid:
            # An earlier payment for this went through after all: say so, do not charge again.
            return Response(
                {
                    "detail": "Your earlier payment for this went through, so there is nothing "
                    "more to pay.",
                    "code": "already_paid",
                    **_status(paid.online),
                },
                status=status.HTTP_409_CONFLICT,
            )
        audit.record(
            request,
            "portal.online_payment_started",
            entity="online_payment",
            entity_id=attempt.pk,
            metadata={"purpose": attempt.purpose, "amount": str(attempt.amount)},
        )
        return Response({"id": attempt.pk, "url": attempt.link_url}, status=status.HTTP_201_CREATED)


class PortalOnlineConfirmView(APIView):
    """Back from Razorpay's page: check with Razorpay and record the payment if it is paid."""

    permission_classes = [IsStudent]

    def post(self, request):
        attempt = online.confirm_from_callback(user=request.user, params=request.data)
        return Response(_status(attempt))


class PortalOnlineStatusView(APIView):
    """For the return page while it waits. `?refresh=1` asks Razorpay, at most every 15s."""

    permission_classes = [IsStudent]

    def get(self, request, pk):
        attempt = (
            OnlinePayment.objects.filter(pk=pk, student__account=request.user)
            .select_related("payment", "renewal")
            .first()
        )
        if attempt is None:
            raise Http404
        if (
            request.query_params.get("refresh")
            and attempt.status == OnlinePayment.Status.PENDING
            and cache.add(f"online-check-{attempt.pk}", 1, timeout=15)
        ):
            try:
                attempt = online.check(attempt)
            except razorpay.RazorpayError:
                pass  # the webhook or the checking job will record it
        return Response(_status(attempt))


class NoticeViewSet(BranchScopedMixin, AuditedViewSetMixin, ModelViewSet):
    """Admin side: staff post and edit notices; only the Super Admin deletes them."""

    queryset = Notice.objects.select_related("created_by")
    serializer_class = NoticeSerializer
    permission_classes = [AdminArea]
    staff_actions = {"create", "update", "partial_update"}
    pagination_class = None
    audit_entity = "notice"

    def get_save_kwargs(self) -> dict:
        return {**super().get_save_kwargs(), "created_by": self.request.user}

    def perform_update(self, serializer):
        before = snapshot(serializer.instance)
        instance = serializer.save()
        after = snapshot(instance)
        changed = [k for k in after if after[k] != before.get(k) and k != "updated_at"]
        if changed:
            self.record_audit(
                "updated",
                instance,
                before={k: before.get(k) for k in changed},
                after={k: after[k] for k in changed},
            )
