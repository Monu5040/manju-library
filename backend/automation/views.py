"""
Reminders API (/api/admin/reminders/, /api/admin/automation/). Staff work through the list
(send on WhatsApp, mark done, skip); only the Super Admin changes the settings.
"""

from django.db.models import Count
from django.utils import timezone
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from accounts.permissions import AdminArea
from audit import services as audit
from audit.mixins import changes, snapshot
from library.branching import BranchScopedMixin, current_branch

from . import services
from .models import AutomationSettings, Reminder
from .serializers import (
    AutomationSettingsSerializer,
    MarkSentSerializer,
    ReminderSerializer,
    SkipSerializer,
)

OPEN = [Reminder.Status.PENDING, Reminder.Status.FAILED]


class ReminderViewSet(BranchScopedMixin, mixins.ListModelMixin, GenericViewSet):
    queryset = Reminder.objects.select_related("student", "sent_by")
    serializer_class = ReminderSerializer
    permission_classes = [AdminArea]
    staff_actions = {"refresh", "sent", "skip", "reopen"}
    filterset_fields = ["status", "kind", "student"]
    ordering_fields = ["for_date", "sent_at", "created_at"]
    ordering = ["for_date", "kind", "id"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("open") == "1":
            queryset = queryset.filter(status__in=OPEN)
        elif self.request.query_params.get("done") == "1":
            queryset = queryset.exclude(status__in=OPEN)
        return queryset

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        """Close reminders that no longer apply and add the ones due now. Sends nothing."""
        return Response(services.refresh(self.get_branch()))

    @action(detail=False, methods=["get"])
    def summary(self, request):
        counts = dict(
            Reminder.objects.filter(branch=self.get_branch(), status__in=OPEN)
            .values_list("kind")
            .annotate(n=Count("id"))
            .order_by()
        )
        return Response({"open": sum(counts.values()), "by_kind": counts})

    def _get_open(self) -> Reminder:
        reminder = self.get_object()
        if reminder.status not in OPEN:
            raise ValidationError({"detail": "This reminder is already done."})
        return reminder

    @action(detail=True, methods=["post"])
    def sent(self, request, pk=None):
        """The front desk sent it themselves: on WhatsApp, by a call, or in person."""
        reminder = self._get_open()
        serializer = MarkSentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reminder.status = Reminder.Status.SENT
        reminder.channel = serializer.validated_data["channel"]
        reminder.sent_at = timezone.now()
        reminder.sent_by = request.user
        reminder.note = ""
        reminder.save(update_fields=["status", "channel", "sent_at", "sent_by", "note"])
        return Response(ReminderSerializer(reminder).data)

    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        reminder = self._get_open()
        serializer = SkipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reminder.status = Reminder.Status.SKIPPED
        reminder.note = serializer.validated_data["note"] or "Skipped by the front desk."
        reminder.sent_by = request.user
        reminder.save(update_fields=["status", "note", "sent_by"])
        return Response(ReminderSerializer(reminder).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        """Put a reminder marked by mistake back on the list (not one sent by SMS)."""
        reminder = self.get_object()
        if reminder.channel == Reminder.Channel.SMS or reminder.status == Reminder.Status.PENDING:
            raise ValidationError({"detail": "This reminder cannot be put back on the list."})
        reminder.status = Reminder.Status.PENDING
        reminder.channel = ""
        reminder.sent_at = None
        reminder.sent_by = None
        reminder.note = ""
        reminder.save(update_fields=["status", "channel", "sent_at", "sent_by", "note"])
        return Response(ReminderSerializer(reminder).data)


class AutomationSettingsView(APIView):
    """Everyone in the admin area may read these; only the Super Admin changes them."""

    permission_classes = [AdminArea]

    def get(self, request):
        conf = AutomationSettings.for_branch(current_branch(request))
        return Response(AutomationSettingsSerializer(conf).data)

    def patch(self, request):
        conf = AutomationSettings.for_branch(current_branch(request))
        before = snapshot(conf)
        serializer = AutomationSettingsSerializer(conf, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        old, new = changes(before, snapshot(conf))
        if new:
            audit.record(
                request,
                "automation.settings_updated",
                entity="automation",
                entity_id=conf.pk,
                before=old,
                after=new,
            )
        return Response(AutomationSettingsSerializer(conf).data)
