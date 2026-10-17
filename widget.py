#!/usr/bin/env python3
"""
Claude Code Usage Widget — floating desktop widget for Windows.

Two layouts (set LAYOUT below):
  "horizontal" — a thin strip that docks just above the taskbar (default)
  "vertical"   — a tall card in the bottom-right corner

- Drag to move
- Double-click to refresh now
- Right-click to quit

Reads usage_data.json written by fetch_usage.py or receiver.py, and picks up new
data on its own (watches the file's modification time). The pixel mascot's mood
follows your session usage.
"""

import ctypes
import json
import os
import tkinter as tk
from ctypes import wintypes
from datetime import datetime
import sys
from pathlib import Path

# next to the .exe when built with PyInstaller, else next to this script
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_FILE = APP_DIR / "usage_data.json"
# remembers where you last dragged the widget (per layout)
POS_FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "claude-usage-widget" / "widget_pos.json"

LAYOUT = "compact"           # "compact" (tiny, sits on the taskbar), "horizontal" (strip above
                             # the taskbar), or "vertical" (corner card)

# ── color palette ───────────────────────────────────────────────────────────
C = {
    "bg":        "#0D0D0D",
    "surface":   "#111111",
    "border":    "#D97706",   # Claude orange
    "title":     "#F59E0B",   # amber
    "text":      "#E5E7EB",
    "dim":       "#6B7280",
    "bar_fill":  "#3B82F6",   # blue progress
    "bar_bg":    "#1E293B",
    "bar_warn":  "#F59E0B",   # amber at 75%+
    "bar_crit":  "#EF4444",   # red at 90%+
    "green":     "#10B981",
    "separator": "#262B36",
    "bot":       "#E07050",   # mascot body
    "bot_dark":  "#1C1E21",   # mascot eyes/mouth
    "sweat":     "#7DD3FC",
    "reset":     "#FDE047",   # bright yellow — "resets in …" text
}

FONT = "Consolas"            # ships with Windows; monospace
ANIM_MS = 220               # mascot animation tick

# vertical layout geometry
V_W, V_H = 440, 520
MASCOT_TOP = 44
# horizontal layout geometry
H_W, H_H = 860, 60
# compact (on-taskbar) geometry
COMPACT_W = 480
COMPACT_H = 44
TRAY_MARGIN = 300   # px kept clear on the right for the clock / system tray
EDGE_MARGIN = 8     # px kept clear on the left


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, encoding="utf-8-sig") as f:   # tolerate a BOM
                return json.load(f)
        except Exception:
            pass
    return {
        "session": {"percent": 0, "resets_in": "—"},
        "weekly":  {"percent": 0, "resets_in": "—"},
        "fable":   {"percent": 0, "resets_in": "—", "available": False},
        "extra":   {"spent": 0.0, "percent": 0, "limit": 20.0, "resets": "—", "enabled": False},
        "plan":    "—",
        "updated": None,
    }


def bar_color(pct):
    if pct >= 90:
        return C["bar_crit"]
    if pct >= 75:
        return C["bar_warn"]
    return C["bar_fill"]


def mood_for(pct):
    if pct >= 100: return ("sleep",  "limit hit · resting", C["bar_crit"])
    if pct >= 90:  return ("panic",  "panicking",           C["bar_crit"])
    if pct >= 75:  return ("hustle", "hustling",            C["bar_warn"])
    if pct >= 25:  return ("work",   "working",             C["text"])
    return             ("idle",   "idle",                C["dim"])


def format_ago(iso_str):
    if not iso_str:
        return "never"
    try:
        dt = datetime.fromisoformat(iso_str)
        secs = (datetime.now() - dt).total_seconds()
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{int(secs / 60)}m ago"
        return f"{int(secs / 3600)}h ago"
    except Exception:
        return "—"


def workarea():
    """Primary-monitor rect excluding the taskbar, or None."""
    try:
        r = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
        return r.left, r.top, r.right, r.bottom
    except Exception:
        return None


class UsageWidget:
    def __init__(self):
        self.data = load_data()
        self._mtime = self._file_mtime()
        self._frame = 0
        self._drag_x = self._drag_y = 0
        self._mascot_pos = (0, 0, 6)
        self.W, self.H = V_W, V_H           # set for real in _setup_window

        self.root = tk.Tk()
        self.root.title("Claude Usage Widget")
        self._setup_window()
        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                bg=C["bg"], highlightthickness=0)
        self.canvas.pack()
        self._bind_events()
        self.redraw()
        self._tick()

    # ── window setup ──────────────────────────────────────────────────────
    def _setup_window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-alpha", 0.97)
        r.attributes("-topmost", True)
        r.configure(bg=C["bg"])
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        wa = workarea()
        if LAYOUT == "compact":
            wl, wt, wr, wb = wa or (0, 0, sw, sh)
            tb_top = wb if (wa and sh * 0.5 < wb <= sh + 2) else sh - 48
            self.W, self.H = COMPACT_W, COMPACT_H
            tb_h = sh - tb_top
            # default spot (until you drag it): centered horizontally, sitting on the
            # taskbar. A repeated topmost push (see _assert_topmost) keeps it visible
            # over the Win11 taskbar. Your dragged position is remembered and takes over.
            x = (wr - self.W) // 2
            y = tb_top + max(0, (tb_h - self.H) // 2)
        elif LAYOUT == "horizontal":
            self.W, self.H = H_W, H_H
            bottom = wa[3] if (wa and sh * 0.5 < wa[3] <= sh + 2) else sh - 48
            x = (sw - self.W) // 2
            y = bottom - self.H - 6
        else:
            self.W, self.H = V_W, V_H
            x = sw - self.W - 24
            y = sh - self.H - 80
        saved = self._load_pos()
        if saved:
            x, y = saved                      # reopen where you left it
        x, y = self._clamp(x, y)
        r.geometry(f"{self.W}x{self.H}+{x}+{y}")
        r.update_idletasks()
        try:
            self._hwnd = ctypes.windll.user32.GetAncestor(self.root.winfo_id(), 2)  # GA_ROOT
        except Exception:
            self._hwnd = 0

    def _clamp(self, x, y):
        """Keep the window on-screen and (compact) clear of the clock/tray.
        Vertical is free — you can drag it all the way down onto the taskbar."""
        r = self.root
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        wl, wt, wr, wb = workarea() or (0, 0, sw, sh)
        reserve = TRAY_MARGIN if LAYOUT == "compact" else 0
        min_x = wl + (EDGE_MARGIN if LAYOUT == "compact" else 0)
        max_x = max(min_x, wr - self.W - reserve)   # can't slide into the clock / system tray
        max_y = max(0, sh - self.H)                 # can go all the way down onto the taskbar
        return min(max(x, min_x), max_x), min(max(y, 0), max_y)

    def _show_front(self):
        """Pull the widget back into view and raise it (triggered when you
        launch it again / press the hotkey while it's already running)."""
        x, y = self._clamp(self.root.winfo_x(), self.root.winfo_y())
        self.root.geometry(f"+{x}+{y}")
        try:
            self.root.deiconify()
        except Exception:
            pass
        self.root.lift()
        self.root.attributes("-topmost", True)
        self._save_pos()

    # ── remember / restore position (per layout) ───────────────────────────
    def _load_pos(self):
        try:
            if POS_FILE.exists():
                p = json.loads(POS_FILE.read_text(encoding="utf-8")).get(LAYOUT)
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
            data[LAYOUT] = {"x": self.root.winfo_x(), "y": self.root.winfo_y()}
            POS_FILE.parent.mkdir(parents=True, exist_ok=True)
            POS_FILE.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    def _quit(self):
        self._save_pos()
        self.root.destroy()

    def _assert_topmost(self):
        """Re-push above the Z-order so it stays over the taskbar when docked onto it."""
        try:
            hwnd = getattr(self, "_hwnd", 0) or self.root.winfo_id()
            ctypes.windll.user32.SetWindowPos(
                ctypes.c_void_p(hwnd), ctypes.c_void_p(-1),  # HWND_TOPMOST
                0, 0, 0, 0, 0x0013)                          # NOMOVE|NOSIZE|NOACTIVATE
        except Exception:
            pass

    # ── events ────────────────────────────────────────────────────────────
    def _bind_events(self):
        cv = self.canvas
        cv.bind("<Button-1>",       self._on_press)
        cv.bind("<B1-Motion>",      self._on_drag)
        cv.bind("<ButtonRelease-1>", lambda e: self._save_pos())
        cv.bind("<Double-1>",       lambda e: self._reload())
        cv.bind("<Button-2>",       lambda e: self._quit())
        cv.bind("<Button-3>",       lambda e: self._quit())

    def _on_press(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _on_drag(self, e):
        nx = self.root.winfo_x() + e.x - self._drag_x
        ny = self.root.winfo_y() + e.y - self._drag_y
        nx, ny = self._clamp(nx, ny)          # can't be dragged behind the taskbar
        self.root.geometry(f"+{nx}+{ny}")

    # ── data watching + animation ─────────────────────────────────────────
    def _file_mtime(self):
        try:
            return DATA_FILE.stat().st_mtime
        except OSError:
            return 0

    def _reload(self):
        self.data = load_data()
        self._mtime = self._file_mtime()
        self.redraw()

    def _tick(self):
        self._frame += 1
        ev = getattr(self, "_show_event", None)
        if ev and ctypes.windll.kernel32.WaitForSingleObject(ev, 0) == 0:
            ctypes.windll.kernel32.ResetEvent(ev)
            self._show_front()                # another launch asked us to come forward
        if self._frame % 5 == 0:
            self._assert_topmost()            # stay above the taskbar even when docked onto it
        if self._file_mtime() != self._mtime:
            self._reload()
        else:
            self._draw_mascot(*self._mascot_pos)
        self.root.after(ANIM_MS, self._tick)

    # ── drawing helpers ───────────────────────────────────────────────────
    def _text(self, x, y, s, color=None, size=10, anchor="w", bold=False, tags=None):
        self.canvas.create_text(x, y, text=s, fill=color or C["text"],
                                font=(FONT, size, "bold" if bold else "normal"),
                                anchor=anchor, tags=tags or ())

    def _bar(self, x, y, w, h, pct):
        cv = self.canvas
        cv.create_rectangle(x, y, x + w, y + h, fill=C["bar_bg"], outline="")
        fill_w = max(3, int(w * min(pct, 100) / 100))
        cv.create_rectangle(x, y, x + fill_w, y + h, fill=bar_color(pct), outline="")

    # ── pixel mascot (tagged "bot" so it animates without a full redraw) ───
    def _px(self, ox, oy, gx, gy, gw, gh, color, scale):
        x, y = ox + gx * scale, oy + gy * scale
        self.canvas.create_rectangle(x, y, x + gw * scale, y + gh * scale,
                                     fill=color, outline="", tags="bot")

    def _draw_mascot(self, cx, cy, scale):
        cv = self.canvas
        cv.delete("bot")
        pct = self.data.get("session", {}).get("percent", 0) or 0
        name, _, _ = mood_for(pct)
        f = self._frame

        speed = {"idle": 6, "sleep": 6, "work": 3, "hustle": 2, "panic": 1}[name]
        phase = (f // max(1, speed)) % 2
        moving = name in ("work", "hustle", "panic")
        bob = -1 if phase else 0
        shake = (1 if f % 2 else -1) if name == "panic" else 0

        ox = cx - round(7 * scale) + shake
        oy = cy - round(5 * scale) + bob * scale

        b, d = C["bot"], C["bot_dark"]
        self._px(ox, oy, 3, 1, 8, 6, b, scale)                 # head
        if name == "sleep" or (f % 18 == 0):                   # eyes (blink / shut)
            self._px(ox, oy, 4, 3, 1, 1, d, scale)
            self._px(ox, oy, 9, 3, 1, 1, d, scale)
        else:
            self._px(ox, oy, 4, 2, 1, 1, d, scale)
            self._px(ox, oy, 9, 2, 1, 1, d, scale)
        self._px(ox, oy, 5, 5, 4, 1, d, scale)                 # mouth
        arm = 1 if (moving and phase) else 0                    # arms
        self._px(ox, oy, 1,  3 + arm, 2, 2, b, scale)
        self._px(ox, oy, 11, 3 + (1 - arm if moving else 0), 2, 2, b, scale)
        if moving and phase:                                    # legs
            self._px(ox, oy, 4, 7, 1, 2, b, scale)
            self._px(ox, oy, 9, 7, 1, 2, b, scale)
        else:
            self._px(ox, oy, 3, 7, 1, 2, b, scale)
            self._px(ox, oy, 10, 7, 1, 2, b, scale)
        if name in ("hustle", "panic"):                         # sweat
            drop = (f % 4) * scale // 2
            cv.create_rectangle(ox + 12 * scale, oy + 1 * scale + drop,
                                ox + 13 * scale, oy + 2 * scale + drop,
                                fill=C["sweat"], outline="", tags="bot")
        if name == "sleep":                                     # z's
            for i in range(3):
                if (f // 3 + i) % 3 == 0:
                    cv.create_text(ox + (12 + i) * scale, oy - i * scale, text="z",
                                   fill=C["dim"], font=(FONT, max(7, scale + 2), "bold"),
                                   tags="bot")

    # ── redraw dispatch ───────────────────────────────────────────────────
    def redraw(self):
        if LAYOUT == "compact":
            self._redraw_compact()
        elif LAYOUT == "horizontal":
            self._redraw_horizontal()
        else:
            self._redraw_vertical()

    # ── compact layout (sits on the taskbar) ──────────────────────────────
    def _redraw_compact(self):
        cv = self.canvas
        cv.delete("all")
        d = self.data
        W, H = self.W, self.H

        cv.create_rectangle(0, 0, W - 1, H - 1, outline=C["border"], width=1)

        # mascot at the left
        cx, cy, scale = 19, H // 2, 2
        self._mascot_pos = (cx, cy, scale)
        self._draw_mascot(cx, cy, scale)

        # right cell: plan + updated
        info_x = W - 8
        self._text(info_x, 14, d.get("plan", "—"), color=C["title"], size=8, anchor="e", bold=True)
        self._text(info_x, 32, f"↻ {format_ago(d.get('updated'))}", color=C["dim"], size=7, anchor="e")

        fable = d.get("fable") or {}
        extra = d.get("extra") or {}
        cols = [
            ("SESSION", d["session"]["percent"], f"↻ {d['session']['resets_in']}"),
            ("WEEKLY",  d["weekly"]["percent"],  f"↻ {d['weekly']['resets_in']}"),
            ("FABLE",   fable.get("percent", 0),
             f"↻ {fable.get('resets_in', '—')}" if fable.get("available") else "no limit"),
            ("EXTRA",   extra.get("percent", 0),
             f"${extra.get('spent', 0):.0f}/${extra.get('limit', 0):.0f}"),
        ]
        start, end = 40, info_x - 52
        gap = 9
        col_w = (end - start - gap * (len(cols) - 1)) // len(cols)
        for i, (label, pct, sub) in enumerate(cols):
            x = start + i * (col_w + gap)
            if i:
                cv.create_line(x - gap // 2, 7, x - gap // 2, H - 7, fill=C["separator"], width=1)
            self._text(x, 13, label, color=C["title"], size=8, bold=True)
            self._text(x + col_w, 13, f"{pct}%", color=C["text"], size=8, anchor="e")
            self._bar(x, 24, col_w, 6, pct)
            self._text(x, 36, sub, color=C["reset"], size=8)

    # ── horizontal layout (above the taskbar) ─────────────────────────────
    def _redraw_horizontal(self):
        cv = self.canvas
        cv.delete("all")
        d = self.data
        W, H = self.W, self.H

        cv.create_rectangle(1, 1, W - 1, H - 1, outline=C["border"], width=1)

        # mascot at the far left
        cx, cy, scale = 34, H // 2, 3
        self._mascot_pos = (cx, cy, scale)
        self._draw_mascot(cx, cy, scale)

        # right info cell: plan + updated
        info_x = W - 12
        self._text(info_x, 16, d.get("plan", "—"), color=C["title"], size=9, anchor="e", bold=True)
        self._text(info_x, 36, f"↻ {format_ago(d.get('updated'))}", color=C["dim"], size=7, anchor="e")

        fable = d.get("fable") or {}
        extra = d.get("extra") or {}
        cols = [
            ("SESSION", d["session"]["percent"], f"resets {d['session']['resets_in']}"),
            ("WEEKLY",  d["weekly"]["percent"],  f"resets {d['weekly']['resets_in']}"),
            ("FABLE",   fable.get("percent", 0),
             f"resets {fable.get('resets_in', '—')}" if fable.get("available") else "no limit"),
            ("EXTRA",   extra.get("percent", 0),
             f"${extra.get('spent', 0):.0f}/${extra.get('limit', 0):.0f}"),
        ]

        start, end = 64, info_x - 70
        gap = 12
        col_w = (end - start - gap * (len(cols) - 1)) // len(cols)
        for i, (label, pct, sub) in enumerate(cols):
            x = start + i * (col_w + gap)
            if i:
                cv.create_line(x - gap // 2, 10, x - gap // 2, H - 10, fill=C["separator"], width=1)
            self._text(x, 15, label, color=C["title"], size=8, bold=True)
            self._text(x + col_w, 15, f"{pct}%", color=C["text"], size=8, anchor="e")
            self._bar(x, 26, col_w, 6, pct)
            self._text(x, 44, sub, color=C["reset"], size=7)

    # ── vertical layout (corner card) ─────────────────────────────────────
    def _redraw_vertical(self):
        cv = self.canvas
        cv.delete("all")
        d = self.data
        W, H = self.W, self.H
        pad = 16
        bar_w = W - pad * 2 - 72

        cv.create_rectangle(1, 1, W - 1, H - 1, outline=C["border"], width=1)

        cv.create_rectangle(1, 1, W - 1, 34, fill=C["surface"], outline="")
        self._text(pad,       17, "◆",                color=C["border"], size=11, bold=True)
        self._text(pad + 18,  17, "CLAUDE CODE",       color=C["title"],  size=10, bold=True)
        self._text(pad + 128, 17, "·  USAGE MONITOR",  color=C["dim"],    size=9)
        self._text(W - pad,   17, d.get("plan", "—"),  color=C["dim"],    size=9, anchor="e")
        cv.create_line(1, 34, W - 1, 34, fill=C["border"], width=1)

        cx, cy, scale = W // 2, MASCOT_TOP + 32, 6
        self._mascot_pos = (cx, cy, scale)
        self._draw_mascot(cx, cy, scale)
        name, label, color = mood_for(d.get("session", {}).get("percent", 0) or 0)
        self._text(W // 2, MASCOT_TOP + 78, label, color=color, size=9, anchor="center")

        y = MASCOT_TOP + 96
        cv.create_line(pad, y, W - pad, y, fill=C["separator"], width=1); y += 14

        def section(title, pct, sub):
            nonlocal y
            self._text(pad, y, title, color=C["title"], size=9, bold=True)
            y += 16
            self._bar(pad, y, bar_w, 7, pct)
            self._text(W - pad, y + 3, f"{pct}% used", color=C["text"], size=9, anchor="e")
            y += 16
            self._text(pad, y, sub, color=C["reset"], size=9)
            y += 18
            cv.create_line(pad, y, W - pad, y, fill=C["separator"], width=1); y += 12

        section("SESSION", d["session"]["percent"], f"Resets in {d['session']['resets_in']}")
        section("WEEKLY",  d["weekly"]["percent"],  f"Resets in {d['weekly']['resets_in']}")
        fable = d.get("fable") or {}
        fsub = (f"Weekly  ·  Resets in {fable.get('resets_in', '—')}"
                if fable.get("available") else "No Fable limit on this plan")
        section("FABLE", fable.get("percent", 0), fsub)

        extra = d.get("extra", {})
        enabled = extra.get("enabled", False)
        self._text(pad, y, "EXTRA USAGE", color=C["title"], size=9, bold=True)
        self._text(W - pad, y, "ON" if enabled else "OFF",
                   color=C["green"] if enabled else C["dim"], size=9, anchor="e", bold=True)
        y += 16
        self._text(pad, y, f"${extra.get('spent', 0.0):.2f} spent  ·  "
                           f"${extra.get('limit', 20.0):.0f} monthly limit", color=C["text"], size=9)
        y += 14
        self._bar(pad, y, bar_w, 7, extra.get("percent", 0))
        self._text(W - pad, y + 3, f"{extra.get('percent', 0)}% used", color=C["text"], size=9, anchor="e")
        y += 16
        self._text(pad, y, f"Resets {extra.get('resets', '—')}", color=C["dim"], size=9)

        cv.create_line(1, H - 26, W - 1, H - 26, fill=C["border"], width=1)
        self._text(pad, H - 13, f"↻  {format_ago(d.get('updated'))}", color=C["dim"], size=8)
        self._text(W - pad, H - 13, "dbl-click refresh  ·  right-click quit",
                   color=C["dim"], size=7, anchor="e")

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

    w = UsageWidget()
    w._show_event = _show_event
    w.run()


if __name__ == "__main__":
    main()
