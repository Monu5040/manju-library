from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Business-rule errors from the service layer become 400s with field messages."""
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages}
        exc = ValidationError(detail)
    elif isinstance(exc, ProtectedError):
        return Response(
            {
                "detail": "This record is still used by other records (for example memberships "
                "or payments), so it cannot be deleted. Switch it off instead."
            },
            status=status.HTTP_409_CONFLICT,
        )
    return exception_handler(exc, context)
