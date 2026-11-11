"""
Ledger API (/api/admin/ledger/..., /api/admin/cash-closings/).

- Staff record expenses and other income and close the cash drawer. They see only the
  entries they recorded themselves (so salaries stay private); the Super Admin sees all,
  edits, voids, manages categories, imports the old Balance Sheet and sees the ledger.
"""

from datetime import date
from decimal import Decimal

import django_filters
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from accounts.models import Role
from accounts.permissions import AdminArea, CanExport, IsSuperAdmin
from audit import services as audit
from audit.mixins import AuditedViewSetMixin, changes, snapshot
from core.exports import Column, file_response
from imports.reader import UnreadableFile
from imports.views import MAX_UPLOAD_BYTES
from library.branching import BranchScopedMixin, current_branch

from . import balance_sheet
from .models import CashClosing, LedgerCategory, LedgerEntry, LedgerImport
from .serializers import (
    CashClosingSerializer,
    CloseDaySerializer,
    LedgerCategorySerializer,
    LedgerEntrySerializer,
    LedgerImportDetailSerializer,
    LedgerImportSerializer,
    VoidEntrySerializer,
)
from .services import close_day, closing_preview, daily_ledger, parse_range, void_entry

ENTRY_EXPORT_COLUMNS = [
    Column("entry_date", "Date", "date", 12),
    Column("kind", "Type", "text", 13),
    Column("category", "Category", "text", 22),
    Column("amount", "Amount", "money", 12),
    Column("mode", "Paid By", "text", 13),
    Column("party", "Paid To / From", "text", 22),
    Column("details", "Details", "text", 36),
    Column("reference", "Bill / Reference", "text", 16),
    Column("source", "Source", "text", 16),
    Column("entered_by", "Entered By", "text", 18),
    Column("void", "Void", "text", 7),
    Column("void_reason", "Void Reason", "text", 24),
]

DAILY_EXPORT_COLUMNS = [
    Column("day", "Date", "date", 12),
    Column("students", "Students Paid", "int", 14),
    Column("fees", "Fees", "money", 12),
    Column("other_income", "Other Income", "money", 13),
    Column("income", "Total Income", "money", 13),
    Column("expenses", "Expenses", "money", 12),
    Column("balance", "Balance", "money", 12),
]


def export_filters(request) -> dict:
    return {k: v for k, v in request.query_params.items() if k != "file_type"}


class LedgerCategoryViewSet(AuditedViewSetMixin, ModelViewSet):
    """Everyone in the admin area reads the list; the Super Admin changes it."""

    # The count groups the query, so the model's default ordering must be repeated here.
    queryset = LedgerCategory.objects.annotate(entry_count=Count("entries")).order_by(
        "kind", "sort_order", "name"
    )
    serializer_class = LedgerCategorySerializer
    permission_classes = [AdminArea]
    pagination_class = None
    audit_entity = "ledger_category"

    def perform_destroy(self, instance):
        if instance.code:
            raise ValidationError({"detail": "The app relies on this category. Turn it off."})
        if instance.entries.exists():
            raise ValidationError({"detail": "This category has entries. Turn it off instead."})
        super().perform_destroy(instance)


class LedgerEntryFilter(django_filters.FilterSet):
    kind = django_filters.ChoiceFilter(
        field_name="category__kind", choices=LedgerCategory.Kind.choices
    )
    date_from = django_filters.DateFilter(field_name="entry_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="entry_date", lookup_expr="lte")
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = LedgerEntry
        fields = ["category", "mode", "source", "is_void"]

    def filter_q(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(details__icontains=value) | Q(party__icontains=value) | Q(reference__icontains=value)
        )


class LedgerEntryViewSet(
    BranchScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    queryset = LedgerEntry.objects.select_related("category", "created_by", "voided_by")
    serializer_class = LedgerEntrySerializer
    permission_classes = [AdminArea]
    staff_actions = {"create"}
    filterset_class = LedgerEntryFilter
    ordering_fields = ["entry_date", "amount", "created_at"]
    ordering = ["-entry_date", "-id"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role != Role.SUPER_ADMIN:
            queryset = queryset.filter(created_by=self.request.user)
        return queryset

    def perform_create(self, serializer):
        entry = serializer.save(branch=self.get_branch(), created_by=self.request.user)
        audit.record(
            self.request,
            "ledger_entry.created",
            entity="ledger_entry",
            entity_id=entry.pk,
            after=snapshot(entry),
        )

    def perform_update(self, serializer):
        if serializer.instance.is_void:
            raise ValidationError({"detail": "A void entry cannot be changed."})
        before = snapshot(serializer.instance)
        entry = serializer.save()
        old, new = changes(before, snapshot(entry))
        if new:
            audit.record(
                self.request,
                "ledger_entry.updated",
                entity="ledger_entry",
                entity_id=entry.pk,
                before=old,
                after=new,
            )

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        """Super Admin only. The entry stays in the ledger, struck through."""
        entry = self.get_object()
        serializer = VoidEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        void_entry(entry, reason=serializer.validated_data["reason"], by=request.user)
        audit.record(
            request,
            "ledger_entry.voided",
            entity="ledger_entry",
            entity_id=entry.pk,
            metadata={"reason": entry.void_reason, "amount": str(entry.amount)},
        )
        return Response(LedgerEntrySerializer(entry).data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Totals of the filtered entries (void ones left out), by type and by category."""
        # order_by() drops the list's date ordering, which would otherwise split the groups.
        entries = self.filter_queryset(self.get_queryset()).filter(is_void=False).order_by()
        totals = {
            row["category__kind"]: row
            for row in entries.values("category__kind").annotate(
                total=Sum("amount"), count=Count("id")
            )
        }
        by_category = (
            entries.values("category", "category__name", "category__kind")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")
        )

        def total(kind):
            return float(totals.get(kind, {}).get("total") or 0)

        return Response(
            {
                "expenses": total(LedgerCategory.Kind.EXPENSE),
                "other_income": total(LedgerCategory.Kind.INCOME),
                "count": sum(row["count"] for row in totals.values()),
                "by_category": [
                    {
                        "category": row["category"],
                        "name": row["category__name"],
                        "kind": row["category__kind"],
                        "total": float(row["total"]),
                        "count": row["count"],
                    }
                    for row in by_category
                ],
            }
        )

    @action(detail=False, methods=["get"], permission_classes=[CanExport])
    def export(self, request):
        entries = list(self.filter_queryset(self.get_queryset()))
        rows = [
            {
                "entry_date": e.entry_date,
                "kind": e.category.get_kind_display(),
                "category": e.category.name,
                "amount": e.amount,
                "mode": e.get_mode_display(),
                "party": e.party,
                "details": e.details,
                "reference": e.reference,
                "source": e.get_source_display(),
                "entered_by": e.created_by.full_name if e.created_by else "",
                "void": "Yes" if e.is_void else "",
                "void_reason": e.void_reason,
            }
            for e in entries
        ]
        audit.record(
            request,
            "export.ledger_entries",
            entity="ledger_entry",
            metadata={"rows": len(rows), "filters": export_filters(request)},
        )
        return file_response(
            ENTRY_EXPORT_COLUMNS,
            rows,
            name=f"expenses-{timezone.localdate():%Y-%m-%d}",
            file_type=request.query_params.get("file_type", "xlsx"),
            sheet="Expenses",
        )


class DailyLedgerView(APIView):
    """The Balance Sheet, day by day. With ?file_type=xlsx|csv it downloads instead."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        branch = current_branch(request)
        start, end = parse_range(request.query_params)
        ledger = daily_ledger(branch, start, end)
        file_type = request.query_params.get("file_type")
        if file_type:
            rows = [*ledger["days"], {"day": "Total", **ledger["totals"]}]
            audit.record(
                request,
                "export.ledger_daily",
                entity="ledger",
                metadata={"rows": len(ledger["days"]), "filters": export_filters(request)},
            )
            return file_response(
                DAILY_EXPORT_COLUMNS,
                rows,
                name=f"ledger-{start:%Y-%m-%d}-to-{end:%Y-%m-%d}",
                file_type=file_type,
                sheet="Ledger",
            )
        money = ("fees", "other_income", "income", "expenses", "balance")

        def clean(row):
            return {k: float(v) if k in money else v for k, v in row.items()}

        return Response(
            {
                "from": ledger["from"],
                "to": ledger["to"],
                "days": [clean(row) for row in ledger["days"]],
                "totals": clean(ledger["totals"]),
            }
        )


class CashClosingViewSet(
    BranchScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    """Staff and the Super Admin close days in order; only the Super Admin reopens one."""

    queryset = CashClosing.objects.select_related("closed_by")
    serializer_class = CashClosingSerializer
    permission_classes = [AdminArea]
    staff_actions = {"create"}

    def create(self, request, *args, **kwargs):
        serializer = CloseDaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        closing = close_day(branch=self.get_branch(), by=request.user, **serializer.validated_data)
        audit.record(
            request,
            "cash_closing.created",
            entity="cash_closing",
            entity_id=closing.pk,
            after=snapshot(closing),
        )
        return Response(CashClosingSerializer(closing).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        latest = self.get_queryset().order_by("-day").first()
        if latest is None or latest.pk != instance.pk:
            raise ValidationError({"detail": "Only the latest closing can be reopened."})
        before = snapshot(instance)
        pk = instance.pk
        instance.delete()
        audit.record(
            self.request,
            "cash_closing.reopened",
            entity="cash_closing",
            entity_id=pk,
            before=before,
        )

    @action(detail=False, methods=["get"])
    def preview(self, request):
        day_text = request.query_params.get("day")
        try:
            day = date.fromisoformat(day_text) if day_text else timezone.localdate()
        except ValueError as exc:
            raise ValidationError({"day": "Use the format YYYY-MM-DD."}) from exc
        preview = closing_preview(self.get_branch(), day)
        closing = preview.pop("closing")
        return Response(
            {
                **{k: float(v) if isinstance(v, Decimal) else v for k, v in preview.items()},
                "closing": CashClosingSerializer(closing).data if closing else None,
            }
        )


class LedgerImportViewSet(
    BranchScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """Upload the old Balance Sheet → check (nothing saved) → import → undo within 7 days."""

    queryset = LedgerImport.objects.select_related("created_by")
    permission_classes = [IsSuperAdmin]
    parser_classes = [JSONParser, MultiPartParser]

    def get_serializer_class(self):
        return LedgerImportSerializer if self.action == "list" else LedgerImportDetailSerializer

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Choose the Excel or CSV file with the Balance Sheet."})
        if upload.size > MAX_UPLOAD_BYTES:
            raise ValidationError({"file": "Files up to 10 MB only."})
        try:
            job = balance_sheet.check(
                branch=self.get_branch(),
                file_name=upload.name,
                content=upload.read(),
                by=request.user,
            )
        except UnreadableFile as exc:
            raise ValidationError({"file": str(exc)}) from exc
        audit.record(
            request,
            "ledger_import.checked",
            entity="ledger_import",
            entity_id=job.pk,
            metadata={"file": job.file_name, **job.summary},
        )
        return Response(LedgerImportDetailSerializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def commit(self, request, pk=None):
        job = balance_sheet.commit(self.get_object(), by=request.user)
        audit.record(
            request,
            "ledger_import.imported",
            entity="ledger_import",
            entity_id=job.pk,
            metadata={"file": job.file_name, **job.summary},
        )
        return Response(LedgerImportDetailSerializer(job).data)

    @action(detail=True, methods=["post"])
    def undo(self, request, pk=None):
        job = balance_sheet.undo(self.get_object(), by=request.user)
        audit.record(
            request,
            "ledger_import.undone",
            entity="ledger_import",
            entity_id=job.pk,
            metadata={"file": job.file_name, "removed": job.summary.get("removed")},
        )
        return Response(LedgerImportDetailSerializer(job).data)
