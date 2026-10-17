@echo off
REM start.bat - run the usage fetcher in the background without Task Scheduler.
REM (If you installed the scheduled task with install_task.ps1, you don't need this.)
REM Uses pythonw so no console window stays open; progress is written to fetch.log.

cd /d "%~dp0"
start "" /b pythonw "%~dp0fetch_usage.py" --loop
echo Fetcher started in the background. Progress is logged to fetch.log
echo Then show the widget with:  python widget.py
