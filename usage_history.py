"""
usage_history.py — weekly % snapshots for the panel's "This week by day" chart.

The file lives next to usage_data.json (APP_DIR), not in %LOCALAPPDATA%:
a program started from inside a packaged (MSIX) app, such as the Claude desktop
app, has its %LOCALAPPDATA% writes redirected to a private copy, so the widget
started at sign-in would not see that history. APP_DIR is the same folder for
every launch.

A second copy is kept on another drive (BACKUP_FILE), by default the first fixed
drive that is not the Windows drive, e.g. D:\\Claude Usage Widget\\history.json.
Uninstalling the widget or setting Windows up again clears the copy in APP_DIR;
the backup stays, and the next install merges it back in on start. Set
CLAUDE_USAGE_HISTORY_DIR to keep the backup somewhere else (a OneDrive folder,
say), or to "off" to turn it off.

Both receiver.py (on each push from the extension) and widget.py record here, so
the history keeps growing while the widget is closed.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
HISTORY_FILE = APP_DIR / "history.json"
# where older versions kept it; merged in once, when found
OLD_FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "claude-usage-widget" / "history.json"
KEEP_DAYS = 35
BACKUP_NAME = "Claude Usage Widget"


def _backup_dir():
    """The folder for the second copy: CLAUDE_USAGE_HISTORY_DIR, or the first fixed
    drive that is not the Windows drive. None when there is no such place."""
    env = (os.environ.get("CLAUDE_USAGE_HISTORY_DIR") or "").strip()
    if env:
        return None if env.lower() == "off" else Path(env)
    if os.name != "nt":
        return None
    try:
        import ctypes
        system = (os.environ.get("SystemDrive") or "C:").upper().rstrip("\\")
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if not mask & (1 << i):
                continue
            root = f"{chr(65 + i)}:"
            if root == system:
                continue
            if ctypes.windll.kernel32.GetDriveTypeW(root + "\\") == 3:   # DRIVE_FIXED
                return Path(root + "\\") / BACKUP_NAME
    except Exception:
        pass
    return None


_BACKUP_DIR = _backup_dir()
BACKUP_FILE = _BACKUP_DIR / "history.json" if _BACKUP_DIR else None


def _parse(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def _read(path):
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _clean(entries):
    """Sort by time, drop bad and old entries, keep one entry per time stamp and
    only the entries where the % changed."""
    cutoff = datetime.now().astimezone() - timedelta(days=KEEP_DAYS)
    rows = {}
    for e in entries:
        t = _parse(str(e.get("t") or ""))
        if t and t >= cutoff:
            rows[t] = {"t": e["t"], "pct": int(e.get("pct") or 0)}
    out = []
    for t in sorted(rows):
        if not out or out[-1]["pct"] != rows[t]["pct"]:
            out.append(rows[t])
    return out


def _write_to(path, hist):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(hist), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def _write(hist):
    _write_to(HISTORY_FILE, hist)
    if BACKUP_FILE and BACKUP_FILE != HISTORY_FILE:
        _write_to(BACKUP_FILE, hist)


def load():
    """The history from APP_DIR, merged with the backup copy and the old file.
    Both copies are brought up to date when they differ from the merge."""
    hist = _read(HISTORY_FILE)
    backup = _read(BACKUP_FILE) if BACKUP_FILE and BACKUP_FILE != HISTORY_FILE else None
    old = _read(OLD_FILE) if OLD_FILE.exists() else []
    if backup is None and not old:
        return hist
    merged = _clean(hist + (backup or []) + old)
    if merged != hist:
        _write_to(HISTORY_FILE, merged)
    if backup is not None and merged != backup:
        _write_to(BACKUP_FILE, merged)
    return merged


def record(data):
    """Add this data's weekly % to the history. Only changes are kept: the % at
    any moment is the last snapshot before it, so repeats add nothing."""
    hist = load()
    t = data.get("updated")
    pct = int((data.get("weekly") or {}).get("percent") or 0)
    if not t or (hist and (hist[-1].get("t") == t or hist[-1].get("pct") == pct)):
        return hist
    hist = _clean(hist + [{"t": t, "pct": pct}])
    _write(hist)
    return hist
