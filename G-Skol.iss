#define AppName "G-Skol"
#define AppVersion "6.1"

[Setup]
AppId={{D6B26DAA-A089-4A89-AD93-4F9AEAD02D89}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=G-Skol
DefaultDirName={autopf}\G-Skol
DefaultGroupName=G-Skol
PrivilegesRequired=admin
ChangesAssociations=yes
OutputDir=dist
OutputBaseFilename=G-Skol-Installation
SetupIconFile=assets\G-Skol.ico
UninstallDisplayIcon={app}\G-Skol.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Dirs]
; The user workspace remains after uninstallation and must be writable by ordinary users.
Name: "{sd}\G-Skol-Workspace"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{sd}\G-Skol-Workspace\Bibliothèques"; Flags: uninsneveruninstall

[Files]
Source: "dist\G-Skol-Portable\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "Workspace\*,G-Skol.portable"
; Only clean official library, never overwrite user-modified models.
Source: "dist\G-Skol-Portable\Workspace\Bibliothèques\*"; DestDir: "{sd}\G-Skol-Workspace\Bibliothèques"; Flags: onlyifdoesntexist uninsneveruninstall recursesubdirs createallsubdirs skipifsourcedoesntexist

[Registry]
Root: HKCU; Subkey: "Software\Classes\MM3.Collection"; ValueType: string; ValueData: "Collection G-Skol"
Root: HKCU; Subkey: "Software\Classes\MM3.Collection\DefaultIcon"; ValueType: string; ValueData: "{app}\G-Skol.exe,0"
Root: HKCU; Subkey: "Software\Classes\MM3.Collection\shell\open\command"; ValueType: string; ValueData: """{app}\G-Skol.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.coldb"; ValueType: string; ValueData: "MM3.Collection"

[Icons]
Name: "{autoprograms}\G-Skol"; Filename: "{app}\G-Skol.exe"
Name: "{autoprograms}\Workspace G-Skol"; Filename: "{sd}\G-Skol-Workspace"
Name: "{autodesktop}\G-Skol"; Filename: "{app}\G-Skol.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\G-Skol.exe"; Description: "Lancer G-Skol"; Flags: nowait postinstall skipifsilent
