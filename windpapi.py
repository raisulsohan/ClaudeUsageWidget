"""
windpapi.py — thin ctypes wrapper around the Windows Data Protection API (DPAPI).

Used in two places:
  - credential_store.py encrypts the saved sessionKey so it never sits on disk
    in plain text (the ciphertext is tied to the current Windows user account).
  - browser_cookies.py unwraps the AES key that Chromium browsers keep in their
    "Local State" file.

Both functions swallow errors and return None instead of raising, so callers can
treat "couldn't protect/unprotect" the same as "not available".
"""

import ctypes
from ctypes import wintypes


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


_crypt32 = ctypes.windll.crypt32
_kernel32 = ctypes.windll.kernel32


def _blob(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _take(blob: _DATA_BLOB) -> bytes:
    out = ctypes.string_at(blob.pbData, blob.cbData)
    _kernel32.LocalFree(blob.pbData)
    return out


def encrypt(data: bytes) -> bytes | None:
    """CryptProtectData — ciphertext only this Windows user can read back."""
    out = _DATA_BLOB()
    if _crypt32.CryptProtectData(ctypes.byref(_blob(data)), None, None, None, None, 0,
                                 ctypes.byref(out)):
        return _take(out)
    return None


def decrypt(data: bytes) -> bytes | None:
    """CryptUnprotectData — returns None if the blob wasn't ours or is corrupt."""
    out = _DATA_BLOB()
    if _crypt32.CryptUnprotectData(ctypes.byref(_blob(data)), None, None, None, None, 0,
                                   ctypes.byref(out)):
        return _take(out)
    return None
