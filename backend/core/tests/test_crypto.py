import pytest
from django.core.exceptions import ImproperlyConfigured

from core import crypto
from core.fields import EncryptedTextField


def test_round_trip_and_random_nonce():
    first = crypto.encrypt("1234-5678-9012")
    second = crypto.encrypt("1234-5678-9012")
    assert first.startswith("enc:v1:")
    assert first != second
    assert "1234-5678-9012" not in first
    assert crypto.decrypt(first) == "1234-5678-9012"


def test_key_rotation(settings):
    old_key, new_key = crypto.generate_key(), crypto.generate_key()
    settings.FIELD_ENCRYPTION_KEYS = [old_key]
    token = crypto.encrypt("secret")

    settings.FIELD_ENCRYPTION_KEYS = [new_key, old_key]
    assert crypto.decrypt(token) == "secret"
    assert crypto.decrypt(crypto.encrypt("again")) == "again"

    settings.FIELD_ENCRYPTION_KEYS = [new_key]
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(token)


def test_tampering_is_detected():
    token = crypto.encrypt("secret")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(tampered)


def test_bad_keys_are_refused(settings):
    settings.FIELD_ENCRYPTION_KEYS = ["dG9vLXNob3J0"]
    with pytest.raises(ImproperlyConfigured):
        crypto.encrypt("x")
    settings.FIELD_ENCRYPTION_KEYS = []
    with pytest.raises(ImproperlyConfigured):
        crypto.encrypt("x")


def test_field_encrypts_on_save_and_decrypts_on_load():
    field = EncryptedTextField()
    stored = field.get_prep_value("1234-5678-9012")
    assert crypto.is_encrypted(stored)
    assert field.from_db_value(stored, None, None) == "1234-5678-9012"
    assert field.get_prep_value(None) is None
    assert field.get_prep_value("") == ""
