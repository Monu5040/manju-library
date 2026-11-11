import re

from rest_framework import serializers

from .models import MOBILE_PATTERN, User, normalize_mobile


class MobileField(serializers.CharField):
    default_error_messages = {
        "invalid_mobile": "Enter a 10-digit mobile number that starts with 6, 7, 8 or 9.",
    }

    def to_internal_value(self, data):
        mobile = normalize_mobile(super().to_internal_value(data))
        if not re.fullmatch(MOBILE_PATTERN, mobile):
            self.fail("invalid_mobile")
        return mobile


class OtpRequestSerializer(serializers.Serializer):
    mobile = MobileField()


class OtpVerifySerializer(serializers.Serializer):
    mobile = MobileField()
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code."})


class AdminLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class TotpTokenSerializer(serializers.Serializer):
    token = serializers.RegexField(
        r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code from your app."}
    )


class MeSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(source="masked_mobile")
    can_export = serializers.BooleanField(source="may_export")

    class Meta:
        model = User
        fields = ["id", "full_name", "mobile", "email", "role", "can_export"]
