"""
usage_history.py — weekly % snapshots for the panel's "This week by day" chart.

The file lives next to usage_data.json (APP_DIR), not in %LOCALAPPDATA%:
a program started from inside a packaged (MSIX) app, such as the Claude desktop
app, has its %LOCALAPPDATA% writes redirected to a private copy, so the widget
started at sign-in would not see that history. APP_DIR is the same folder for
every launch.

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


def _write(hist):
    try:
        tmp = HISTORY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(hist), encoding="utf-8")
        os.replace(tmp, HISTORY_FILE)
    except Exception:
        pass


def load():
    hist = _read(HISTORY_FILE)
    if OLD_FILE.exists():
        old = _read(OLD_FILE)
        merged = _clean(hist + old)
        if merged != hist:
            hist = merged
            _write(hist)
    return hist


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
