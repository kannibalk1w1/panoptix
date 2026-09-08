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
; Panoptix.exe is a 64-bit binary. Without these it installs under
; Program Files (x86) on 64-bit Windows, and on 32-bit Windows it would install
; an executable that cannot run at all, leaving a shortcut to a dead target.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Panoptix sits in the tray, so a reinstall would otherwise hit a locked
; Panoptix.exe and leave the installed copy missing or half replaced.
CloseApplications=yes
RestartApplications=no
; Installs per user by default so testers without admin rights can run it,
; while still offering an all-users install when the tester is an admin.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts"

[Files]
; Only the executable is installed. The README and the manual test checklist are
; development files, are never read at runtime, and shipping loose Markdown into
; Program Files gave testers spurious antivirus and unwanted-file warnings.
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Start Panoptix now"; Flags: nowait postinstall skipifsilent

; Startup at login is owned by the in-app setting (Settings -> Open Panoptix with
; Windows startup), so the installer deliberately does not add a startup entry.
; Uninstalling removes that entry but never touches captured evidence, which
; lives in the configured screenshot folder or %LOCALAPPDATA%\Panoptix\data.
[UninstallDelete]
Type: files; Name: "{userstartup}\Panoptix.cmd"
