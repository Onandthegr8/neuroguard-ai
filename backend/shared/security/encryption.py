"""AES-256-GCM field-level encryption for PHI columns (wearable tokens, etc.)

Key is fetched from AWS KMS via the DATA_ENCRYPTION_KEY env var (base64-encoded DEK).
In production, the DEK is fetched from KMS on startup and cached in memory only.
"""

import base64
import os
import secrets
from typing import Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_GCM_NONCE_BYTES = 12
_KEY_BYTES = 32  # 256-bit


def _get_key() -> bytes:
    raw = os.environ.get("FIELD_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError("FIELD_ENCRYPTION_KEY environment variable not set")
    key = base64.b64decode(raw)
    if len(key) != _KEY_BYTES:
        raise ValueError(f"FIELD_ENCRYPTION_KEY must be {_KEY_BYTES} bytes after base64 decode")
    return key


def encrypt_field(plaintext: Union[str, bytes]) -> bytes:
    """Encrypt a value. Returns nonce (12 bytes) || ciphertext+tag."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode()
    key = _get_key()
    nonce = secrets.token_bytes(_GCM_NONCE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_field(blob: bytes) -> bytes:
    """Decrypt a value encrypted with encrypt_field()."""
    key = _get_key()
    nonce, ciphertext = blob[:_GCM_NONCE_BYTES], blob[_GCM_NONCE_BYTES:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def decrypt_field_str(blob: bytes) -> str:
    return decrypt_field(blob).decode()
