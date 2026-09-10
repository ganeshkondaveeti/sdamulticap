; Inno Setup script — Windows `.exe` installer (v1.6 primary Windows artifact).
; See docs/implementation-plan.md §15. Consumes packaging/pyinstaller/dist/multicap/.
; Signed with signtool via CI (packaging/windows/signtool.env).

#define AppName "Multicap"
#define AppVersion "0.0.0"
#define AppPublisher "Multicap Contributors"
#define AppExeName "multicap.exe"

[Setup]
AppId={{5F5C1E4E-0000-0000-0000-000000000000}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputBaseFilename=multicap-{#AppVersion}-setup
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog

[Files]
Source: "..\pyinstaller\dist\multicap\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
