; Inno Setup script for the Panoptix Windows installer.
; Build with: ISCC.exe /DAppVersion=0.1.0 installer\panoptix.iss
; scripts\build_windows.ps1 runs this automatically when Inno Setup is installed.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "Panoptix"
#define AppExeName "Panoptix.exe"

[Setup]
AppId={{BEAA8ABF-4B22-4DF6-9F36-BEFDB2070182}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Panoptix
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Panoptix-Setup-{#AppVersion}
SetupIconFile=..\assets\panoptix.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Installs per user by default so testers without admin rights can run it,
; while still offering an all-users install when the tester is an admin.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts"

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\MANUAL_TEST_CHECKLIST.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Start Panoptix now"; Flags: nowait postinstall skipifsilent

; Startup at login is owned by the in-app setting (Settings -> Open Panoptix with
; Windows startup), so the installer deliberately does not add a startup entry.
; Uninstalling removes that entry but never touches captured evidence, which
; lives in the configured screenshot folder or %LOCALAPPDATA%\Panoptix\data.
[UninstallDelete]
Type: files; Name: "{userstartup}\Panoptix.cmd"
