"""
Application-level encryption for sensitive values such as Aadhaar numbers.

AES-256-GCM with a random 96-bit nonce per value. Stored format:
    enc:v1:<base64url(nonce || ciphertext+tag)>

settings.FIELD_ENCRYPTION_KEYS is a list of base64url-encoded 32-byte keys. The first key
encrypts; all keys are tried on decrypt, which allows key rotation.
"""

import base64
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PREFIX = "enc:v1:"
_NONCE_BYTES = 12


class DecryptionError(ValueError):
    pass


def generate_key() -> str:
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()


def decode_key(key: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(key.encode())
    except (ValueError, TypeError) as exc:
        msg = "FIELD_ENCRYPTION_KEYS contains a key that is not base64."
        raise ImproperlyConfigured(msg) from exc
    if len(raw) != 32:
        raise ImproperlyConfigured("Each FIELD_ENCRYPTION_KEYS entry must decode to 32 bytes.")
    return raw


@lru_cache(maxsize=8)
def _ciphers_for(keys: tuple[str, ...]) -> tuple[AESGCM, ...]:
    if not keys:
        msg = "FIELD_ENCRYPTION_KEYS is empty; sensitive fields cannot be used."
        raise ImproperlyConfigured(msg)
    return tuple(AESGCM(decode_key(k)) for k in keys)


def _ciphers() -> tuple[AESGCM, ...]:
    return _ciphers_for(tuple(settings.FIELD_ENCRYPTION_KEYS))


def is_encrypted(value: str) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = _ciphers()[0].encrypt(nonce, plaintext.encode("utf-8"), None)
    return PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt(token: str) -> str:
    if not is_encrypted(token):
        raise DecryptionError("Value is not in the encrypted format.")
    try:
        blob = base64.urlsafe_b64decode(token[len(PREFIX) :].encode())
    except (ValueError, TypeError) as exc:
        raise DecryptionError("Encrypted value is not valid base64.") from exc
    nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    for cipher in _ciphers():
        try:
            return cipher.decrypt(nonce, ciphertext, None).decode("utf-8")
        except InvalidTag:
            continue
    raise DecryptionError("No configured key can decrypt this value.")


BYTES_PREFIX = b"enc:v1:"


def encrypt_bytes(data: bytes) -> bytes:
    """The same scheme for files (for example an uploaded spreadsheet), without base64."""
    nonce = os.urandom(_NONCE_BYTES)
    return BYTES_PREFIX + nonce + _ciphers()[0].encrypt(nonce, data, None)


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypts what encrypt_bytes made; data stored before encryption is returned as it is."""
    if not data.startswith(BYTES_PREFIX):
        return data
    blob = data[len(BYTES_PREFIX) :]
    nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    for cipher in _ciphers():
        try:
            return cipher.decrypt(nonce, ciphertext, None)
        except InvalidTag:
            continue
    raise DecryptionError("No configured key can decrypt this file.")


def mask_digits(value: str) -> str:
    """XXXX-XXXX-1234 for anything that looks like an ID number; nothing readable otherwise."""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return f"XXXX-XXXX-{digits[-4:]}" if len(digits) >= 4 else "(hidden)"
