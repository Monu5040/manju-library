from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .balance_sheet import UNDO_DAYS
from .models import CashClosing, LedgerCategory, LedgerEntry, LedgerImport


class LedgerCategorySerializer(serializers.ModelSerializer):
    entry_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = LedgerCategory
        fields = ["id", "name", "kind", "code", "sort_order", "is_active", "entry_count"]
        read_only_fields = ["code"]
        validators = []  # the friendlier duplicate check is in validate()

    def validate_name(self, value):
        return " ".join(value.split())

    def validate(self, attrs):
        instance = self.instance
        kind = attrs.get("kind", instance.kind if instance else None)
        name = attrs.get("name", instance.name if instance else "")
        clash = LedgerCategory.objects.filter(kind=kind, name__iexact=name)
        if instance:
            clash = clash.exclude(pk=instance.pk)
        if clash.exists():
            raise serializers.ValidationError({"name": "A category with this name already exists."})
        if instance and "kind" in attrs and attrs["kind"] != instance.kind:
            if instance.code or instance.entries.exists():
                raise serializers.ValidationError(
                    {"kind": "This category is in use. Add a new category instead."}
                )
        return attrs


class LedgerEntrySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    kind = serializers.CharField(source="category.kind", read_only=True)
    mode_label = serializers.CharField(source="get_mode_display", read_only=True)
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True, default=None
    )
    voided_by_name = serializers.CharField(
        source="voided_by.full_name", read_only=True, default=None
    )

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "category",
            "category_name",
            "kind",
            "entry_date",
            "amount",
            "mode",
            "mode_label",
            "party",
            "details",
            "reference",
            "source",
            "source_label",
            "created_by_name",
            "created_at",
            "is_void",
            "void_reason",
            "voided_at",
            "voided_by_name",
        ]
        read_only_fields = ["source", "is_void", "void_reason", "voided_at", "created_at"]

    def validate_category(self, value):
        unchanged = self.instance is not None and self.instance.category_id == value.pk
        if not value.is_active and not unchanged:
            raise serializers.ValidationError("This category is turned off.")
        return value

    def validate_entry_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("The date cannot be in the future.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Enter an amount above zero.")
        return value

    def validate(self, attrs):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from .services import ensure_cash_day_open

        instance = self.instance
        day = attrs.get("entry_date", instance.entry_date if instance else None)
        mode = attrs.get("mode", instance.mode if instance else "CASH")
        branch = self.context.get("branch") or (instance.branch if instance else None)
        moved = instance is None or "entry_date" in attrs or "mode" in attrs or "amount" in attrs
        if branch is not None and day is not None and moved:
            try:
                ensure_cash_day_open(branch, day, mode, field="entry_date")
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
        return attrs


class VoidEntrySerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)


class CashClosingSerializer(serializers.ModelSerializer):
    difference = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    closed_by_name = serializers.CharField(
        source="closed_by.full_name", read_only=True, default=None
    )

    class Meta:
        model = CashClosing
        fields = [
            "id",
            "day",
            "period_start",
            "opening",
            "cash_in",
            "cash_out",
            "removed",
            "expected",
            "counted",
            "difference",
            "note",
            "closed_by_name",
            "created_at",
        ]


class CloseDaySerializer(serializers.Serializer):
    day = serializers.DateField()
    counted = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    removed = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, default=0)
    opening = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class LedgerImportSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True, default=None
    )
    can_undo = serializers.SerializerMethodField()

    class Meta:
        model = LedgerImport
        fields = [
            "id",
            "file_name",
            "sheet",
            "status",
            "status_label",
            "summary",
            "created_by_name",
            "created_at",
            "imported_at",
            "undone_at",
            "can_undo",
        ]

    def get_can_undo(self, obj) -> bool:
        return bool(
            obj.status == LedgerImport.Status.IMPORTED
            and obj.imported_at
            and timezone.now() - obj.imported_at <= timedelta(days=UNDO_DAYS)
        )


class LedgerImportDetailSerializer(LedgerImportSerializer):
    income = serializers.SerializerMethodField()
    expenses = serializers.SerializerMethodField()
    errors = serializers.SerializerMethodField()

    class Meta(LedgerImportSerializer.Meta):
        fields = [*LedgerImportSerializer.Meta.fields, "income", "expenses", "errors"]

    def get_income(self, obj) -> list:
        return obj.plan.get("income", [])

    def get_expenses(self, obj) -> list:
        return obj.plan.get("expenses", [])

    def get_errors(self, obj) -> list:
        return obj.plan.get("errors", [])
