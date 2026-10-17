"""
browser_cookies.py — find claude.ai logins (the `sessionKey` cookie) in the
browsers installed on this Windows PC.

  Firefox family   cookies.sqlite, values stored in plain text
  Chromium family  Cookies DB, values encrypted with AES-256-GCM. The AES key
                   lives in the browser's "Local State" file, itself wrapped
                   with DPAPI for the current Windows user — so we can unwrap it
                   silently, no prompt (unlike macOS, which shows a dialog).

Chromium "app-bound" encryption (v20):
  Chrome/Edge 127+ re-encrypt cookies with a key that can only be unwrapped by
  the browser's own elevation service running as SYSTEM. There is no way to read
  those from an ordinary user process. Such logins are reported as `locked` and
  skipped — use a Firefox-family browser or paste your key (see README).
"""

import base64
import ctypes
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import windpapi

# Notes from the most recent find_sessions() — e.g. a browser whose cookie DB
# was locked because it was running. fetch_usage.py surfaces these to the user.
SCAN_NOTES: list[str] = []

APPDATA = Path(os.environ.get("APPDATA", ""))
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", ""))

FIREFOX_FAMILY = {
    "firefox":   APPDATA / "Mozilla/Firefox/Profiles",
    "zen":       APPDATA / "zen/Profiles",
    "librewolf": APPDATA / "librewolf/Profiles",
    "floorp":    APPDATA / "Floorp/Profiles",
}

CHROMIUM_FAMILY = {  # name: user-data dir (each holds its own "Local State")
    "chrome":   LOCALAPPDATA / "Google/Chrome/User Data",
    "brave":    LOCALAPPDATA / "BraveSoftware/Brave-Browser/User Data",
    "edge":     LOCALAPPDATA / "Microsoft Edge/User Data",
    "vivaldi":  LOCALAPPDATA / "Vivaldi/User Data",
    "chromium": LOCALAPPDATA / "Chromium/User Data",
}

BROWSERS = [*FIREFOX_FAMILY, *CHROMIUM_FAMILY]

CHROMIUM_EPOCH_OFFSET = 11644473600  # seconds between 1601-01-01 and 1970-01-01


@dataclass
class Session:
    browser: str
    profile: str
    last_used: float                                  # unix seconds
    _read: Callable[[], "str | None"] = field(repr=False)
    locked: bool = False                              # app-bound (v20), cannot be read

    def session_key(self) -> str | None:
        return self._read()


_GENERIC_READ = 0x80000000
_FILE_SHARE_ALL = 0x01 | 0x02 | 0x04       # read | write | delete
_OPEN_EXISTING = 3
_INVALID_HANDLE = ctypes.c_void_p(-1).value


def _copy_file(src: Path, dst: Path) -> None:
    """Copy src to dst even if another process has it open for sharing.

    Tries a normal copy first (works for Firefox-family DBs and for Chromium
    when the browser is closed). Falls back to a shared-mode read handle. Raises
    OSError if the owner holds an exclusive lock (modern Chrome while running).
    """
    try:
        shutil.copy2(src, dst)
        return
    except OSError:
        pass
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = wintypes.HANDLE
    h = k32.CreateFileW(str(src), _GENERIC_READ, _FILE_SHARE_ALL, None,
                        _OPEN_EXISTING, 0x80, None)
    if not h or h == _INVALID_HANDLE:
        raise OSError(f"cannot open {src.name} (locked by the browser?)")
    try:
        buf = ctypes.create_string_buffer(1 << 20)
        read = wintypes.DWORD(0)
        with open(dst, "wb") as out:
            while k32.ReadFile(h, buf, len(buf), ctypes.byref(read), None) and read.value:
                out.write(buf.raw[:read.value])
    finally:
        k32.CloseHandle(h)


def _query(db: Path, sql: str) -> list:
    """Query a copy of the DB — browsers keep theirs locked while running."""
    tmp = Path(tempfile.mkdtemp())
    try:
        copy = tmp / db.name
        _copy_file(db, copy)
        wal = db.with_name(db.name + "-wal")
        if wal.exists():
            try:
                _copy_file(wal, tmp / wal.name)
            except OSError:
                pass
        con = sqlite3.connect(copy)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Firefox family ────────────────────────────────────────────────────────────

def _firefox_sessions(name: str, root: Path) -> list[Session]:
    out = []
    for db in root.glob("*/cookies.sqlite"):
        try:
            rows = _query(db, "SELECT value, lastAccessed FROM moz_cookies "
                              "WHERE host LIKE '%claude.ai' AND name = 'sessionKey'")
        except (sqlite3.Error, OSError):
            SCAN_NOTES.append(f"{name}: couldn't read cookies (is it running?)")
            continue
        for value, last in rows:
            out.append(Session(name, db.parent.name, (last or 0) / 1e6, lambda v=value: v))
    return out


# ── Chromium family ───────────────────────────────────────────────────────────

_keys: dict[Path, "bytes | None"] = {}

def _chromium_key(root: Path) -> bytes | None:
    """Read and DPAPI-unwrap the AES key from the browser's Local State file."""
    if root not in _keys:
        key = None
        try:
            state = json.loads((root / "Local State").read_text(encoding="utf-8"))
            enc = base64.b64decode(state["os_crypt"]["encrypted_key"])
            if enc[:5] == b"DPAPI":
                key = windpapi.decrypt(enc[5:])
        except Exception:
            key = None
        _keys[root] = key
    return _keys[root]

def _chromium_decrypt(blob: bytes, host: str, root: Path) -> str | None:
    if blob[:3] not in (b"v10", b"v11"):   # v20 = app-bound, unreadable here
        return None
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        return None
    key = _chromium_key(root)
    if not key:
        return None
    try:
        plain = AESGCM(key).decrypt(blob[3:15], blob[15:], None)
    except Exception:
        return None
    # Chrome 130+ prefixes the value with sha256(host) before encrypting
    if plain[:32] == hashlib.sha256(host.encode()).digest():
        plain = plain[32:]
    return plain.decode("utf-8", "replace")

def _chromium_sessions(name: str, root: Path) -> list[Session]:
    out = []
    for db in [*root.glob("*/Network/Cookies"), *root.glob("*/Cookies")]:
        try:
            rows = _query(db, "SELECT host_key, value, encrypted_value, last_access_utc FROM cookies "
                              "WHERE host_key LIKE '%claude.ai' AND name = 'sessionKey'")
        except (sqlite3.Error, OSError):
            SCAN_NOTES.append(f"{name}: cookies are locked — close {name}, or paste your key (--setup)")
            continue
        profile = db.parents[1].name if db.parent.name == "Network" else db.parent.name
        for host, value, blob, last in rows:
            blob = blob or b""
            locked = False
            if value:
                read = lambda v=value: v
            elif blob[:3] in (b"v10", b"v11"):
                read = lambda b=blob, h=host, r=root: _chromium_decrypt(b, h, r)
            else:
                read = lambda: None          # v20 app-bound or unknown
                locked = True
            out.append(Session(name, profile, (last or 0) / 1e6 - CHROMIUM_EPOCH_OFFSET,
                               read, locked=locked))
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def find_sessions(browser: str | None = None) -> list[Session]:
    """Every claude.ai login found, most recently used first. `browser` limits the search to one."""
    if browser and browser not in BROWSERS:
        raise ValueError(f"Unknown browser '{browser}'. Choose from: {', '.join(BROWSERS)}")
    SCAN_NOTES.clear()
    found = []
    for name, root in FIREFOX_FAMILY.items():
        if browser in (None, name) and root:
            found += _firefox_sessions(name, root)
    for name, root in CHROMIUM_FAMILY.items():
        if browser in (None, name) and root:
            found += _chromium_sessions(name, root)
    return sorted(found, key=lambda s: s.last_used, reverse=True)
