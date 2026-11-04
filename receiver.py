#!/usr/bin/env python3
"""
receiver.py — local endpoint for the Chrome extension.

The extension (see extension/) fetches claude.ai usage from inside Chrome and
POSTs the raw JSON here. We reuse fetch_usage.parse() so the widget schema is
defined in exactly one place, then write usage_data.json for the widget.

No browser cookies are touched; this is the Chrome-friendly path. Run it in the
background (start_receiver.bat, or install_task.ps1 -Receiver) while Chrome and
the widget are open.

Usage:  python receiver.py  [--port 8765]
"""

import json
import socket
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import fetch_usage
import usage_history

# next to the .exe when built with PyInstaller, else next to this script
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_FILE = APP_DIR / "usage_data.json"
RAW_FILE = APP_DIR / "usage_raw.json"   # last raw API payload, for debugging the parser
HOST = "127.0.0.1"
PORT = 8765

# set by the widget's Refresh button; the extension polls /pending and fetches
REFRESH = threading.Event()


class Server(HTTPServer):
    """Takes the port for itself. With the default SO_REUSEADDR, Windows lets a
    second server (any other project's dev server) bind 8765 too and quietly take
    the extension's pushes."""
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj):
        self.send_response(200); self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip("/") == "/pending":
            self._json({"refresh": REFRESH.is_set()})
        else:
            self.send_response(404); self._cors(); self.end_headers()

    def do_POST(self):
        if self.path.rstrip("/") == "/refresh":
            REFRESH.set()
            self._json({"ok": True})
            return
        if self.path.rstrip("/") != "/data":
            self.send_response(404); self._cors(); self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            RAW_FILE.write_text(json.dumps(body.get("usage") or {}, indent=2), encoding="utf-8")
            data = fetch_usage.parse(body.get("usage") or {}, body.get("org") or {})
            DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            usage_history.record(data)      # the "by day" chart, also while the widget is closed
            REFRESH.clear()
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] weekly={data['weekly']['percent']}%  "
                  f"fable={data['fable']['percent']}%  "
                  f"extra=${data['extra']['spent']:.2f}")
            self.send_response(200); self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            print(f"  error handling push: {e}")
            self.send_response(500); self._cors(); self.end_headers()

    def log_message(self, *args):
        pass  # silence the default per-request logging; we print our own line


def main():
    port = PORT
    if "--port" in sys.argv:
        i = sys.argv.index("--port")
        if i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    try:
        httpd = Server((HOST, port), Handler)
    except OSError as e:
        print(f"Port {port} is already in use ({e}). Is another receiver, or another app, running?")
        sys.exit(1)
    print(f"Receiver listening on http://{HOST}:{port}/data  (Ctrl-C to stop)")
    print("Load the Chrome extension and keep this running. It writes usage_data.json.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
