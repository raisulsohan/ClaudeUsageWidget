@echo off
setlocal
cd /d "%~dp0"
title Claude Usage Widget

rem ---- find a windowless Python (pyw/pythonw: no console window stays open) ----
set "PYW="
if exist "%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe"
if not defined PYW if exist "%SystemRoot%\pyw.exe" set "PYW=%SystemRoot%\pyw.exe"
if not defined PYW for %%I in (pythonw.exe) do if not "%%~$PATH:I"=="" set "PYW=%%~$PATH:I"
if not defined PYW (
  echo Python was not found. Install it with:  winget install -e --id Python.Python.3.14
  pause
  exit /b 1
)

rem ---- 1. receiver.py (gets data from the Edge/Chrome extension) ----
rem      skipped when something already listens on 127.0.0.1:8765
netstat -ano | findstr /R /C:"127.0.0.1:8765 .*LISTENING" >nul
if errorlevel 1 (
  start "" "%PYW%" "%~dp0receiver.py"
  echo [1/2] Receiver started on 127.0.0.1:8765
) else (
  echo [1/2] Receiver already running
)

rem ---- 2. widget.py (the thing you see on screen) ----
rem      skipped when a widget window is already open
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%%widget.py%%' AND (Name='pythonw.exe' OR Name='python.exe')\") { exit 0 } else { exit 1 }"
if errorlevel 1 (
  start "" "%PYW%" "%~dp0widget.py"
  echo [2/2] Widget started
) else (
  echo [2/2] Widget already open
)

echo.
echo Done. Right-click the widget to close it; run "Stop Widget.cmd" to stop everything.
timeout /t 3 >nul
endlocal
