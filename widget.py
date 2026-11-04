#!/usr/bin/env python3
"""
Claude Usage Widget — a small strip on the Windows taskbar, with a usage panel.

- The strip shows the weekly limit ("51% until Tue") and a bar. The mark on the
  bar shows how much of the week has gone.
- Click the strip (or right-click it) to open the panel. Click outside the
  panel, or press Esc, to close it.
- Drag the strip to move it. It reopens where you left it.

Reads usage_data.json written by fetch_usage.py or receiver.py, and picks up new
data on its own (watches the file's modification time).
"""

import ctypes
import functools
import json
import math
import os
import re
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
import webbrowser
import winreg
from ctypes import wintypes
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageGrab, ImageTk

import usage_history   # weekly % snapshots for the "by day" chart (next to usage_data.json)

# next to the .exe when built with PyInstaller, else next to this script
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_FILE = APP_DIR / "usage_data.json"
# remembers where you last dragged the strip
POS_FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "claude-usage-widget" / "widget_pos.json"
POS_KEY = "compact"
# your choices in the panel, e.g. {"theme": "dark"}
SETTINGS_FILE = POS_FILE.parent / "settings.json"
THEMES = ("system", "light", "dark")     # the panel's theme button goes round in this order

USAGE_PAGE = "https://claude.ai/settings/limits"
RECEIVER_REFRESH = "http://127.0.0.1:8765/refresh"

STRIP_W = 156        # strip width (px at 100% scaling)
PANEL_W = 380        # panel width
PANEL_GAP = 12       # space between the panel and the taskbar
TRAY_MARGIN = 300    # px kept clear on the right for the clock / system tray
EDGE_MARGIN = 8      # px kept clear on the left
STALE_MIN = 30       # "Updated …" turns amber when the data is older than this
TICK_MS = 1000

WEEK = timedelta(days=7)
DAY = timedelta(days=1)
EVEN_DAY = 100 / 7   # % of the weekly limit per day at an even pace
SS = 4               # supersampling for the anti-aliased shapes
OPEN_MS = 420        # panel open: slide up, fade in, bars fill and numbers count up
CLOSE_MS = 110       # panel close: fade out (exits are faster than entrances)
STRIP_MS = 600       # strip: bar and number move to new data

# ── colors ──────────────────────────────────────────────────────────────────
LIGHT = {
    "bg": "#F9F9F9", "border": "#E3E3E3", "text": "#1B1B1B", "sub": "#5C5C5C",
    "dim": "#8B8B8B", "sep": "#EAEAEA", "btn": "#F3F3F3", "hover": "#EBEBEB", "press": "#E3E3E3",
    "track": "#E4E1DD", "fill": "#C2603F", "fill2": "#DA8565", "crit": "#C42B1C",
    "marker": "#3B3B3B", "stale": "#9D5D00",
    "ok": ("#E2F3DF", "#1D7A34"), "warn": ("#FFF0D4", "#8F5400"),
    "bad": ("#FDE4E1", "#B42318"), "new": ("#EDEDED", "#5C5C5C"),
}
DARK = {
    "bg": "#2C2C2C", "border": "#3F3F3F", "text": "#F2F2F2", "sub": "#C8C8C8",
    "dim": "#9B9B9B", "sep": "#3A3A3A", "btn": "#323232", "hover": "#3A3A3A", "press": "#353535",
    "track": "#4A4744", "fill": "#D2704F", "fill2": "#E8977A", "crit": "#FF6B5E",
    "marker": "#EDEDED", "stale": "#F2B84B",
    "ok": ("#1E3A25", "#73D08A"), "warn": ("#3F3117", "#F2B84B"),
    "bad": ("#47211E", "#FF8F85"), "new": ("#3A3A3A", "#C8C8C8"),
}
LOGO = "#D97757"     # Claude orange

# the Claude mark, from extension/claude_official.svg (viewBox 0 0 100 100)
LOGO_PATH = (
    "m19.6 66.5 19.7-11 .3-1-.3-.5h-1l-3.3-.2-11.2-.3L14 53l-9.5-.5-2.4-.5L0 49l.2-1.5 2-1.3 "
    "2.9.2 6.3.5 9.5.6 6.9.4L38 49.1h1.6l.2-.7-.5-.4-.4-.4L29 41l-10.6-7-5.6-4.1-3-2-1.5-2-.6-4.2 "
    "2.7-3 3.7.3.9.2 3.7 2.9 8 6.1L37 36l1.5 1.2.6-.4.1-.3-.7-1.1L33 25l-6-10.4-2.7-4.3-.7-2.6c-.3-1"
    "-.4-2-.4-3l3-4.2L28 0l4.2.6L33.8 2l2.6 6 4.1 9.3L47 29.9l2 3.8 1 3.4.3 1h.7v-.5l.5-7.2 1-8.7 "
    "1-11.2.3-3.2 1.6-3.8 3-2L61 2.6l2 2.9-.3 1.8-1.1 7.7L59 27.1l-1.5 8.2h.9l1-1.1 4.1-5.4 6.9-8.6 "
    "3-3.5L77 13l2.3-1.8h4.3l3.1 4.7-1.4 4.9-4.4 5.6-3.7 4.7-5.3 7.1-3.2 5.7.3.4h.7l12-2.6 6.4-1.1 "
    "7.6-1.3 3.5 1.6.4 1.6-1.4 3.4-8.2 2-9.6 2-14.3 3.3-.2.1.2.3 6.4.6 2.8.2h6.8l12.6 1 3.3 2 1.9 "
    "2.7-.3 2-5.1 2.6-6.8-1.6-16-3.8-5.4-1.3h-.8v.4l4.6 4.5 8.3 7.5L89 80.1l.5 2.4-1.3 2-1.4-.2-9.2-7"
    "-3.6-3-8-6.8h-.5v.7l1.8 2.7 9.8 14.7.5 4.5-.7 1.4-2.6 1-2.7-.6-5.8-8-6-9-4.7-8.2-.5.4-2.9 "
    "30.2-1.3 1.5-3 1.2-2.5-2-1.4-3 1.4-6.2 1.6-8 1.3-6.4 1.2-7.9.7-2.6v-.2H49L43 72l-9 12.3-7.2 "
    "7.6-1.7.7-3-1.5.3-2.8L24 86l10-12.8 6-7.9 4-4.6-.1-.5h-.3L17.2 77.4l-4.7.6-2-2 .2-3 1-1 8-5.5Z"
)


# ── data ────────────────────────────────────────────────────────────────────
def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, encoding="utf-8-sig") as f:   # tolerate a BOM
                return json.load(f)
        except Exception:
            pass
    return {
        "weekly":  {"percent": 0, "resets_in": "—"},
        "fable":   {"percent": 0, "resets_in": "—", "available": False},
        "extra":   {"spent": 0.0, "percent": 0, "limit": 0.0, "resets": "—", "enabled": False},
        "plan":    "—",
        "updated": None,
    }


def parse_time(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def reset_time(win, updated):
    """When a limit window resets: `resets_at` if present, else `resets_in`
    ("6d 7h 37m") counted from the `updated` time (older data files)."""
    t = parse_time(win.get("resets_at") or "")
    if not t:
        base = parse_time(updated or "")
        parts = dict((u, int(n)) for n, u in re.findall(r"(\d+)\s*([dhm])", win.get("resets_in") or ""))
        if not base or not parts:
            return None
        t = base + timedelta(days=parts.get("d", 0), hours=parts.get("h", 0), minutes=parts.get("m", 0))
    # The API gives the same reset as 17:59:59.9 one time and 18:00:00.07 the
    # next. Round to the minute, so the day shown does not flip between updates.
    return (t + timedelta(seconds=30)).replace(second=0, microsecond=0)


def reset_label(t, fmt):
    """The last minute of the window, e.g. 'Mon 23:59' for a reset at Tue 00:00:
    you can use the limit until then."""
    return (t - timedelta(minutes=1)).strftime(fmt)


def format_left(t):
    """'1 day 16 hr', '5 hr 12 min', '8 min'."""
    secs = max(0, (t - datetime.now().astimezone()).total_seconds())
    d, rem = divmod(int(secs), 86400)
    h, m = rem // 3600, (rem % 3600) // 60
    if d:
        return f"{d} day{'s' if d > 1 else ''} {h} hr" if h else f"{d} day{'s' if d > 1 else ''}"
    if h:
        return f"{h} hr {m} min" if m else f"{h} hr"
    return f"{m} min"


def format_ago(iso):
    t = parse_time(iso or "")
    if not t:
        return "never", 1e9
    mins = (datetime.now().astimezone() - t).total_seconds() / 60
    if mins < 1:
        return "just now", mins
    if mins < 60:
        return f"{int(mins)} min ago", mins
    if mins < 48 * 60:
        return f"{int(mins / 60)} hr ago", mins
    return f"{int(mins / 1440)} days ago", mins


def week_pace(pct, resets):
    """(elapsed 0–1, pill label, pill style, detail text) for the weekly window."""
    if not resets:
        return None, None, None, ""
    elapsed = (datetime.now().astimezone() - (resets - WEEK)) / WEEK
    elapsed = min(max(elapsed, 0.0), 1.0)
    head = f"{round(elapsed * 100)}% of week elapsed"
    if pct >= 100:
        return elapsed, "Limit reached", "bad", head
    if elapsed < 0.03:
        return elapsed, "New week", "new", head
    proj = round(pct / elapsed)
    if proj <= 90:
        label, style = "On track", "ok"
    elif proj <= 100:
        label, style = "Tight", "warn"
    else:
        label, style = "Over pace", "bad"
    return elapsed, label, style, f"{head} · projected ~{min(proj, 999)}%"


def load_history():
    return usage_history.load()


def record_history(data):
    return usage_history.record(data)


def week_days(pct, resets, hist):
    """The 7 days of the current weekly window, each with how much of the limit
    it used. A day's use = the weekly % at its end minus the % at its start, from
    the history snapshots. Days the widget did not see have value None."""
    now = datetime.now().astimezone()
    start = resets - WEEK
    pts = sorted((t, e.get("pct", 0)) for e in hist
                 if (t := parse_time(e.get("t") or "")) and start <= t <= now + timedelta(minutes=5))

    def pct_at(moment):
        known = [p for t, p in pts if t <= moment]
        return known[-1] if known else None

    days = []
    for i in range(7):
        a = start + i * DAY
        b = a + DAY
        base = 0 if i == 0 else pct_at(a)            # the limit is 0% when the week starts
        if a > now:
            state, value = "future", None
        elif b > now:
            state = "today"
            value = None if base is None else max(0, pct - base)
        else:
            end = pct_at(b)
            state = "past"
            value = None if base is None or end is None else max(0, end - base)
        if value is None and state != "future":
            state = "nodata" if state == "past" else state
        days.append({"start": a, "label": (a + DAY / 2).strftime("%a"), "state": state,
                     "value": value, "base": base})
    return days


def motion_enabled():
    """Windows' "Animation effects" setting (Settings › Accessibility › Visual effects)."""
    try:
        on = wintypes.BOOL()
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(on), 0)   # SPI_GETCLIENTAREAANIMATION
        return bool(on.value)
    except Exception:
        return True


def ease_out(t):
    return 1 - (1 - t) ** 3


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(**changes):
    s = {**load_settings(), **changes}
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(s), encoding="utf-8")
    except Exception:
        pass


# ── Windows helpers ─────────────────────────────────────────────────────────
def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)     # system DPI aware: crisp text
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def light_theme(key):
    """AppsUseLightTheme (panel) or SystemUsesLightTheme (taskbar)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return bool(winreg.QueryValueEx(k, key)[0])
    except OSError:
        return True


def workarea():
    """Primary-monitor rect excluding the taskbar, or None."""
    try:
        r = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
        return r.left, r.top, r.right, r.bottom
    except Exception:
        return None


def hwnd_of(win):
    try:
        return ctypes.windll.user32.GetAncestor(win.winfo_id(), 2)     # GA_ROOT
    except Exception:
        return 0


def round_corners(win, border=None):
    """Windows 11 rounded corners (and border color) for a borderless window."""
    try:
        hwnd = wintypes.HWND(hwnd_of(win))
        pref = ctypes.c_int(2)                                         # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)
        if border:
            r, g, b = (int(border[i:i + 2], 16) for i in (1, 3, 5))
            ref = ctypes.c_uint(r | g << 8 | b << 16)                  # COLORREF
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(ref), 4)
    except Exception:
        pass


def hex_rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def rgb_hex(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb[:3])


def mix(a, b, t):
    """Blend hex color a toward b by t."""
    ra, rb = hex_rgb(a), hex_rgb(b)
    return rgb_hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def luminance(c):
    r, g, b = hex_rgb(c)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


# ── anti-aliased shapes (drawn large with Pillow, then scaled down) ────────
def _svg_points(d):
    """Flatten an SVG path (M L H V C Z, absolute and relative) to one polygon."""
    toks = re.findall(r"[MmLlHhVvCcZz]|-?(?:\d+\.?\d*|\.\d+)", d)
    pts, x, y, i, cmd = [], 0.0, 0.0, 0, None
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c in "ML":
            nx, ny = float(toks[i]), float(toks[i + 1]); i += 2
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            pts.append((x, y))
            if c == "M":
                cmd = "l" if rel else "L"                               # later pairs are lines
        elif c == "H":
            v = float(toks[i]); i += 1
            x = x + v if rel else v
            pts.append((x, y))
        elif c == "V":
            v = float(toks[i]); i += 1
            y = y + v if rel else v
            pts.append((x, y))
        elif c == "C":
            v = [float(t) for t in toks[i:i + 6]]; i += 6
            if rel:
                v = [v[k] + (x if k % 2 == 0 else y) for k in range(6)]
            x0, y0 = x, y
            for s in range(1, 9):
                t = s / 8; u = 1 - t
                pts.append((u**3 * x0 + 3 * u * u * t * v[0] + 3 * u * t * t * v[2] + t**3 * v[4],
                            u**3 * y0 + 3 * u * u * t * v[1] + 3 * u * t * t * v[3] + t**3 * v[5]))
            x, y = v[4], v[5]
        else:
            i += 1
    return pts


_LOGO_PTS = _svg_points(LOGO_PATH)


@functools.lru_cache(maxsize=16)
def logo_image(size):
    big = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    k = size * SS / 100
    ImageDraw.Draw(big).polygon([(px * k, py * k) for px, py in _LOGO_PTS], fill=LOGO)
    return big.resize((size, size), Image.LANCZOS)


@functools.lru_cache(maxsize=16)
def theme_icon(mode, size, color):
    """Sun (light), moon (dark) or a half-filled circle (follow Windows)."""
    S = size * SS
    big = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(big)
    c = S / 2
    if mode == "light":
        r = S * 0.19
        dr.ellipse((c - r, c - r, c + r, c + r), fill=color)
        for k in range(8):
            a = k * math.pi / 4
            dx, dy = math.cos(a), math.sin(a)
            dr.line((c + dx * S * 0.31, c + dy * S * 0.31, c + dx * S * 0.44, c + dy * S * 0.44),
                    fill=color, width=round(S * 0.075))
    elif mode == "dark":
        r = S * 0.36
        dr.ellipse((c - r, c - r, c + r, c + r), fill=color)
        cx, cy, r2 = c + S * 0.2, c - S * 0.16, S * 0.3
        dr.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=(0, 0, 0, 0))   # cut the crescent
    else:
        r = S * 0.36
        dr.ellipse((c - r, c - r, c + r, c + r), outline=color, width=round(S * 0.075))
        dr.pieslice((c - r, c - r, c + r, c + r), 90, 270, fill=color)
    return big.resize((size, size), Image.LANCZOS)


@functools.lru_cache(maxsize=256)
def rrect_image(w, h, r, fill):
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), r * SS, fill=fill)
    return big.resize((w, h), Image.LANCZOS)


@functools.lru_cache(maxsize=512)
def bar_image(w, h, pct, track, fill, fill2, marker=None, marker_at=None, marker_w=2, marker_h=0):
    """A rounded bar with a left-to-right gradient fill and an optional mark."""
    H = max(h, marker_h)
    big = Image.new("RGBA", (w * SS, H * SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(big)
    top = (H - h) * SS // 2
    rad = h * SS // 2
    dr.rounded_rectangle((0, top, w * SS - 1, top + h * SS - 1), rad, fill=track)
    if pct > 0:
        fw = max(h * SS, int(w * SS * min(pct, 100) / 100))
        grad = Image.new("RGB", (2, 1))
        grad.putpixel((0, 0), hex_rgb(fill))
        grad.putpixel((1, 0), hex_rgb(fill2))
        # the gradient spans the full bar, so a short fill stays the darker color
        grad = grad.resize((w * SS, 1), Image.BILINEAR).crop((0, 0, fw, 1)).resize((fw, h * SS))
        mask = Image.new("L", (fw, h * SS), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, fw - 1, h * SS - 1), rad, fill=255)
        big.paste(grad, (0, top), mask)
    if marker and marker_at is not None:
        mx = int(min(max(marker_at, 0), 1) * (w - marker_w) * SS)
        dr.rounded_rectangle((mx, 0, mx + marker_w * SS - 1, H * SS - 1), marker_w * SS // 2, fill=marker)
    return big.resize((w, H), Image.LANCZOS)


# ── tooltip (a small card that follows the mouse) ───────────────────────────
class Tooltip:
    def __init__(self, app):
        self.app = app
        self.win = None
        self._job = None

    @property
    def hwnd(self):
        return hwnd_of(self.win) if self.win is not None else 0

    def schedule(self, lines, above_y=None, delay=350):
        """Show `lines` after a short hover. The first line is the title."""
        self.hide()
        self._job = self.app.root.after(delay, lambda: self._show(lines, above_y))

    def hide(self):
        if self._job:
            self.app.root.after_cancel(self._job)
            self._job = None
        if self.win is not None:
            self.win.destroy()
            self.win = None

    def _show(self, lines, above_y):
        self._job = None
        app, px, F = self.app, self.app.px, self.app.fonts
        c = app.colors()
        self.win = w = tk.Toplevel(app.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        cv = tk.Canvas(w, bg=c["bg"], highlightthickness=0, bd=0)
        cv.pack()
        fonts = [F["small_b"]] + [F["small"]] * (len(lines) - 1)
        lh = px(19)
        W = max(f.measure(s) for f, s in zip(fonts, lines)) + px(24)
        H = lh * len(lines) + px(12)
        for i, (f, s) in enumerate(zip(fonts, lines)):
            cv.create_text(px(12), px(6) + lh * i + lh // 2, text=s, font=f, anchor="w",
                           fill=c["text"] if i == 0 else c["sub"])
        cv.configure(width=W, height=H)
        mx, my = app.root.winfo_pointerxy()
        sw = app.root.winfo_screenwidth()
        x = min(max(mx - W // 2, px(4)), sw - W - px(4))
        y = max(px(4), (above_y if above_y is not None else my - px(16)) - H)
        w.geometry(f"{W}x{H}+{x}+{y}")
        w.update_idletasks()
        round_corners(w, c["border"])


# ── the panel (pops up above the strip) ─────────────────────────────────────
class Panel:
    def __init__(self, app):
        self.app = app
        self.win = None
        self.closed_at = 0.0
        self._slide = 0          # px the panel is still below its place (open animation)
        self._anim = 0           # id of the running animation, so a newer one stops it

    @property
    def is_open(self):
        return self.win is not None

    def toggle(self):
        if self.is_open:
            self.close()
        elif (datetime.now().timestamp() - self.closed_at) > 0.35:     # the same click just closed it
            self.open()

    def open(self):
        app = self.app
        app.tip.hide()               # a strip tooltip still waiting to show would cover the panel
        self.win = w = tk.Toplevel(app.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        self.c = app.colors()
        w.configure(bg=self.c["bg"])
        self.cv = tk.Canvas(w, bg=self.c["bg"], highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        motion = app.motion
        if motion:
            w.attributes("-alpha", 0.0)
            self._slide = app.px(14)
        self.render(0.0 if motion else 1.0)
        w.bind("<Escape>", lambda e: self.close())
        w.update_idletasks()
        round_corners(w, self.c["border"])
        w.deiconify()
        w.lift()
        self._fg0 = ctypes.windll.user32.GetForegroundWindow()
        self._had_focus = False
        w.focus_force()
        app.redraw()
        self._watch_focus()

        def step(t):
            if self.win is not w:
                return
            e = ease_out(t)
            self._slide = round((1 - ease_out(min(1.0, t * 1.4))) * app.px(14))
            w.attributes("-alpha", min(1.0, t * 2.5))
            self.render(e)
        self._anim = app.animate(OPEN_MS, step)

    @property
    def animating(self):
        return self.app.is_animating(self._anim)

    def close(self):
        if self.win is None:
            return
        w, self.win = self.win, None
        self.closed_at = datetime.now().timestamp()
        self.app.tip.hide()
        self.app.redraw()

        def step(t):
            try:
                w.attributes("-alpha", 1 - t)
            except tk.TclError:
                pass
        self._anim = self.app.animate(CLOSE_MS, step, w.destroy)

    def _watch_focus(self):
        """Close when you click into another window. Polls the foreground window:
        FocusOut is not reliable for a borderless window that Windows may not
        let take the focus."""
        if self.win is None:
            return
        fg = ctypes.windll.user32.GetForegroundWindow()
        if fg in (hwnd_of(self.win), self.app._hwnd, self.app.tip.hwnd):
            self._had_focus = True
        elif self._had_focus or fg != self._fg0:
            self.close()
            return
        self.win.after(150, self._watch_focus)

    def place(self, W, H):
        app = self.app
        sw, sh = app.root.winfo_screenwidth(), app.root.winfo_screenheight()
        wl, wt, wr, wb = workarea() or (0, 0, sw, sh)
        sx, sy = app.root.winfo_x(), app.root.winfo_y()
        x = sx + (app.W - W) // 2
        x = min(max(x, wl + app.px(8)), wr - W - app.px(8))
        bottom = min(sy, wb) - app.px(PANEL_GAP)
        y = max(wt + app.px(8), bottom - H)
        self.win.geometry(f"{W}x{H}+{x}+{y + self._slide}")

    def render(self, e=1.0):
        """Draw the panel. `e` (0–1) is how far the open animation has got: bars,
        marks and numbers are drawn at that share of their value."""
        if self.win is None:
            return
        app, c, cv = self.app, self.app.colors(), self.cv
        self.c = c
        cv.delete("all")
        self.imgs = []
        px, d = app.px, app.data
        W = px(PANEL_W)
        pad = px(24)
        right = W - pad
        F = app.fonts

        def image(x, y, pil, anchor="nw", tags=()):
            ph = ImageTk.PhotoImage(pil)
            self.imgs.append(ph)
            return cv.create_image(x, y, image=ph, anchor=anchor, tags=tags)

        def text(x, y, s, font, color, anchor="w", tags=()):
            return cv.create_text(x, y, text=s, font=font, fill=color, anchor=anchor, tags=tags)

        def hover(tag, lines):
            cv.tag_bind(tag, "<Enter>", lambda ev: app.tip.schedule(lines))
            cv.tag_bind(tag, "<Leave>", lambda ev: app.tip.hide())

        # header: logo, "Claude Usage", updated
        y = px(30)
        image(pad, y, logo_image(px(20)), anchor="w")
        tx = pad + px(28)
        text(tx, y, "Claude", F["title_b"], c["text"])
        text(tx + F["title_b"].measure("Claude ") , y, "Usage", F["title"], c["text"])
        if app.refreshing:
            upd, col = "Refreshing…", c["sub"]
        else:
            ago, mins = format_ago(d.get("updated"))
            upd, col = f"Updated {ago}", (c["stale"] if mins > STALE_MIN else c["sub"])
        text(right, y, upd, F["small"], col, anchor="e")

        # weekly limit
        wk = d.get("weekly") or {}
        pct = int(wk.get("percent") or 0)
        resets = reset_time(wk, d.get("updated"))
        y = px(72)
        text(pad, y, "Weekly limit · all models", F["body"], c["sub"])
        y = px(108)
        text(pad - px(2), y, f"{round(pct * e)}%", F["big"], c["crit"] if pct >= 90 else c["text"])
        if resets:
            text(right, y - px(10), f"Resets in {format_left(resets)}", F["body_b"], c["text"], anchor="e")
            text(right, y + px(13), reset_label(resets, "%a %H:%M"), F["body"], c["sub"], anchor="e")

        elapsed, label, style, detail = week_pace(pct, resets)
        days = week_days(pct, resets, app.history) if resets else []
        today_i = next((i for i, dd in enumerate(days) if dd["state"] == "today"), None)
        y = px(146)
        fill, fill2 = ((c["crit"], c["crit"]) if pct >= 90 else (c["fill"], c["fill2"]))
        image(pad, y, bar_image(W - 2 * pad, px(8), pct * e, c["track"], fill, fill2, c["marker"],
                                None if elapsed is None else elapsed * e, px(2), px(18)),
              anchor="w", tags="mainbar")
        if elapsed is not None:
            gone = round(elapsed * 100)
            hover("mainbar", [
                f"Day {today_i + 1 if today_i is not None else '—'} of 7 · {gone}% of the week gone",
                f"Used {pct}% of the limit · even pace now: {gone}%",
                "The mark moves right as the week goes on.",
                "Stay left of it and the limit lasts the week.",
            ])

        # pace pill + detail
        y = px(182)
        x = pad
        if label:
            bg, fg = c[style]
            tw = F["small_b"].measure(label)
            image(x, y, rrect_image(tw + px(20), px(24), px(12), bg), anchor="w")
            text(x + px(10), y, label, F["small_b"], fg)
            x += tw + px(30)
        text(x, y, detail, F["small"], c["sub"])

        y = px(212)
        cv.create_line(pad, y, right, y, fill=c["sep"])
        y += px(26)

        def section(title, note=None):
            nonlocal y
            text(pad, y, title, F["small"], c["dim"])
            if note:
                text(right, y, note, F["small"], c["dim"], anchor="e")
            y += px(30)

        def row(name, value_pct, value_text=None, note=None, fill=None, tag=""):
            nonlocal y
            text(pad, y, name, F["body"], c["text"], tags=tag)
            if note:
                text(pad + F["body"].measure(name) + px(8), y + px(1), note, F["small"], c["dim"], tags=tag)
            bx, bw = px(198), px(118)
            f1, f2 = (fill, fill) if fill else (c["fill"], c["fill2"])
            image(bx, y, bar_image(bw, px(6), value_pct * e, c["track"], f1, f2), anchor="w", tags=tag)
            text(right, y, value_text or f"{round(value_pct * e)}%", F["body_b"], c["text"], anchor="e", tags=tag)
            y += px(32)

        # this week by day: a column per day, and today's budget under it
        if days:
            section("This week by day", f"- - even pace {EVEN_DAY:.0f}% a day")
            ch, gap = px(52), px(8)
            colw = (W - 2 * pad - 6 * gap) // 7
            top = y - px(12)
            bottom = top + ch
            scale = max(max(dd["value"] or 0 for dd in days), EVEN_DAY) * 1.15
            faint = mix(c["track"], c["bg"], 0.45)
            for i, dd in enumerate(days):
                x = pad + i * (colw + gap)
                tag = f"day{i}"
                image(x, top, rrect_image(colw, ch, px(5), faint), tags=tag)
                v = dd["value"]
                if v:
                    h = max(px(4), round(ch * v / scale * e))
                    col = c["fill"] if dd["state"] == "today" else c["fill2"]
                    image(x, bottom, rrect_image(colw, h, min(px(5), h // 2), col), anchor="sw", tags=tag)
                elif dd["state"] == "nodata":
                    text(x + colw // 2, bottom - px(10), "–", F["small"], c["dim"], anchor="center", tags=tag)
                is_today = dd["state"] == "today"
                text(x + colw // 2, bottom + px(12), dd["label"], F["small_b"] if is_today else F["small"],
                     c["text"] if is_today else c["dim"], anchor="center", tags=tag)
                a = dd["start"] + DAY / 2
                date = f"{a:%a} {a.day} {a:%b}"
                hover(tag, {
                    "today":  ["Today", f"{v}% of the weekly limit so far" if v is not None else "No data yet"],
                    "past":   [date, f"{v}% of the weekly limit"],
                    "nodata": [date, "No data: the widget was not running"],
                    "future": [date, "Still to come"],
                }[dd["state"]])
            pace_y = bottom - round(ch * EVEN_DAY / scale)
            cv.create_line(pad, pace_y, right, pace_y, fill=c["dim"], dash=(2, 3))
            y = bottom + px(12) + px(34)

            # today's budget: what is left, spread evenly over the days that are left
            if today_i is not None and pct < 100:
                td = days[today_i]
                now = datetime.now().astimezone()
                base = td["base"] if td["base"] is not None else pct
                since = td["start"] if td["base"] is not None else now
                left_days = max((resets - since) / DAY, 0.1)
                budget = max((100 - base) / left_days, 0.1)
                used = td["value"]
                over = used is not None and used > budget
                row("Today", min(100, used / budget * 100) if used is not None else 0,
                    f"{round(used * e)}%" if used is not None else "—",
                    f"budget ~{budget:.0f}% a day", c["crit"] if over else None, "budget")
                hover("budget", [
                    f"Today's budget: ~{budget:.0f}% of the limit",
                    f"{100 - base}% is left for {left_days:.1f} days.",
                    "Over budget today" if over else "Stay under it and the limit lasts the week.",
                ])
            y += px(8)

        # The API gives each product's share of this week's usage. Show how much of
        # the weekly limit that share is (share × weekly %), with the share as a note.
        # Claude Code and Chats always show; other products only once used.
        products = [p for p in d.get("products") or []
                    if p.get("percent") or p.get("key", p.get("name")) in
                    ("claude_code", "chat", "Claude Code", "Chats")]
        if products:
            section("This week by product", "of weekly limit")
            for p in products:
                share = int(p.get("percent") or 0)
                part = share * pct / 100
                shown = f"{round(part * e)}%" if part >= 0.5 or not share else "<1%"
                row(p.get("name", "—"), part, shown, f"{share}% of use")
            y += px(8)

        fable = d.get("fable") or {}
        extra = d.get("extra") or {}
        others = []
        if fable.get("available"):
            others.append(("Fable · weekly", int(fable.get("percent") or 0), None))
        if extra.get("enabled"):
            others.append(("Extra usage", int(extra.get("percent") or 0),
                           f"${extra.get('spent', 0):.2f} / ${extra.get('limit', 0):.0f}"))
        if others:
            section("Other limits")
            for name, p, val in others:
                row(name, p, val)
            y += px(8)

        # buttons
        y += px(10)
        bh = px(34)
        buttons = [("Open usage page", self._open_page), ("Refresh", self._refresh)]
        x = pad
        for label_, cmd in buttons:
            x += self._button(x, y, bh, label_, cmd) + px(8)
        qw = F["body"].measure("Quit") + px(24)
        self._button(right - qw, y, bh, "Quit", app.quit)
        self._theme_button(right - qw - px(8) - bh, y, bh)

        H = y + bh // 2 + pad - px(4)
        cv.configure(width=W, height=H)
        self.place(W, H)

    def _button(self, x, y, h, label, cmd):
        """A flat button that shows a soft rounded background on hover. Returns its width."""
        c, cv, px, F = self.c, self.cv, self.app.px, self.app.fonts
        w = F["body"].measure(label) + px(24)
        tag = f"btn_{label}"
        states = {k: ImageTk.PhotoImage(rrect_image(w, h, px(6), c[k])) for k in ("btn", "hover", "press")}
        self.imgs.extend(states.values())
        bg = cv.create_image(x, y, image=states["btn"], anchor="w", tags=tag)
        cv.create_text(x + w // 2, y, text=label, font=F["body"], fill=c["text"], tags=tag)
        cv.tag_bind(tag, "<Enter>", lambda e: (cv.itemconfigure(bg, image=states["hover"]),
                                              cv.configure(cursor="hand2")))
        cv.tag_bind(tag, "<Leave>", lambda e: (cv.itemconfigure(bg, image=states["btn"]),
                                              cv.configure(cursor="")))
        cv.tag_bind(tag, "<ButtonPress-1>", lambda e: cv.itemconfigure(bg, image=states["press"]))
        cv.tag_bind(tag, "<ButtonRelease-1>", lambda e: (cv.itemconfigure(bg, image=states["hover"]), cmd()))
        return w

    def _theme_button(self, x, y, h):
        """A square button with the current theme's icon; a click picks the next theme."""
        app, c, cv, px = self.app, self.c, self.cv, self.app.px
        pref = app.theme_pref
        tag = "btn_theme"
        states = {k: ImageTk.PhotoImage(rrect_image(h, h, px(6), c[k])) for k in ("btn", "hover", "press")}
        icon = ImageTk.PhotoImage(theme_icon(pref, px(16), c["text"]))
        self.imgs.extend([*states.values(), icon])
        bg = cv.create_image(x, y, image=states["btn"], anchor="w", tags=tag)
        cv.create_image(x + h // 2, y, image=icon, anchor="center", tags=tag)
        nxt = THEMES[(THEMES.index(pref) + 1) % len(THEMES)]
        names = {"system": "Same as Windows", "light": "Light", "dark": "Dark"}
        lines = [f"Theme: {names[pref]}", f"Click for {names[nxt]}"]

        def enter(_e):
            cv.itemconfigure(bg, image=states["hover"])
            cv.configure(cursor="hand2")
            app.tip.schedule(lines)

        def leave(_e):
            cv.itemconfigure(bg, image=states["btn"])
            cv.configure(cursor="")
            app.tip.hide()

        cv.tag_bind(tag, "<Enter>", enter)
        cv.tag_bind(tag, "<Leave>", leave)
        cv.tag_bind(tag, "<ButtonPress-1>", lambda e: cv.itemconfigure(bg, image=states["press"]))
        cv.tag_bind(tag, "<ButtonRelease-1>", lambda e: app.next_theme())

    def retheme(self):
        """Redraw an open panel in the current colors (after a theme change)."""
        if self.win is None:
            return
        c = self.app.colors()
        self.win.configure(bg=c["bg"])
        self.cv.configure(bg=c["bg"])
        round_corners(self.win, c["border"])
        self.render()

    def _open_page(self):
        webbrowser.open(USAGE_PAGE)
        self.close()

    def _refresh(self):
        self.app.refresh()


# ── the strip (sits on the taskbar) ─────────────────────────────────────────
class UsageWidget:
    def __init__(self):
        enable_dpi_awareness()
        self.data = load_data()
        self.history = record_history(self.data)
        self._strip_pct = float((self.data.get("weekly") or {}).get("percent") or 0)
        self._anim_next = 0
        self._anims = set()
        self.motion = motion_enabled()
        self._mtime = self._file_mtime()
        self._frame = 0
        self._press = None
        self._dragging = False
        self._hover = False
        self._refresh_until = 0.0
        self._theme = (light_theme("AppsUseLightTheme"), light_theme("SystemUsesLightTheme"))
        self.theme_pref = load_settings().get("theme")
        if self.theme_pref not in THEMES:
            self.theme_pref = "system"

        self.root = tk.Tk()
        self.root.title("Claude Usage Widget")
        self.S = self.root.winfo_fpixels("1i") / 96.0
        self.fonts = self._make_fonts()
        self.panel = Panel(self)
        self.tip = Tooltip(self)
        self._setup_window()
        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                bg=self.tb_bg, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._bind_events()
        self.root.update()                    # the window must exist before it gets an owner
        self._own_by_taskbar()
        self._hook_foreground()
        self.redraw()
        self._tick()

    # ── sizes, fonts, colors ──────────────────────────────────────────────
    def px(self, v):
        return int(round(v * self.S))

    def _make_fonts(self):
        fams = set(tkfont.families(self.root))

        def pick(*names):
            return next((n for n in names if n in fams), "Segoe UI")

        text = pick("Segoe UI Variable Text", "Segoe UI")
        text_b = pick("Segoe UI Variable Text Semibold", "Segoe UI Semibold")
        disp = pick("Segoe UI Variable Display Semib", "Segoe UI Semibold")
        small = pick("Segoe UI Variable Small", "Segoe UI")
        small_b = pick("Segoe UI Variable Small Semibol", "Segoe UI Semibold")
        f = lambda fam, size: tkfont.Font(self.root, family=fam, size=size)
        return {
            "title": f(disp.replace(" Semib", "") if "Variable" in disp else text, 13),
            "title_b": f(disp, 13),
            "big": f(disp, 30),
            "body": f(text, 10),
            "body_b": f(text_b, 10),
            "small": f(small, 9),
            "small_b": f(small_b, 9),
            "strip": f(text, 10),
            "strip_b": f(text_b, 10),
        }

    def colors(self):
        """Panel and tooltip colors: your theme choice, or Windows' app theme."""
        if self.theme_pref != "system":
            return LIGHT if self.theme_pref == "light" else DARK
        return LIGHT if self._theme[0] else DARK

    def next_theme(self):
        self.theme_pref = THEMES[(THEMES.index(self.theme_pref) + 1) % len(THEMES)]
        save_settings(theme=self.theme_pref)
        self.tip.hide()
        self.panel.retheme()

    # ── animation ─────────────────────────────────────────────────────────
    def animate(self, ms, step, done=None):
        """Call step(t) for t from 0 to 1 over `ms` (~60 fps), then done().
        With Windows animation effects off, it jumps straight to the end.
        Returns an id for is_animating()."""
        self._anim_next += 1
        aid = self._anim_next
        if not self.motion:
            step(1.0)
            if done:
                done()
            return aid
        self._anims.add(aid)
        t0 = time.perf_counter()

        def frame():
            t = min(1.0, (time.perf_counter() - t0) * 1000 / ms)
            step(t)
            if t < 1.0:
                self.root.after(16, frame)
            else:
                self._anims.discard(aid)
                if done:
                    done()
        frame()
        return aid

    def is_animating(self, aid):
        return aid in self._anims

    # ── window setup ──────────────────────────────────────────────────────
    def _taskbar(self):
        r = self.root
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        wa = workarea()
        wl, wt, wr, wb = wa or (0, 0, sw, sh)
        tb_top = wb if (wa and sh * 0.5 < wb <= sh + 2) else sh - self.px(48)
        return wr, tb_top, sh - tb_top

    def _setup_window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        wr, tb_top, tb_h = self._taskbar()
        self.W, self.H = self.px(STRIP_W), max(self.px(40), tb_h)
        # default spot (until you drag it): on the taskbar, just left of the tray
        x, y = wr - self.px(TRAY_MARGIN) - self.W, tb_top + max(0, (tb_h - self.H) // 2)
        saved = self._load_pos()
        if saved:
            x, y = saved                      # reopen where you left it
        x, y = self._clamp(x, y)
        self.tb_bg = self._sample_taskbar(x, y)
        r.configure(bg=self.tb_bg)
        r.geometry(f"{self.W}x{self.H}+{x}+{y}")
        r.update_idletasks()
        self._hwnd = hwnd_of(r)

    def _sample_taskbar(self, x, y):
        """The taskbar's color under the strip, so the strip blends in."""
        fallback = "#EEEEEE" if self._theme[1] else "#1C1C1C"
        try:
            img = ImageGrab.grab(bbox=(x, y, x + self.W, y + self.H)).convert("RGB")
            count, rgb = max(img.getcolors(self.W * self.H) or [(0, None)])
            return rgb_hex(rgb) if rgb else fallback
        except Exception:
            return fallback

    def _sample_beside(self):
        """The taskbar's color in thin columns just left and right of the strip,
        read without hiding the strip. None when the two sides do not agree
        (an icon, a full-screen app or anything else that is not plain taskbar)."""
        x, y, W, H = self.root.winfo_x(), self.root.winfo_y(), self.W, self.H
        gap, cw = self.px(3), self.px(8)
        sw = self.root.winfo_screenwidth()
        sides = []
        for left in (x - gap - cw, x + W + gap):
            if left < 0 or left + cw > sw:
                continue
            try:
                img = ImageGrab.grab(bbox=(left, y + 2, left + cw, y + H - 2)).convert("RGB")
            except Exception:
                return None
            n = img.width * img.height
            count, rgb = max(img.getcolors(n) or [(0, None)])
            if rgb and count >= n * 0.6:              # a plain area, not an icon
                sides.append(rgb)
        if not sides:
            return None
        if len(sides) == 2 and sum(abs(a - b) for a, b in zip(*sides)) > 12:
            return None
        return rgb_hex(sides[0])

    def _follow_taskbar(self):
        """Keep the strip the same color as the taskbar. The taskbar color
        changes with the wallpaper, the accent color and transparency, and at
        sign-in it is not painted yet when the strip starts. A new color must be
        seen twice in a row, so a short flash does not change the strip."""
        if self._dragging:
            return
        col = self._sample_beside()
        if not col or col == self.tb_bg:
            self._tb_seen = None
            return
        if col != getattr(self, "_tb_seen", None):
            self._tb_seen = col
            return
        self._tb_seen = None
        self.tb_bg = col
        self.root.configure(bg=col)
        self.canvas.configure(bg=col)
        self._redraw_strip()

    def _resample(self):
        """Theme changed: hide, read the taskbar color again, show."""
        r = self.root
        r.withdraw()
        r.update()
        r.after(150, lambda: (setattr(self, "tb_bg", self._sample_taskbar(r.winfo_x(), r.winfo_y())),
                              r.configure(bg=self.tb_bg), self.canvas.configure(bg=self.tb_bg),
                              r.deiconify(), self.redraw()))

    def _clamp(self, x, y):
        """Keep the strip on-screen and clear of the clock / tray."""
        r = self.root
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        wl, wt, wr, wb = workarea() or (0, 0, sw, sh)
        min_x = wl + EDGE_MARGIN
        max_x = max(min_x, wr - self.W - self.px(TRAY_MARGIN))
        max_y = max(0, sh - self.H)
        return min(max(x, min_x), max_x), min(max(y, 0), max_y)

    def _show_front(self):
        """Pull the strip back into view (another launch asked for it)."""
        x, y = self._clamp(self.root.winfo_x(), self.root.winfo_y())
        self.root.geometry(f"+{x}+{y}")
        try:
            self.root.deiconify()
        except Exception:
            pass
        self.root.lift()
        self.root.attributes("-topmost", True)
        self._save_pos()

    # ── remember / restore position ───────────────────────────────────────
    def _load_pos(self):
        try:
            if POS_FILE.exists():
                p = json.loads(POS_FILE.read_text(encoding="utf-8")).get(POS_KEY)
                if p:
                    return int(p["x"]), int(p["y"])
        except Exception:
            pass
        return None

    def _save_pos(self):
        try:
            data = {}
            if POS_FILE.exists():
                data = json.loads(POS_FILE.read_text(encoding="utf-8"))
            data[POS_KEY] = {"x": self.root.winfo_x(), "y": self.root.winfo_y()}
            POS_FILE.parent.mkdir(parents=True, exist_ok=True)
            POS_FILE.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    def quit(self):
        self.quitting = True
        self._save_pos()
        self.root.destroy()

    def _assert_topmost(self):
        """Re-push above the Z-order so it stays over the taskbar."""
        try:
            hwnd = self._hwnd or self.root.winfo_id()
            ctypes.windll.user32.SetWindowPos(
                ctypes.c_void_p(hwnd), ctypes.c_void_p(-1),  # HWND_TOPMOST
                0, 0, 0, 0, 0x0013)                          # NOMOVE|NOSIZE|NOACTIVATE
        except Exception:
            pass

    def _own_by_taskbar(self):
        """Make the taskbar the strip's owner window. Windows keeps an owned
        window above its owner, also when the Start menu (or search, or the
        notification center) lifts the taskbar into a layer above all normal
        topmost windows; without an owner the strip was hidden while Start was
        open. (A child window of the taskbar does not work on Windows 11: the
        taskbar's XAML layer draws over every child window.)
        The strip and the taskbar then share one input queue, so the strip must
        never block for long."""
        try:
            u = ctypes.windll.user32
            tray = u.FindWindowW("Shell_TrayWnd", None)
            if not tray or not self._hwnd:
                return
            u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            u.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
            u.SetWindowLongPtrW(self._hwnd, -8, tray)                  # GWLP_HWNDPARENT = owner
            self._tray = tray
            self._assert_topmost()
        except Exception:
            pass

    def _hook_foreground(self):
        """Go back on top the moment another window comes to the front.
        A click on the taskbar (or the Start button, or a tray icon) brings the
        taskbar to the front, over the strip; the 3-second check alone left the
        strip hidden for up to 3 s, so it seemed to blink and jump. The taskbar
        can raise itself a moment after the event, so check again soon after."""
        WINEVENTPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                                          wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)

        # The callback runs inside Tk's own message loop, so it must not call Tk
        # (that kills Python: "PyEval_RestoreThread … GIL is released"). It only
        # calls Win32 and sets a time; _zorder_watch (a Tk timer) does the rest.
        hwnd = self._hwnd

        def on_event(_hook, _event, _hwnd, _obj, _child, _thread, _time):
            if not self._dragging and hwnd:
                ctypes.windll.user32.SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(-1),
                                                  0, 0, 0, 0, 0x0013)
            self._fg_at = time.perf_counter()

        self._fg_at = 0.0
        self._fg_proc = WINEVENTPROC(on_event)      # keep a reference: ctypes must not free it
        try:
            u = ctypes.windll.user32
            u.SetWinEventHook.restype = wintypes.HANDLE
            u.SetWinEventHook.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
                                          wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
            # EVENT_SYSTEM_FOREGROUND; WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
            self._fg_hook = u.SetWinEventHook(0x0003, 0x0003, None, self._fg_proc, 0, 0, 0x0002)
        except Exception:
            self._fg_hook = None
        self._zorder_watch()

    def _zorder_watch(self):
        """For half a second after another window came to the front, go back on
        top every 50 ms: the taskbar can raise itself a moment after the event."""
        if not self._dragging and time.perf_counter() - self._fg_at < 0.5:
            self._assert_topmost()
        self.root.after(50, self._zorder_watch)

    # ── events ────────────────────────────────────────────────────────────
    def _bind_events(self):
        cv = self.canvas
        cv.bind("<ButtonPress-1>",   self._on_press)
        cv.bind("<B1-Motion>",       self._on_drag)
        cv.bind("<ButtonRelease-1>", self._on_release)
        cv.bind("<Button-3>",        lambda e: self.panel.toggle())
        cv.bind("<Enter>",           lambda e: self._set_hover(True))
        cv.bind("<Leave>",           lambda e: self._set_hover(False))

    def _set_hover(self, on):
        self._hover = on
        self._redraw_strip()
        if on and not self.panel.is_open:
            self.tip.schedule(self._strip_tip(), above_y=self.root.winfo_y() - self.px(8), delay=600)
        else:
            self.tip.hide()

    def _strip_tip(self):
        d = self.data
        wk = d.get("weekly") or {}
        pct = int(wk.get("percent") or 0)
        resets = reset_time(wk, d.get("updated"))
        elapsed, label, _, _ = week_pace(pct, resets)
        lines = [f"Weekly limit {pct}%" + (f" · {label}" if label else "")]
        if resets:
            lines.append(f"Resets in {format_left(resets)} (after {reset_label(resets, '%a %H:%M')})")
            lines.append(f"{round(elapsed * 100)}% of the week gone · click for details")
        return lines

    def _on_press(self, e):
        self.tip.hide()
        self._press = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._dragging = False

    def _on_drag(self, e):
        if not self._press:
            return
        x0, y0, wx, wy = self._press
        if not self._dragging and abs(e.x_root - x0) + abs(e.y_root - y0) < self.px(5):
            return
        if not self._dragging:
            self._dragging = True
            self.panel.close()
        nx, ny = self._clamp(wx + e.x_root - x0, wy + e.y_root - y0)
        self.root.geometry(f"+{nx}+{ny}")

    def _on_release(self, e):
        if self._dragging:
            self._save_pos()
            self._tb_seen = None              # _follow_taskbar reads the color at the new place
        else:
            self.panel.toggle()
        self._press = None
        self._dragging = False

    # ── data watching ─────────────────────────────────────────────────────
    def _file_mtime(self):
        try:
            return DATA_FILE.stat().st_mtime
        except OSError:
            return 0

    def _reload(self):
        self.data = load_data()
        self.history = record_history(self.data)
        self._mtime = self._file_mtime()
        self._refresh_until = 0.0
        self.redraw()
        # the strip's number and bar move to the new value
        old, new = self._strip_pct, float((self.data.get("weekly") or {}).get("percent") or 0)
        if old != new:
            def step(t):
                self._strip_pct = old + (new - old) * ease_out(t)
                self._redraw_strip()
            self.animate(STRIP_MS, step)

    @property
    def refreshing(self):
        return datetime.now().timestamp() < self._refresh_until

    def refresh(self):
        """Ask for fresh data: the receiver passes the request on to the browser
        extension, and a saved key (cookie / paste method) fetches directly."""
        self._refresh_until = datetime.now().timestamp() + 20
        self.panel.render()

        def work():
            try:
                req = urllib.request.Request(RECEIVER_REFRESH, data=b"{}", method="POST")
                urllib.request.urlopen(req, timeout=2).close()
            except Exception:
                pass
            try:
                import credential_store
                if credential_store.load():
                    import fetch_usage
                    fetch_usage.run_once(verbose=False)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _tick(self):
        self._frame += 1
        ev = getattr(self, "_show_event", None)
        if ev and ctypes.windll.kernel32.WaitForSingleObject(ev, 0) == 0:
            ctypes.windll.kernel32.ResetEvent(ev)
            self._show_front()                # another launch asked us to come forward
        if not self.panel.is_open:
            self._assert_topmost()            # stay above the taskbar (backup for _hook_foreground)
        if self._frame % 2 == 0:
            self._follow_taskbar()            # match the taskbar's color as it changes
        if self._frame % 5 == 0:
            theme = (light_theme("AppsUseLightTheme"), light_theme("SystemUsesLightTheme"))
            if theme != self._theme:
                self._theme = theme
                self.panel.close()
                self._resample()
        if self._file_mtime() != self._mtime:
            self._reload()
        elif self._frame % 30 == 0:
            self.redraw()                     # keep "until …" and "Updated … ago" current
        elif self.panel.is_open and self._refresh_until and not self.refreshing:
            self._refresh_until = 0.0
            self.panel.render()               # refresh timed out: back to "Updated … ago"
        self.root.after(TICK_MS, self._tick)

    # ── drawing ───────────────────────────────────────────────────────────
    def redraw(self):
        self._redraw_strip()
        if self.panel.is_open and not self.panel.animating:   # the open animation draws it
            self.panel.render()

    def _redraw_strip(self):
        cv, px, W, H = self.canvas, self.px, self.W, self.H
        cv.delete("all")
        self._imgs = []
        bg = self.tb_bg
        dark_bar = luminance(bg) > 0.5
        fg = "#1B1B1B" if dark_bar else "#F3F3F3"
        sub = mix(fg, bg, 0.38)
        c = LIGHT if dark_bar else DARK

        def image(x, y, pil, anchor="w"):
            ph = ImageTk.PhotoImage(pil)
            self._imgs.append(ph)
            cv.create_image(x, y, image=ph, anchor=anchor)

        if self._hover or self.panel.is_open:  # like a taskbar button's hover
            image(px(2), H // 2, rrect_image(W - px(4), H - px(8), px(5),
                                             mix(bg, "#FFFFFF" if not dark_bar else "#000000",
                                                 0.10 if self.panel.is_open else 0.06)))

        image(px(10), H // 2, logo_image(px(22)))

        d = self.data
        wk = d.get("weekly") or {}
        pct = int(wk.get("percent") or 0)
        shown = self._strip_pct                # moves to `pct` when new data comes in
        resets = reset_time(wk, d.get("updated"))
        tx, ty = px(42), H // 2 - px(7)
        f_b, f = self.fonts["strip_b"], self.fonts["strip"]
        num = f"{round(shown)}%"
        cv.create_text(tx, ty, text=num, font=f_b, anchor="w",
                       fill=c["crit"] if pct >= 90 else fg)
        until = f"until {reset_label(resets, '%a')}" if resets else ""
        cv.create_text(tx + f_b.measure(num) + px(6), ty, text=until, font=f, fill=sub, anchor="w")

        elapsed = week_pace(pct, resets)[0]
        fill, fill2 = (c["crit"], c["crit"]) if pct >= 90 else (c["fill"], c["fill2"])
        image(tx, H // 2 + px(10), bar_image(W - tx - px(12), px(4), shown, mix(bg, fg, 0.16),
                                             fill, fill2, sub, elapsed, max(1, px(2)), px(10)))

    def run(self):
        self.root.mainloop()


def main():
    # Single instance: if one is already running, tell it to come to the front
    # (so the hotkey / Start-Menu entry "re-opens" it) instead of stacking copies.
    _show_event = None
    try:
        _k = ctypes.WinDLL("kernel32", use_last_error=True)
        _show_event = _k.CreateEventW(None, True, False, "claude-usage-widget-show-event")
        _k.CreateMutexW(None, False, "claude-usage-widget-single-instance")
        if ctypes.get_last_error() == 183:      # ERROR_ALREADY_EXISTS
            if _show_event:
                _k.SetEvent(_show_event)
            raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        _show_event = None

    # The taskbar owns the strip. When Explorer restarts, Windows destroys the
    # strip together with the old taskbar: wait for the new taskbar and start again.
    while True:
        w = UsageWidget()
        w._show_event = _show_event
        try:
            w.run()
        except Exception:
            pass
        if getattr(w, "quitting", False):
            break
        for _ in range(60):
            time.sleep(1)
            if ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None):
                break
        time.sleep(2)                         # let the new taskbar finish drawing


if __name__ == "__main__":
    main()
