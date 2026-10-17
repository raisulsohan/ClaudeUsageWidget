; installer.iss - Inno Setup 6 script for Claude Usage Widget.
; Build with build_installer.bat (it runs PyInstaller first, then this script).
; Installs per user (no admin prompt) to %LOCALAPPDATA%\Programs\Claude Usage Widget.

#define AppName "Claude Usage Widget"
#define AppVersion "1.0.0"
#define AppExe "ClaudeUsageWidget.exe"

[Setup]
AppId={{6C1F4E2A-9B7D-4C3E-A5F1-2D8B0E7C9A41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Raisul Sohan
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=ClaudeUsageWidget-Setup
SetupIconFile=build\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=LICENSE

[Tasks]
Name: "startup"; Description: "Start the widget when I sign in to Windows"; GroupDescription: "Options:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "build\dist\ClaudeUsageWidget\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "extension\*"; DestDir: "{app}\extension"; Excludes: "generate_icons.py"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Chrome extension folder"; Filename: "{app}\extension"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName} now"; Flags: nowait postinstall skipifsilent
Filename: "{app}\extension"; Description: "Open the Chrome extension folder (load it once in chrome://extensions)"; Flags: shellexec nowait postinstall skipifsilent unchecked

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopWidget"

[UninstallDelete]
Type: files; Name: "{app}\usage_data.json"
Type: files; Name: "{app}\fetch.log"

[Messages]
FinishedLabel=Setup has installed [name] on your computer.%n%nOne-time step: open chrome://extensions (or edge://extensions), turn on Developer mode, click "Load unpacked" and select the "extension" folder in the install folder. The Start Menu has a shortcut to it.%n%nDrag the widget to move it, double-click to refresh, right-click to quit.

[Code]
// Stop a running copy before files are replaced (upgrade / reinstall).
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM {#AppExe} /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
