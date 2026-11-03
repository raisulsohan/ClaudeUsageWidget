"""
app.py — one-process entry point for the .exe build (ClaudeUsageWidget.exe).

Does what "Start Widget.cmd" does, in a single windowless program:
  1. runs receiver.py's HTTP server on 127.0.0.1:8765 in a background thread
     (skipped when something already listens there), and
  2. shows widget.py's window. Quit (in the widget's panel) ends both.

Build:  build_installer.bat  (makes installer/ClaudeUsageWidget-Setup.exe)
"""

import threading

import receiver
import widget


def start_receiver():
    try:
        httpd = receiver.Server((receiver.HOST, receiver.PORT), receiver.Handler)
    except OSError:
        return  # port in use: another receiver is already running
    threading.Thread(target=httpd.serve_forever, daemon=True).start()


if __name__ == "__main__":
    start_receiver()
    widget.main()
