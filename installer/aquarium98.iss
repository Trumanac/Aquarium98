; Aquarium 98 — Inno Setup installer script
; https://jrsoftware.org/isinfo.php  (free)
;
; Build requirements:
;   1. PyInstaller output in  dist\Aquarium98\  (run: pyinstaller aquarium98.spec)
;   2. Inno Setup 6.x  (download from jrsoftware.org)
;
; Compile:
;   iscc installer\aquarium98.iss
;
; Output:
;   installer\Output\Aquarium98-Setup-1.0.0.exe
;
; NO administrator rights required — installs per-user into %LocalAppData%.
; Uninstaller is registered automatically.

#define MyAppName      "Aquarium 98"
#define MyAppVersion   "1.0.15"
#define MyAppPublisher "Truman AC"
#define MyAppURL       "https://github.com/trumanac/aquarium98"
#define MyAppExeName   "Aquarium98.exe"
#define MyBuildDir     "..\dist\Aquarium98"

[Setup]
AppId={{A3F7B2C1-4E8D-4F1A-9B3C-D2E5F6A7B8C9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Per-user install — no UAC prompt, no admin required
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=

; Install to %LocalAppData%\Aquarium98 (user-writable, survives Windows updates)
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Don't ask users to close running instances — the app handles its own lock
CloseApplications=no

; Uninstall info
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; Installer appearance
WizardStyle=modern
WizardSmallImageFile=..\assets\icon\SplashScreen.png
SetupIconFile=..\assets\icon\icon.ico

; Output
OutputDir=Output
OutputBaseFilename=Aquarium98-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; x64 only — pygame-ce doesn't ship 32-bit Windows wheels
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Code-signing: set SIGNTOOL_PARAMS in the environment or comment out if unsigned
; SignTool=MsSign $f
; SignedUninstaller=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}";    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startuplaunch";  Description: "Launch {#MyAppName} when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Copy the entire PyInstaller onedir output
Source: "{#MyBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

; Desktop (optional, off by default)
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; "Open on Startup" toggle — mirrors what the app writes itself.
; Only write this key if the user ticked the startup task; the app can
; also manage this key independently via Settings → Open on Startup.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "Aquarium98"; \
  ValueData: """{app}\{#MyAppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startuplaunch

[Run]
; Launch after install.
; postinstall  → shows as a ticked checkbox on the wizard's final page (interactive).
; nowait       → don't block the installer waiting for the app to exit.
; Omitting skipifsilent means this entry also fires during /SILENT auto-updates.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: nowait postinstall

[UninstallRun]
; Kill any running instance before uninstalling (best-effort)
Filename: "taskkill"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillAquarium98"

[UninstallDelete]
; Clean up the user's lock file
Type: files; Name: "{userdocs}\Aquarium98\*.lock"
