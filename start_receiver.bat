@echo off
REM start_receiver.bat - run the Chrome-extension receiver in the background.
REM Keep this running (with Chrome open and the extension loaded) and it will
REM write usage_data.json whenever the extension pushes usage.

cd /d "%~dp0"
start "" /b pythonw "%~dp0receiver.py"
echo Receiver started in the background on http://127.0.0.1:8765
echo Load the extension in Chrome, then show the widget with:  python widget.py
