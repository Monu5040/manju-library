import django_filters
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from accounts.permissions import AdminArea, CanExport
from audit import services as audit
from audit.mixins import snapshot
from core.exports import Column, file_response
from library.branching import BranchScopedMixin
from members.filters import search

from . import online, razorpay
from .models import OnlinePayment, Payment
from .serializers import (
    OnlinePaymentSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
    VoidSerializer,
)
from .services import record_payment, void_payment

PAYMENT_EXPORT_COLUMNS = [
    Column("receipt_no", "Receipt No.", "int", 11),
    Column("paid_on", "Date", "date", 12),
    Column("roll_no", "Roll No.", "int", 9),
    Column("student", "Name", "text", 24),
    Column("amount", "Amount", "money", 12),
    Column("mode", "Paid By", "text", 12),
    Column("reference", "Reference", "text", 18),
    Column("taken_by", "Taken By", "text", 18),
    Column("void", "Void", "text", 7),
    Column("void_reason", "Void Reason", "text", 24),
]


class PaymentFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    paid_from = django_filters.DateFilter(field_name="paid_on", lookup_expr="gte")
    paid_to = django_filters.DateFilter(field_name="paid_on", lookup_expr="lte")

    class Meta:
        model = Payment
        fields = ["student", "membership", "mode", "source", "is_void"]

    def filter_q(self, queryset, name, value):
        value = value.strip()
        if value.isdigit() and len(value) <= 7:
            receipts = queryset.filter(receipt_no=int(value))
            if receipts.exists():
                return receipts
        return search(queryset, value, prefix="student__")


class PaymentViewSet(
    BranchScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    """Payments are recorded and voided, never edited or deleted."""

    queryset = Payment.objects.select_related("student", "collected_by")
    serializer_class = PaymentSerializer
    permission_classes = [AdminArea]
    staff_actions = {"create"}
    filterset_class = PaymentFilter
    ordering_fields = ["paid_on", "receipt_no", "amount"]
    ordering = ["-paid_on", "-receipt_no"]

    def create(self, request, *args, **kwargs):
        serializer = PaymentCreateSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        payment = record_payment(student=data.pop("student"), by=request.user, **data)
        audit.record(
            request,
            "payment.created",
            entity="payment",
            entity_id=payment.pk,
            after=snapshot(payment),
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        """Super Admin only. The receipt number stays used so the sequence has no gaps."""
        payment = self.get_object()
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        void_payment(payment, reason=serializer.validated_data["reason"], by=request.user)
        audit.record(
            request,
            "payment.voided",
            entity="payment",
            entity_id=payment.pk,
            metadata={"reason": payment.void_reason, "amount": str(payment.amount)},
        )
        return Response(PaymentSerializer(payment).data)

    @action(detail=False, methods=["get"], permission_classes=[CanExport])
    def export(self, request):
        payments = list(self.filter_queryset(self.get_queryset()))
        rows = [
            {
                "receipt_no": p.receipt_no,
                "paid_on": p.paid_on,
                "roll_no": p.student.roll_no,
                "student": p.student.full_name,
                "amount": p.amount,
                "mode": p.get_mode_display(),
                "reference": p.reference,
                "taken_by": p.collected_by.full_name
                if p.collected_by
                else ("Online (Razorpay)" if p.source == Payment.Source.ONLINE else ""),
                "void": "Yes" if p.is_void else "",
                "void_reason": p.void_reason,
            }
            for p in payments
        ]
        audit.record(
            request,
            "export.payments",
            entity="payment",
            metadata={
                "rows": len(rows),
                "filters": {k: v for k, v in request.query_params.items() if k != "file_type"},
            },
        )
        return file_response(
            PAYMENT_EXPORT_COLUMNS,
            rows,
            name=f"payments-{timezone.localdate():%Y-%m-%d}",
            file_type=request.query_params.get("file_type", "xlsx"),
            sheet="Payments",
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Totals by payment mode for the filtered payments (for example one day)."""
        payments = self.filter_queryset(self.get_queryset()).filter(is_void=False)
        by_mode = (
            payments.values("mode")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("mode")
        )
        return Response(
            {
                "total": float(payments.aggregate(t=Sum("amount"))["t"] or 0),
                "count": payments.count(),
                "by_mode": [
                    {"mode": row["mode"], "total": float(row["total"]), "count": row["count"]}
                    for row in by_mode
                ],
            }
        )


class OnlinePaymentFilter(django_filters.FilterSet):
    needs_attention = django_filters.BooleanFilter(method="filter_attention")
    closed = django_filters.BooleanFilter(method="filter_closed")

    class Meta:
        model = OnlinePayment
        fields = ["status", "purpose", "student"]

    def filter_attention(self, queryset, name, value):
        return queryset.exclude(problem="") if value else queryset.filter(problem="")

    def filter_closed(self, queryset, name, value):
        """Links that closed without being paid (expired or replaced by a newer one)."""
        closed = [OnlinePayment.Status.EXPIRED, OnlinePayment.Status.CANCELLED]
        return queryset.filter(status__in=closed) if value else queryset.exclude(status__in=closed)


class OnlinePaymentViewSet(
    BranchScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """Online payment attempts. Staff can look and ask Razorpay; the owner clears notes."""

    queryset = OnlinePayment.objects.select_related("student", "payment", "plan")
    serializer_class = OnlinePaymentSerializer
    permission_classes = [AdminArea]
    staff_actions = {"check"}
    filterset_class = OnlinePaymentFilter
    ordering = ["-created_at"]

    @action(detail=True, methods=["post"])
    def check(self, request, pk=None):
        """Ask Razorpay now, instead of waiting for the webhook or the next check."""
        attempt = self.get_object()
        try:
            attempt = online.check(attempt)
        except razorpay.RazorpayError as exc:
            raise ValidationError({"detail": f"Razorpay could not be asked: {exc}"}) from exc
        return Response(OnlinePaymentSerializer(attempt).data)

    @action(detail=True, methods=["post"], url_path="sorted")
    def mark_sorted(self, request, pk=None):
        """Super Admin only: the note was dealt with (a refund made, a renewal fixed...)."""
        attempt = self.get_object()
        if not attempt.problem:
            raise ValidationError({"detail": "There is nothing to sort out on this payment."})
        audit.record(
            request,
            "online_payment.sorted",
            entity="online_payment",
            entity_id=attempt.pk,
            before={"problem": attempt.problem},
            metadata={"note": str(request.data.get("note", ""))[:200]},
        )
        attempt.problem = ""
        attempt.save(update_fields=["problem"])
        return Response(OnlinePaymentSerializer(attempt).data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        attempts = self.get_queryset()
        return Response(
            {
                "configured": razorpay.configured(),
                "test_mode": razorpay.test_mode(),
                # On a deployed server, test mode is limited to RAZORPAY_TEST_MOBILES.
                "test_mobiles_only": razorpay.test_mode() and settings.IS_DEPLOYED,
                "enabled": self.get_branch().allow_online_payments,
                "needs_attention": attempts.exclude(problem="").count(),
                "paid_today": attempts.filter(
                    status=OnlinePayment.Status.PAID, paid_at__date=timezone.localdate()
                ).count(),
                "waiting": attempts.filter(
                    Q(status=OnlinePayment.Status.PENDING) & Q(expires_at__gt=timezone.now())
                ).count(),
            }
        )


class RazorpayWebhookView(APIView):
    """
    Razorpay's server tells us about payment links (paid, expired, cancelled). Every call is
    checked against RAZORPAY_WEBHOOK_SECRET; recording is idempotent, so retries are safe.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get("X-Razorpay-Signature", "")
        try:
            result = online.handle_webhook(request.body, signature)
        except PermissionDenied:
            return Response({"detail": "Bad signature."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"result": result})
