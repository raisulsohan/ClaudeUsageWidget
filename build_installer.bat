@echo off
REM build_installer.bat - build the Windows installer:
REM   installer\ClaudeUsageWidget-Setup.exe
REM
REM Needs Python 3.10+ and Inno Setup 6 (winget install -e --id JRSoftware.InnoSetup).
REM Steps: PyInstaller bundles app.py (receiver + widget) into build\dist\ClaudeUsageWidget\,
REM then Inno Setup packs that folder and the Chrome extension into one setup file.

setlocal
cd /d "%~dp0"

set "ISCC="
for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
if not defined ISCC (
  echo Inno Setup 6 was not found. Install it with:  winget install -e --id JRSoftware.InnoSetup
  goto :fail
)

echo [1/3] Installing build tools...
python -m pip install --quiet --upgrade pyinstaller pillow -r requirements.txt || goto :fail

echo [2/3] Building the app with PyInstaller...
if not exist build mkdir build
python -c "from PIL import Image; Image.open('extension/icons/icon512.png').save('build/app.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])" || goto :fail
python -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name ClaudeUsageWidget --icon "%~dp0build\app.ico" ^
  --distpath build\dist --workpath build\work --specpath build ^
  app.py || goto :fail

echo [3/3] Building the installer with Inno Setup...
"%ISCC%" /Q installer.iss || goto :fail

echo.
echo Done: "%~dp0installer\ClaudeUsageWidget-Setup.exe"
exit /b 0

:fail
echo Build failed.
pause
exit /b 1
