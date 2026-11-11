from django.db import models

from . import crypto


class EncryptedTextField(models.TextField):
    """
    A text column whose value is encrypted at rest (AES-256-GCM, see core.crypto).

    The stored value changes on every save (random nonce), so the column cannot be
    searched, filtered or used for uniqueness. Keep a separate, non-sensitive column
    (for example the last 4 digits) for display and lookups.
    """

    description = "Text encrypted at rest"

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return crypto.decrypt(value)

    def to_python(self, value):
        if value is None or value == "" or not crypto.is_encrypted(value):
            return value
        return crypto.decrypt(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "" or crypto.is_encrypted(value):
            return value
        return crypto.encrypt(value)
