[Setup]
AppName=ESP32 Virtual Gamepad
AppVersion=2.1
DefaultDirName={autopf}\ESP32 Virtual Gamepad
DefaultGroupName=ESP32 Virtual Gamepad
OutputDir=D:\gamepad\Installer
OutputBaseFilename=ESP32_Gamepad_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Files]
Source: "D:\gamepad\dist\pc_gamepad\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ESP32 Virtual Gamepad"; Filename: "{app}\pc_gamepad.exe"
Name: "{autodesktop}\ESP32 Virtual Gamepad"; Filename: "{app}\pc_gamepad.exe"; Tasks: desktopicon
Name: "{userstartup}\ESP32 Virtual Gamepad"; Filename: "{app}\pc_gamepad.exe"; Parameters: "--minimized"; Tasks: startupicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Run automatically when Windows starts"; GroupDescription: "Auto-start";

[Run]
Filename: "{app}\pc_gamepad.exe"; Description: "Launch Virtual Gamepad now"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM pc_gamepad.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
