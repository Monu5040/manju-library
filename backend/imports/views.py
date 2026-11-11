from datetime import date

from django.utils import timezone
from rest_framework import mixins, serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from accounts.permissions import IsSuperAdmin
from audit import services as audit
from core.exports import Column, file_response
from library.branching import current_branch

from . import services
from .columns import FIELDS
from .models import ImportJob, ImportRow
from .reader import UnreadableFile

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PREVIEW_ROWS = 5


class ImportRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRow
        fields = ["row_number", "raw", "result", "errors", "warnings"]


class ImportJobSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", default=None)
    can_undo = serializers.SerializerMethodField()

    class Meta:
        model = ImportJob
        fields = [
            "id",
            "file_name",
            "file_format",
            "sheet",
            "header_row",
            "mapping",
            "options",
            "status",
            "summary",
            "created_by_name",
            "created_at",
            "imported_at",
            "undone_at",
            "can_undo",
        ]

    def get_can_undo(self, obj) -> bool:
        return (
            obj.status == ImportJob.Status.IMPORTED
            and obj.imported_at is not None
            and timezone.now() - obj.imported_at <= services.UNDO_WINDOW
        )


class CheckSettingsSerializer(serializers.Serializer):
    sheet = serializers.CharField(required=False, allow_blank=True)
    header_row = serializers.IntegerField(required=False, min_value=0)
    mapping = serializers.DictField(child=serializers.IntegerField(min_value=0), required=False)
    create_missing = serializers.BooleanField(required=False)
    day_first = serializers.BooleanField(required=False)

    def validate_mapping(self, value):
        unknown = set(value) - set(FIELDS)
        if unknown:
            raise serializers.ValidationError(f"Unknown fields: {', '.join(sorted(unknown))}")
        if len(set(value.values())) != len(value):
            raise serializers.ValidationError("One column is matched to two fields.")
        return value


TEMPLATE_COLUMNS = [
    Column("roll_no", "Roll No.", "int", 9),
    Column("full_name", "Name", "text", 24),
    Column("father_name", "Father's Name", "text", 24),
    Column("gender", "Gender", "text", 10, ("Female", "Male", "Other")),
    Column("mobile", "Mobile No.", "text", 14),
    Column("aadhaar", "Aadhaar No.", "text", 16),
    Column("admission_date", "Admission Date", "date", 14),
    Column("seat", "Seat No.", "text", 9),
    Column("shift", "Study Shift", "text", 22),
    Column("custom_shift", "Additional Shift", "text", 20),
    Column("start_date", "Re-newed Date", "date", 14),
    Column("plan_months", "Plan", "int", 7, ("1", "2", "3", "6", "12")),
    Column("end_date", "Expiry Date", "date", 14),
    Column("price", "Shift Charge", "money", 12),
    Column("paid", "Fee Deposited", "money", 13),
    Column("paid_on", "Paid Date", "date", 12),
    Column("receipt_no", "New Receipt No.", "int", 15),
    Column("notes", "Remarks", "text", 24),
]

TEMPLATE_EXAMPLE = {
    "roll_no": 1,
    "full_name": "Example Student",
    "father_name": "Example Father",
    "gender": "Female",
    "mobile": "9000000000",
    "aadhaar": "",
    "admission_date": date(2026, 1, 5),
    "seat": "12",
    "shift": "10:15 AM - 06:30 PM",
    "start_date": date(2026, 1, 5),
    "plan_months": 1,
    "end_date": date(2026, 2, 4),
    "price": 450,
    "paid": 450,
    "paid_on": date(2026, 1, 5),
    "notes": "Delete this example row",
}


class ImportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    """
    Upload → check (dry run, change settings and re-check) → import → undo within 7 days.
    Super Admin only: an import writes many records at once.
    """

    serializer_class = ImportJobSerializer
    permission_classes = [IsSuperAdmin]
    parser_classes = [JSONParser, MultiPartParser]

    def get_queryset(self):
        return ImportJob.objects.filter(branch=current_branch(self.request)).select_related(
            "created_by"
        )

    def _detail(self, job, table=None):
        table = table or services.job_table(job)
        header_row = job.header_row
        preview = [
            [str(v) if v is not None else "" for v in row]
            for row in table.rows[header_row + 1 : header_row + 1 + PREVIEW_ROWS]
        ]
        problems = job.rows.exclude(result=ImportRow.Result.READY).exclude(
            result=ImportRow.Result.IMPORTED
        )
        return {
            **ImportJobSerializer(job).data,
            "sheets": table.sheets,
            "encoding": table.encoding,
            "delimiter": table.delimiter,
            "columns": services.columns_for(job, table),
            "fields": [{"key": key, "label": label} for key, (label, _) in services_fields()],
            "preview": preview,
            "problem_rows": ImportRowSerializer(
                problems.order_by("row_number")[:300], many=True
            ).data,
            "warning_rows": ImportRowSerializer(
                job.rows.filter(result=ImportRow.Result.READY).exclude(warnings=[])[:300], many=True
            ).data,
        }

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Choose an Excel or CSV file."})
        if upload.size > MAX_UPLOAD_BYTES:
            raise ValidationError({"file": "Files up to 10 MB only. Split larger files."})
        content = upload.read()
        try:
            job, table = services.setup_job(
                branch=current_branch(request),
                file_name=upload.name,
                content=content,
                by=request.user,
            )
        except UnreadableFile as exc:
            raise ValidationError({"file": str(exc)}) from exc
        duplicate = (
            ImportJob.objects.filter(
                branch=job.branch, file_hash=job.file_hash, status=ImportJob.Status.IMPORTED
            )
            .exclude(pk=job.pk)
            .first()
        )
        services.check(job, table)
        audit.record(
            request,
            "import.uploaded",
            entity="import",
            entity_id=job.pk,
            metadata={"file": job.file_name},
        )
        data = self._detail(job, table)
        if duplicate:
            data["duplicate_of"] = {"id": duplicate.pk, "imported_at": duplicate.imported_at}
        return Response(data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return Response(self._detail(self.get_object()))

    @action(detail=True, methods=["post"])
    def check(self, request, pk=None):
        job = self.get_object()
        if job.status != ImportJob.Status.CHECKED:
            raise ValidationError({"detail": "This file was already imported."})
        settings = CheckSettingsSerializer(data=request.data)
        settings.is_valid(raise_exception=True)
        data = settings.validated_data
        if "sheet" in data and data["sheet"] != job.sheet:
            job.sheet = data["sheet"]
            table = services.job_table(job)
            job.header_row = services.detect_header_row(table.rows)
            job.mapping = services.auto_mapping(table.rows[job.header_row] if table.rows else [])
        if "header_row" in data:
            job.header_row = data["header_row"]
        if "mapping" in data:
            job.mapping = data["mapping"]
        for option in ("create_missing", "day_first"):
            if option in data:
                job.options = {**job.options, option: data[option]}
        job.save(update_fields=["sheet", "header_row", "mapping", "options"])
        table = services.job_table(job)
        if job.header_row >= len(table.rows):
            raise ValidationError({"header_row": "That row is past the end of the sheet."})
        services.check(job, table)
        return Response(self._detail(job, table))

    @action(detail=True, methods=["post"])
    def commit(self, request, pk=None):
        job = services.commit(
            self.get_object(), by=request.user, skip_errors=bool(request.data.get("skip_errors"))
        )
        audit.record(
            request, "import.committed", entity="import", entity_id=job.pk, metadata=job.summary
        )
        return Response(self._detail(job))

    @action(detail=True, methods=["post"])
    def undo(self, request, pk=None):
        job = services.undo(self.get_object(), by=request.user)
        audit.record(
            request, "import.undone", entity="import", entity_id=job.pk, metadata=job.summary
        )
        return Response(self._detail(job))

    @action(detail=True, methods=["get"], url_path="error-file")
    def error_file(self, request, pk=None):
        """Rows that were not imported, with the reason, to fix in Excel and upload again."""
        job = self.get_object()
        rows = list(
            job.rows.exclude(result__in=[ImportRow.Result.READY, ImportRow.Result.IMPORTED])
        )
        headers: list[str] = []
        for row in rows:
            headers.extend(h for h in row.raw if h not in headers)
        columns = [Column("_row", "Row", "int", 6), Column("_error", "Error", "text", 50)]
        columns += [Column(h, h, "text", 16) for h in headers]
        data = [{"_row": r.row_number, "_error": " | ".join(r.errors), **r.raw} for r in rows]
        name = f"errors-{job.file_name.rsplit('.', 1)[0]}"
        return file_response(
            columns,
            data,
            name=name,
            file_type=request.query_params.get("file_type", "xlsx"),
            sheet="Errors",
        )

    @action(detail=False, methods=["get"])
    def template(self, request):
        file_type = request.query_params.get("file_type", "xlsx")
        return file_response(
            TEMPLATE_COLUMNS,
            [TEMPLATE_EXAMPLE],
            name="students-template",
            file_type=file_type,
            sheet="Students",
        )


def services_fields():
    return FIELDS.items()
