from urllib.parse import quote

from rest_framework import serializers

from core.sms import reminder_ready

from .models import AutomationSettings, Reminder
from .services import PLACEHOLDERS

TEXT_FIELDS = ("text_expiring_soon", "text_expires_today", "text_dues", "text_waitlist")


class ReminderSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    channel_label = serializers.CharField(source="get_channel_display", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    roll_no = serializers.IntegerField(source="student.roll_no", read_only=True)
    sent_by_name = serializers.CharField(source="sent_by.full_name", read_only=True, default=None)
    whatsapp_url = serializers.SerializerMethodField()

    class Meta:
        model = Reminder
        fields = [
            "id",
            "kind",
            "kind_label",
            "status",
            "status_label",
            "channel",
            "channel_label",
            "for_date",
            "student",
            "student_name",
            "roll_no",
            "mobile",
            "message",
            "details",
            "note",
            "sent_at",
            "sent_by_name",
            "whatsapp_url",
        ]

    def get_whatsapp_url(self, obj) -> str:
        """Opens WhatsApp (phone or web) on a chat with the student, message already typed."""
        return f"https://wa.me/91{obj.mobile}?text={quote(obj.message)}"


class MarkSentSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(
        choices=[c for c in Reminder.Channel.choices if c[0] != Reminder.Channel.SMS]
    )


class SkipSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class AutomationSettingsSerializer(serializers.ModelSerializer):
    sms = serializers.SerializerMethodField()
    placeholders = serializers.SerializerMethodField()

    class Meta:
        model = AutomationSettings
        fields = [
            "reminders_enabled",
            "days_before_expiry",
            "remind_on_expiry_day",
            "dues_after_days",
            "dues_repeat_days",
            "waitlist_alerts",
            "send_sms",
            "mark_left_after_days",
            *TEXT_FIELDS,
            "sms",
            "placeholders",
        ]

    def get_sms(self, obj) -> dict:
        """Which reminders can go out by SMS on their own: each needs an approved template."""
        return {kind: reminder_ready(kind) for kind in Reminder.Kind.values}

    def get_placeholders(self, obj) -> dict:
        return PLACEHOLDERS

    def validate(self, attrs):
        limits = {
            "days_before_expiry": 30,
            "dues_after_days": 90,
            "dues_repeat_days": 90,
            "mark_left_after_days": 365,
        }
        errors = {
            field: f"Use a number from 0 to {top}."
            for field, top in limits.items()
            if field in attrs and attrs[field] > top
        }
        for field in TEXT_FIELDS:
            if field in attrs:
                text = attrs[field].strip()
                if not text:
                    errors[field] = "Write the message, or turn this reminder off."
                elif len(text) > 500:
                    errors[field] = "Keep the message under 500 characters."
                attrs[field] = text
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
