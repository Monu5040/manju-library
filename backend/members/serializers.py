from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Max
from rest_framework import serializers

from accounts.serializers import MobileField
from billing.models import Payment
from core.validators import validate_aadhaar
from library.models import Plan, Seat, Shift

from .models import Membership, Student, WaitlistEntry
from .services import default_end_date, ensure_login_account, set_aadhaar


def _as_drf_error(exc: DjangoValidationError) -> serializers.ValidationError:
    return serializers.ValidationError(
        exc.message_dict if hasattr(exc, "error_dict") else exc.messages
    )


def pick_current(memberships):
    """The membership a person most likely means: active now, else next, else the latest."""
    live = [m for m in memberships if m.status != Membership.Status.CANCELLED]
    for wanted in (Membership.State.ACTIVE, Membership.State.UPCOMING):
        found = [m for m in live if m.state == wanted]
        if found:
            return min(found, key=lambda m: m.start_date)
    return max(live, key=lambda m: m.end_date) if live else None


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------


class MembershipSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    roll_no = serializers.IntegerField(source="student.roll_no", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    shift_name = serializers.CharField(source="shift.name", read_only=True, default=None)
    seat_number = serializers.CharField(source="seat.number", read_only=True, default=None)
    time_label = serializers.CharField(read_only=True)
    state = serializers.CharField(read_only=True)
    days_left = serializers.IntegerField(read_only=True)
    net_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paid_total = serializers.SerializerMethodField()
    due_total = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "student",
            "student_name",
            "roll_no",
            "plan",
            "plan_name",
            "shift",
            "shift_name",
            "custom_start_time",
            "custom_end_time",
            "time_label",
            "seat",
            "seat_number",
            "start_date",
            "end_date",
            "price",
            "discount",
            "net_fee",
            "paid_total",
            "due_total",
            "status",
            "state",
            "days_left",
            "renewed_from",
            "notes",
            "created_at",
        ]

    def _paid(self, obj) -> Decimal:
        if hasattr(obj, "paid_total"):
            return obj.paid_total
        return sum((p.amount for p in obj.payments.all() if not p.is_void), start=Decimal("0"))

    def get_paid_total(self, obj) -> float:
        return float(self._paid(obj))

    def get_due_total(self, obj) -> float:
        if obj.status == Membership.Status.CANCELLED:
            return 0.0
        return float(obj.net_fee - self._paid(obj))


class BranchScopedFieldsMixin:
    """Restricts related-record choices to the current branch."""

    branch_scoped = {"plan": Plan, "shift": Shift, "seat": Seat, "student": Student}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        branch = self.context.get("branch")
        if branch is None:
            return
        for name, model in self.branch_scoped.items():
            if name in self.fields:
                self.fields[name].queryset = model.objects.filter(branch=branch)


class MembershipTermsSerializer(BranchScopedFieldsMixin, serializers.Serializer):
    """Seat, shift, dates and fee, as entered on the admission or renewal form."""

    plan = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.all(), required=False, allow_null=True
    )
    shift = serializers.PrimaryKeyRelatedField(
        queryset=Shift.objects.all(), required=False, allow_null=True
    )
    custom_start_time = serializers.TimeField(required=False, allow_null=True)
    custom_end_time = serializers.TimeField(required=False, allow_null=True)
    seat = serializers.PrimaryKeyRelatedField(
        queryset=Seat.objects.all(), required=False, allow_null=True
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False)
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, min_value=Decimal("0")
    )
    discount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=Decimal("0"),
        default=Decimal("0"),
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        plan = attrs.get("plan")
        if not attrs.get("end_date"):
            attrs["end_date"] = default_end_date(
                attrs["start_date"], plan.duration_months if plan else 1
            )
        if attrs.get("price") is None:
            if plan is None:
                raise serializers.ValidationError({"price": "Enter the fee or choose a plan."})
            attrs["price"] = plan.price
        if plan and plan.shift_id and not attrs.get("shift") and not attrs.get("custom_start_time"):
            attrs["shift"] = plan.shift
        return attrs


class NewMembershipSerializer(MembershipTermsSerializer):
    """A membership for an existing student (for example from the waiting list)."""

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())


class MembershipWriteSerializer(BranchScopedFieldsMixin, serializers.ModelSerializer):
    """Editing an existing membership: change seat, shift, dates or fee."""

    class Meta:
        model = Membership
        fields = [
            "plan",
            "shift",
            "custom_start_time",
            "custom_end_time",
            "seat",
            "start_date",
            "end_date",
            "price",
            "discount",
            "notes",
        ]


class PaymentInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    mode = serializers.ChoiceField(choices=Payment.Mode.choices, default=Payment.Mode.CASH)
    paid_on = serializers.DateField(required=False)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=80)


class RenewSerializer(MembershipTermsSerializer):
    start_date = serializers.DateField(required=False)
    payment = PaymentInputSerializer(required=False, allow_null=True)

    def validate(self, attrs):
        # Renewal defaults (start after the old end, same seat and shift) are filled in by
        # members.services.renew_membership; only check what was sent here.
        if (
            attrs.get("start_date")
            and attrs.get("end_date")
            and attrs["end_date"] < attrs["start_date"]
        ):
            raise serializers.ValidationError(
                {"end_date": "The end date is before the start date."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------


class StudentSerializer(serializers.ModelSerializer):
    aadhaar_masked = serializers.CharField(read_only=True)
    current_membership = serializers.SerializerMethodField()
    total_due = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "roll_no",
            "full_name",
            "gender",
            "father_name",
            "mobile",
            "alt_mobile",
            "aadhaar_masked",
            "address",
            "admission_date",
            "status",
            "notes",
            "created_at",
            "current_membership",
            "total_due",
        ]

    def get_current_membership(self, obj):
        current = pick_current(list(obj.memberships.all()))
        if current is None:
            return None
        data = MembershipSerializer(current, context=self.context).data
        keep = (
            "id",
            "seat_number",
            "shift_name",
            "time_label",
            "plan_name",
            "start_date",
            "end_date",
            "days_left",
            "state",
            "due_total",
        )
        return {key: data[key] for key in keep}

    def get_total_due(self, obj) -> float:
        serializer = MembershipSerializer(context=self.context)
        return float(
            sum(
                Decimal(str(serializer.get_due_total(m)))
                for m in obj.memberships.all()
                if m.status != Membership.Status.CANCELLED
            )
        )


class StudentWriteSerializer(serializers.ModelSerializer):
    mobile = MobileField()
    alt_mobile = MobileField(required=False, allow_blank=True)
    aadhaar = serializers.CharField(write_only=True, required=False, allow_blank=True)
    roll_no = serializers.IntegerField(required=False, min_value=1)

    class Meta:
        model = Student
        fields = [
            "roll_no",
            "full_name",
            "gender",
            "father_name",
            "mobile",
            "alt_mobile",
            "aadhaar",
            "address",
            "admission_date",
            "status",
            "notes",
        ]

    def validate_aadhaar(self, value):
        if value:
            try:
                validate_aadhaar(value)
            except DjangoValidationError as exc:
                raise _as_drf_error(exc) from exc
        return value

    def validate_roll_no(self, value):
        branch = self.context.get("branch")
        clash = Student.objects.filter(branch=branch, roll_no=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            top = Student.objects.filter(branch=branch).aggregate(top=Max("roll_no"))["top"]
            raise serializers.ValidationError(
                f"Roll number {value} is taken. The next free one is {top + 1}."
            )
        return value

    def update(self, instance, validated_data):
        aadhaar = validated_data.pop("aadhaar", None)
        mobile_changed = "mobile" in validated_data and validated_data["mobile"] != instance.mobile
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if aadhaar is not None:
            set_aadhaar(instance, aadhaar)
        if mobile_changed:
            ensure_login_account(instance)
        instance.save()
        return instance


class AdmissionSerializer(serializers.Serializer):
    student = StudentWriteSerializer()
    membership = MembershipTermsSerializer()
    payment = PaymentInputSerializer(required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("student", "membership"):
            self.fields[name].context.update(self.context)


# ---------------------------------------------------------------------------
# Waiting list
# ---------------------------------------------------------------------------


class WaitlistEntrySerializer(BranchScopedFieldsMixin, serializers.ModelSerializer):
    branch_scoped = {"student": Student, "preferred_shift": Shift}
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    roll_no = serializers.IntegerField(source="student.roll_no", read_only=True)
    mobile = serializers.CharField(source="student.mobile", read_only=True)
    preferred_shift_name = serializers.CharField(
        source="preferred_shift.name", read_only=True, default=None
    )
    position = serializers.IntegerField(required=False, min_value=1)

    class Meta:
        model = WaitlistEntry
        fields = [
            "id",
            "student",
            "student_name",
            "roll_no",
            "mobile",
            "preferred_shift",
            "preferred_shift_name",
            "position",
            "status",
            "note",
            "created_at",
        ]
