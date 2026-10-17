r"""
credential_store.py — remember the working claude.ai sessionKey between runs.

The macOS original used the Keychain. On Windows we store the key one of two ways,
whichever is available, both tied to the current Windows user account:

  1. Windows Credential Manager, via the optional `keyring` package (pip install keyring).
     This is the "proper" slot you can see in Control Panel → Credential Manager.
  2. A DPAPI-encrypted file at %LOCALAPPDATA%\claude-usage-widget\session.bin.
     Used automatically when `keyring` isn't installed. The file is useless to any
     other user account, so the key is never readable in plain text.

Nothing here ever shows a password prompt.
"""

import os
from pathlib import Path

import windpapi

SERVICE = "claude.ai"
ACCOUNT = "claude-usage-widget"

_STORE_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "claude-usage-widget"
_STORE_FILE = _STORE_DIR / "session.bin"


def _keyring():
    try:
        import keyring
        return keyring
    except Exception:
        return None


def save(key: str) -> None:
    kr = _keyring()
    if kr:
        try:
            kr.set_password(SERVICE, ACCOUNT, key)
            return
        except Exception:
            pass
    blob = windpapi.encrypt(key.encode("utf-8"))
    if blob is None:
        raise RuntimeError("Could not protect the sessionKey with DPAPI")
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    _STORE_FILE.write_bytes(blob)


def load() -> str | None:
    kr = _keyring()
    if kr:
        try:
            value = kr.get_password(SERVICE, ACCOUNT)
            if value:
                return value
        except Exception:
            pass
    if _STORE_FILE.exists():
        try:
            dec = windpapi.decrypt(_STORE_FILE.read_bytes())
            if dec:
                return dec.decode("utf-8", "replace")
        except Exception:
            pass
    return None


def where() -> str:
    """Human-readable description of where the key lives, for diagnostics."""
    return "Windows Credential Manager" if _keyring() else str(_STORE_FILE)
