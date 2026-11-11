import json

from django.core.serializers.json import DjangoJSONEncoder

from . import services as audit

SENSITIVE_FIELDS = {"aadhaar", "password", "code_hash"}


def snapshot(instance) -> dict:
    """A JSON-safe copy of a model's own columns, without sensitive values."""
    values = {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
        if field.attname not in SENSITIVE_FIELDS
    }
    return json.loads(json.dumps(values, cls=DjangoJSONEncoder))


def changes(before: dict, after: dict) -> tuple[dict, dict]:
    keys = [k for k in after if before.get(k) != after.get(k) and k != "updated_at"]
    return {k: before.get(k) for k in keys}, {k: after.get(k) for k in keys}


class AuditedViewSetMixin:
    """Writes an audit entry for every create, update and delete made through the view."""

    audit_entity = ""

    def record_audit(self, action, instance, before=None, after=None, **extra):
        audit.record(
            self.request,
            f"{self.audit_entity}.{action}",
            entity=self.audit_entity,
            entity_id=instance.pk,
            before=before,
            after=after,
            **extra,
        )

    def get_save_kwargs(self) -> dict:
        return {}

    def perform_create(self, serializer):
        instance = serializer.save(**self.get_save_kwargs())
        self.record_audit("created", instance, after=snapshot(instance))

    def perform_update(self, serializer):
        before = snapshot(serializer.instance)
        instance = serializer.save()
        old, new = changes(before, snapshot(instance))
        if new:
            self.record_audit("updated", instance, before=old, after=new)

    def perform_destroy(self, instance):
        before = snapshot(instance)
        pk = instance.pk
        instance.delete()
        instance.pk = pk
        self.record_audit("deleted", instance, before=before)
