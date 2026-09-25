[Setup]
AppName=Syntiox CORE
AppVersion=1.0.0
DefaultDirName={autopf}\Syntiox CORE
DefaultGroupName=Syntiox CORE
OutputDir=Output
OutputBaseFilename=SyntioxSetup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
LicenseFile=LICENSE.txt

[Files]
; The tiny exe built from GitHub Actions
Source: "dist\Syntiox_CORE.exe"; DestDir: "{app}"; Flags: ignoreversion
; Include requirements for the post-install step
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Syntiox CORE"; Filename: "{app}\Syntiox_CORE.exe"
Name: "{autodesktop}\Syntiox CORE"; Filename: "{app}\Syntiox_CORE.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"
Name: "localllm"; Description: "Install Local LLM Support (~1.5GB Download)"; GroupDescription: "Advanced Features:"; Flags: unchecked

[Run]
; 1. Create environment and install base requirements
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -Command ""& {{ $envDir = \""{localappdata}\Syntiox_CORE\env\""; if (-not (Test-Path $envDir)) {{ Write-Host 'Creating Environment...'; python -m venv $envDir; & \""$envDir\Scripts\pip.exe\"" install -r \""{app}\requirements.txt\"" }} }}"""; Flags: runhidden waituntilterminated
; 2. Install llama-cpp-python ONLY if the user checked the 'localllm' task
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -Command ""& {{ $envDir = \""{localappdata}\Syntiox_CORE\env\""; & \""$envDir\Scripts\pip.exe\"" install llama-cpp-python }}"""; Tasks: localllm; Flags: runhidden waituntilterminated
; 3. Finally launch the app
Filename: "{app}\Syntiox_CORE.exe"; Description: "Launch Syntiox CORE"; Flags: nowait postinstall skipifsilent
