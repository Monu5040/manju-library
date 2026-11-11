"""
What students see about themselves. Staff-only details (internal notes, who collected a
payment, void reasons) are deliberately left out.
"""

from rest_framework import serializers

from accounts.serializers import MobileField
from billing.models import Payment
from library.models import Plan, Shift
from members.models import Membership, Student
from members.serializers import pick_current

from .models import Notice


class PortalMembershipSerializer(serializers.ModelSerializer):
    seat_number = serializers.CharField(source="seat.number", default=None)
    shift_name = serializers.CharField(source="shift.name", default=None)
    plan_name = serializers.CharField(source="plan.name", default=None)
    time_label = serializers.CharField()
    state = serializers.CharField()
    days_left = serializers.IntegerField()
    net_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    due_total = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "seat_number",
            "shift_name",
            "plan_name",
            "time_label",
            "start_date",
            "end_date",
            "state",
            "days_left",
            "price",
            "discount",
            "net_fee",
            "paid_total",
            "due_total",
        ]

    def get_due_total(self, obj) -> float:
        if obj.status == Membership.Status.CANCELLED:
            return 0.0
        return float(max(obj.due_total, 0))


class PortalPaymentSerializer(serializers.ModelSerializer):
    mode_label = serializers.CharField(source="get_mode_display")

    class Meta:
        model = Payment
        fields = ["id", "receipt_no", "paid_on", "amount", "mode_label", "reference", "is_void"]


class PortalStudentSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name")
    aadhaar_masked = serializers.CharField()
    current_membership = serializers.SerializerMethodField()
    total_due = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "roll_no",
            "full_name",
            "father_name",
            "mobile",
            "alt_mobile",
            "address",
            "aadhaar_masked",
            "admission_date",
            "status",
            "branch_name",
            "current_membership",
            "total_due",
        ]

    def get_current_membership(self, obj):
        current = pick_current(list(obj.memberships.all()))
        return PortalMembershipSerializer(current).data if current else None

    def get_total_due(self, obj) -> float:
        return float(
            sum(
                max(m.due_total, 0)
                for m in obj.memberships.all()
                if m.status != Membership.Status.CANCELLED
            )
        )


class PortalProfileUpdateSerializer(serializers.ModelSerializer):
    """Students may update how to reach them; everything else goes through the desk."""

    alt_mobile = MobileField(required=False, allow_blank=True)

    class Meta:
        model = Student
        fields = ["address", "alt_mobile"]


class NoticeSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.full_name", default=None, read_only=True
    )

    class Meta:
        model = Notice
        fields = [
            "id",
            "title",
            "body",
            "starts_on",
            "ends_on",
            "is_pinned",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        starts = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts and ends and ends < starts:
            raise serializers.ValidationError({"ends_on": "The notice ends before it starts."})
        return attrs


class PortalNoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ["id", "title", "body", "starts_on", "ends_on", "is_pinned"]


class PortalShiftSerializer(serializers.ModelSerializer):
    time_label = serializers.CharField()
    hours = serializers.FloatField()

    class Meta:
        model = Shift
        fields = ["id", "name", "time_label", "hours"]


class PortalPlanSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(source="shift.name", default=None)

    class Meta:
        model = Plan
        fields = ["id", "name", "duration_months", "shift_name", "price"]
