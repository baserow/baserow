"""
Encryption of the secrets Baserow stores to send to other services.

A secret is stored as ``enc:v1:<key id>:<base64url(nonce + ciphertext + tag)>``,
encrypted with AES-256-GCM. The key id says which key encrypted it, so old keys
can stay around to decrypt while new values use the current key. The associated
data binds a value to its column, so it can't be copied into another one. It
doesn't bind it to its row: whoever can copy a value between rows can also
change where that row sends it.
"""

import base64
import hashlib
import os
import re
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from django.core import checks
from django.core.exceptions import ImproperlyConfigured

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from loguru import logger

PREFIX = "enc:"
VERSION = "v1"
NONCE_SIZE = 12
MIN_KEY_LENGTH = 32

# Separate labels, so the key derived from SECRET_KEY never equals one derived
# from the same string set as BASEROW_ENCRYPTION_KEY.
_KEY_INFO = b"baserow-encryption-key-v1"
_SECRET_KEY_INFO = b"baserow-secrets-at-rest-from-secret-key-v1"


class DecryptionError(Exception):
    """A stored secret can't be decrypted with any configured key."""


def _derive(material: str, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(
        material.encode()
    )


def _key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:8]


@dataclass(frozen=True)
class KeyRing:
    primary_id: str
    """The id of the key new values are encrypted with."""
    keys: dict[str, bytes]
    """Every key that may decrypt a stored value, by id."""
    derived_from_secret_key: bool
    """Whether the primary key comes from SECRET_KEY."""


def _configured_key(value: str, name: str) -> bytes:
    if len(value) < MIN_KEY_LENGTH:
        raise ImproperlyConfigured(
            f"{name} must be at least {MIN_KEY_LENGTH} characters long."
        )
    return _derive(value, _KEY_INFO)


@lru_cache(maxsize=4)
def _build_key_ring(
    primary: str,
    fallbacks: tuple[str, ...],
    secret_key: str,
    secret_key_fallbacks: tuple[str, ...],
) -> KeyRing:
    keys = {}
    if primary:
        primary_key = _configured_key(primary, "BASEROW_ENCRYPTION_KEY")
    else:
        primary_key = _derive(secret_key, _SECRET_KEY_INFO)
    primary_id = _key_id(primary_key)

    def add(key: bytes):
        key_id = _key_id(key)
        known = keys.setdefault(key_id, key)
        if known != key:
            # A stored value names its key by id only, so one of these keys
            # could never decrypt what it encrypted.
            raise ImproperlyConfigured(
                f"Two of the configured encryption keys share the id {key_id}. "
                "Generate another BASEROW_ENCRYPTION_KEY."
            )

    add(primary_key)
    for fallback in fallbacks:
        # A fallback is an old BASEROW_ENCRYPTION_KEY or an old SECRET_KEY. A
        # value shorter than the minimum can only be an old SECRET_KEY.
        if len(fallback) >= MIN_KEY_LENGTH:
            add(_derive(fallback, _KEY_INFO))
        add(_derive(fallback, _SECRET_KEY_INFO))
    # Values written while the key was derived from SECRET_KEY, or from a
    # SECRET_KEY that has since changed, stay readable.
    for old in (secret_key, *secret_key_fallbacks):
        if old:
            add(_derive(old, _SECRET_KEY_INFO))
    return KeyRing(primary_id, keys, derived_from_secret_key=not primary)


_warned_about_secret_key = False


def get_key_ring() -> KeyRing:
    """
    The configured keys, read from the settings so tests can override them.

    :return: The current key ring.
    :raises ImproperlyConfigured: When a configured key is too short.
    """

    global _warned_about_secret_key

    ring = _build_key_ring(
        settings.BASEROW_ENCRYPTION_KEY,
        tuple(settings.BASEROW_ENCRYPTION_KEY_FALLBACKS),
        settings.SECRET_KEY,
        tuple(getattr(settings, "SECRET_KEY_FALLBACKS", ())),
    )
    if ring.derived_from_secret_key and not _warned_about_secret_key:
        _warned_about_secret_key = True
        logger.warning(
            "BASEROW_ENCRYPTION_KEY isn't set, so stored secrets are encrypted "
            "with a key derived from SECRET_KEY. Set BASEROW_ENCRYPTION_KEY to "
            "keep them independent."
        )
    return ring


def _associated_data(key_id: str, context: str) -> bytes:
    return f"baserow:{VERSION}:{key_id}:{context}".encode()


_ENCRYPTED = re.compile(
    rf"^{re.escape(PREFIX)}(?P<version>v[0-9]+):(?P<key_id>[0-9a-f]{{8}}):"
    r"(?P<token>[A-Za-z0-9_-]+)$"
)


def encrypted_prefix(key_id: str) -> str:
    """:return: How every value encrypted with this key starts."""

    return f"{PREFIX}{VERSION}:{key_id}:"


def is_encrypted(value: str) -> bool:
    """
    Only values in the exact format count, so plain text written before the
    field was encrypted is read as is, even when it starts with the prefix.
    """

    return _ENCRYPTED.match(value) is not None


def get_key_id(value: str) -> str | None:
    """
    :param value: A stored value.
    :return: The id of the key that encrypted it, or None when it's plain text.
    """

    match = _ENCRYPTED.match(value)
    return match["key_id"] if match else None


def encrypt(plaintext: str, context: str) -> str:
    """
    Encrypt a secret with the primary key and a fresh random nonce.

    :param plaintext: The secret.
    :param context: Where it's stored, e.g. ``app_label.model.field``. The same
        context is needed to decrypt it.
    :return: The value to store.
    """

    ring = get_key_ring()
    key_id = ring.primary_id
    nonce = os.urandom(NONCE_SIZE)
    sealed = AESGCM(ring.keys[key_id]).encrypt(
        nonce, plaintext.encode(), _associated_data(key_id, context)
    )
    token = base64.urlsafe_b64encode(nonce + sealed).decode().rstrip("=")
    return f"{encrypted_prefix(key_id)}{token}"


def decrypt(value: str, context: str) -> str:
    """
    Decrypt a stored secret.

    :param value: A value made by ``encrypt``.
    :param context: The context it was encrypted with.
    :return: The secret.
    :raises DecryptionError: When the value is malformed, its key isn't
        configured, or it wasn't encrypted for this context.
    """

    match = _ENCRYPTED.match(value)
    if match is None or match["version"] != VERSION:
        raise DecryptionError(f"Unknown format of an encrypted value in {context}.")
    key_id, token = match["key_id"], match["token"]
    key = get_key_ring().keys.get(key_id)
    if key is None:
        raise DecryptionError(
            f"A value in {context} was encrypted with key {key_id}, which isn't "
            "configured. Add it to BASEROW_ENCRYPTION_KEY_FALLBACKS."
        )
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        plaintext = AESGCM(key).decrypt(
            raw[:NONCE_SIZE], raw[NONCE_SIZE:], _associated_data(key_id, context)
        )
    except (InvalidTag, ValueError) as exc:
        raise DecryptionError(f"A value in {context} can't be decrypted.") from exc
    return plaintext.decode()


@checks.register(checks.Tags.security)
def check_encryption_keys(app_configs, **kwargs):
    """Report a key that's too short when Django starts, not at first use."""

    try:
        get_key_ring()
    except ImproperlyConfigured as exc:
        return [checks.Error(str(exc), id="baserow.E002")]
    return []
