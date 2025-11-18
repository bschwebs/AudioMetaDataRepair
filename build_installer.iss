; Inno Setup Script for Audio Metadata Repair Tool
; Compile this script with Inno Setup Compiler to create an installer

[Setup]
AppName=Audio Metadata Repair Tool
AppVersion=2.0.0
AppPublisher=Your Name
AppPublisherURL=https://github.com/bschwebs/AudioMetaDataRepair
AppSupportURL=https://github.com/bschwebs/AudioMetaDataRepair/issues
AppUpdatesURL=https://github.com/bschwebs/AudioMetaDataRepair/releases
DefaultDirName={autopf}\AudioMetadataRepair
DefaultGroupName=Audio Metadata Repair Tool
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=installer
OutputBaseFilename=AudioMetadataRepair-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
Source: "dist\AudioMetadataRepair.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "README_DESKTOP.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Audio Metadata Repair Tool"; Filename: "{app}\AudioMetadataRepair.exe"
Name: "{group}\{cm:UninstallProgram,Audio Metadata Repair Tool}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Audio Metadata Repair Tool"; Filename: "{app}\AudioMetadataRepair.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\Audio Metadata Repair Tool"; Filename: "{app}\AudioMetadataRepair.exe"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\AudioMetadataRepair.exe"; Description: "{cm:LaunchProgram,Audio Metadata Repair Tool}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Check if Python is installed (optional - for informational purposes)
  // The executable should be standalone, but we can add checks here if needed
end;

