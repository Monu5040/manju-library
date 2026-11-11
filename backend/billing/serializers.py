from decimal import Decimal

from rest_framework import serializers

from members.models import Membership, Student

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    roll_no = serializers.IntegerField(source="student.roll_no", read_only=True)
    collected_by_name = serializers.CharField(
        source="collected_by.full_name", read_only=True, default=None
    )
    mode_label = serializers.CharField(source="get_mode_display", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_no",
            "student",
            "student_name",
            "roll_no",
            "membership",
            "amount",
            "mode",
            "mode_label",
            "paid_on",
            "reference",
            "notes",
            "collected_by_name",
            "is_void",
            "void_reason",
            "voided_at",
            "created_at",
        ]
        read_only_fields = fields


class PaymentCreateSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    membership = serializers.PrimaryKeyRelatedField(
        queryset=Membership.objects.all(), required=False, allow_null=True
    )
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    mode = serializers.ChoiceField(choices=Payment.Mode.choices, default=Payment.Mode.CASH)
    paid_on = serializers.DateField(required=False)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=80)
    notes = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        branch = self.context.get("branch")
        if branch is not None:
            self.fields["student"].queryset = Student.objects.filter(branch=branch)
            self.fields["membership"].queryset = Membership.objects.filter(branch=branch)

    def validate(self, attrs):
        membership = attrs.get("membership")
        if membership is not None and membership.student_id != attrs["student"].pk:
            raise serializers.ValidationError(
                {"membership": "This membership belongs to another student."}
            )
        return attrs


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)
