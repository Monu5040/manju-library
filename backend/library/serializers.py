from rest_framework import serializers

from .models import Branch, Plan, Seat, Shift


class BranchSerializer(serializers.ModelSerializer):
    # Whether the server has Razorpay keys; the switch does nothing without them.
    online_payments_ready = serializers.SerializerMethodField()
    online_payments_test_mode = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "address",
            "phone",
            "allow_seat_sharing",
            "allow_online_payments",
            "online_payments_ready",
            "online_payments_test_mode",
            "is_active",
        ]
        read_only_fields = ["code"]

    def get_online_payments_ready(self, obj) -> bool:
        from billing import razorpay

        return razorpay.configured()

    def get_online_payments_test_mode(self, obj) -> bool:
        from billing import razorpay

        return razorpay.configured() and razorpay.test_mode()


class ShiftSerializer(serializers.ModelSerializer):
    hours = serializers.FloatField(read_only=True)
    time_label = serializers.CharField(read_only=True)

    class Meta:
        model = Shift
        fields = [
            "id",
            "name",
            "start_time",
            "end_time",
            "sort_order",
            "is_active",
            "hours",
            "time_label",
        ]

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start is not None and start == end:
            raise serializers.ValidationError({"end_time": "The shift must end at another time."})
        return attrs


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ["id", "number", "label", "is_active"]


class SeatRangeSerializer(serializers.Serializer):
    first = serializers.IntegerField(min_value=1, max_value=999)
    last = serializers.IntegerField(min_value=1, max_value=999)

    def validate(self, attrs):
        if attrs["last"] < attrs["first"]:
            raise serializers.ValidationError({"last": "The last seat is before the first."})
        return attrs


class PlanSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(source="shift.name", read_only=True, default=None)

    class Meta:
        model = Plan
        fields = ["id", "name", "duration_months", "shift", "shift_name", "price", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        branch = self.context.get("branch")
        if branch is not None:
            self.fields["shift"].queryset = Shift.objects.filter(branch=branch)

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("The price cannot be negative.")
        return value
