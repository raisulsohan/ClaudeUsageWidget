#!/usr/bin/env python3
"""
set_usage.py — manually set usage values for the widget (handy for testing the UI).

Usage:  python set_usage.py
"""
import json
from datetime import datetime
import sys
from pathlib import Path

# next to the .exe when built with PyInstaller, else next to this script
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_FILE = APP_DIR / "usage_data.json"

def ask(prompt, default=None, cast=int):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"  {prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return cast(raw)
        except ValueError:
            print(f"  -> enter a valid {cast.__name__}")

def ask_str(prompt, default="—"):
    suffix = f" [{default}]" if default else ""
    raw = input(f"  {prompt}{suffix}: ").strip()
    return raw or default

print()
print("+---------------------------------------------------+")
print("|  Claude Code Usage Widget - manual data entry     |")
print("+---------------------------------------------------+")
print()

try:
    existing = json.load(open(DATA_FILE, encoding="utf-8"))
except Exception:
    existing = {}

s = existing.get("session", {})
w = existing.get("weekly", {})
f = existing.get("fable", {})
e = existing.get("extra", {})

print("SESSION")
sess_pct    = ask("percent used (0-100)",  s.get("percent", 0))
sess_resets = ask_str("resets in",         s.get("resets_in", "3h 55m"))

print()
print("WEEKLY")
week_pct    = ask("percent used (0-100)",  w.get("percent", 0))
week_resets = ask_str("resets in",         w.get("resets_in", "13h 55m"))

print()
print("FABLE (weekly)")
fable_pct    = ask("percent used (0-100)", f.get("percent", 0))
fable_resets = ask_str("resets in",        f.get("resets_in", "—"))

print()
print("EXTRA USAGE")
extra_en    = ask_str("enabled? (y/n)",    "y" if e.get("enabled") else "n")
extra_spent = ask("$ spent (e.g. 4)",      int(e.get("spent", 0)), cast=float)
extra_pct   = ask("percent used (0-100)",  e.get("percent", 0))
extra_limit = ask("monthly limit $",       int(e.get("limit", 20)), cast=float)
extra_reset = ask_str("resets date",       e.get("resets", "1st of month"))

print()
plan = ask_str("Plan (Pro/Max/etc.)", existing.get("plan", "Pro"))

data = {
    "plan": plan,
    "session": {"percent": sess_pct,  "resets_in": sess_resets},
    "weekly":  {"percent": week_pct,  "resets_in": week_resets},
    "fable":   {"percent": fable_pct, "resets_in": fable_resets, "available": True},
    "extra": {
        "enabled": extra_en.lower().startswith("y"),
        "spent":   extra_spent,
        "percent": extra_pct,
        "limit":   extra_limit,
        "resets":  extra_reset,
    },
    "updated": datetime.now().isoformat(),
}

with open(DATA_FILE, "w", encoding="utf-8") as fp:
    json.dump(data, fp, indent=2)

print(f"OK - saved to {DATA_FILE}")
