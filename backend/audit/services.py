from typing import Any

from core.http import client_ip

from .models import AuditLog


def record(
    request,
    action: str,
    *,
    actor=None,
    entity: str = "",
    entity_id: str | int = "",
    before: Any = None,
    after: Any = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Add one audit entry. `actor` defaults to the signed-in user, if any."""
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            actor = user
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id != "" else "",
        before=before,
        after=after,
        metadata=metadata or {},
        ip=client_ip(request) if request is not None else None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:256] if request is not None else ""),
    )
