import re

from rest_framework import serializers

from .models import MOBILE_PATTERN, Role, User, normalize_mobile


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


class StaffSerializer(serializers.ModelSerializer):
    """Admin and staff accounts, managed by the Super Admin."""

    mobile = MobileField()
    password = serializers.CharField(write_only=True, required=False, min_length=12, max_length=128)
    has_authenticator = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "mobile",
            "email",
            "role",
            "can_export",
            "is_active",
            "last_login",
            "date_joined",
            "has_authenticator",
            "password",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def get_has_authenticator(self, obj) -> bool:
        from django_otp.plugins.otp_totp.models import TOTPDevice

        return TOTPDevice.objects.filter(user=obj, confirmed=True).exists()

    def validate_role(self, value):
        if value not in (Role.STAFF, Role.SUPER_ADMIN):
            raise serializers.ValidationError("Staff accounts are Staff or Super Admin.")
        return value

    def validate_email(self, value):
        return value or None

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "Set a first password (12+ characters)."}
            )
        if attrs.get("password"):
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError as DjangoValidationError

            try:
                validate_password(attrs["password"], user=self.instance)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128)
    new_password = serializers.CharField(min_length=12, max_length=128)
