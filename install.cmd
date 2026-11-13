@echo off
goto :VERIFY_EXECUTION
:VERIFY_EXECUTION_FAILED
echo.
echo =================================================================
echo [ERROR] This script cannot be run by piping into cmd.
echo Piping breaks delayed expansion and causes variables to corrupt.
echo =================================================================
echo.
echo Please use the following PowerShell command to install correctly:
echo.
echo irm https://raw.githubusercontent.com/sh4lu-z/Syntiox-CORE/master/install.cmd -OutFile install.cmd ; .\install.cmd
echo.
exit /b 1

:VERIFY_EXECUTION
setlocal ENABLEDELAYEDEXPANSION
title Syntiox CORE Installer

echo =================================================================
echo                 Syntiox CORE Installer
echo =================================================================
echo.

:: Define Paths (Local AppData for binaries/runtimes, User Profile for data/scratch)
set "TARGET_DIR=%LOCALAPPDATA%\.sh4lu-z\Syntiox CORE"
set "BIN_DIR=%LOCALAPPDATA%\.sh4lu-z\bin"
set "DATA_DIR=%USERPROFILE%\.sh4lu-z\Syntiox CORE"
set "CONFIG_DIR=%DATA_DIR%\config"
set "HISTORY_DIR=%DATA_DIR%\history"
set "SCRATCH_DIR=%DATA_DIR%\scratch"
set "SKILLS_DIR=%DATA_DIR%\skills"
set "BROWSER_PROFILE_DIR=%DATA_DIR%\browser_profile"

echo [1/5] Creating directories...
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
if not exist "%CONFIG_DIR%\local" mkdir "%CONFIG_DIR%\local"
if not exist "%CONFIG_DIR%\examples" mkdir "%CONFIG_DIR%\examples"
if not exist "%CONFIG_DIR%\prompts" mkdir "%CONFIG_DIR%\prompts"
if not exist "%HISTORY_DIR%" mkdir "%HISTORY_DIR%"
if not exist "%SCRATCH_DIR%" mkdir "%SCRATCH_DIR%"
if not exist "%SKILLS_DIR%" mkdir "%SKILLS_DIR%"
if not exist "%BROWSER_PROFILE_DIR%" mkdir "%BROWSER_PROFILE_DIR%"
attrib +h "%LOCALAPPDATA%\.sh4lu-z" 2>nul
attrib +h "%USERPROFILE%\.sh4lu-z" 2>nul

echo [2/5] Downloading Syntiox CORE...
curl -L -o "%TARGET_DIR%\Syntiox-CORE.zip" https://github.com/sh4lu-z/Syntiox-CORE/archive/refs/heads/master.zip
if exist "%TARGET_DIR%\Syntiox-CORE.zip" (
    tar -xf "%TARGET_DIR%\Syntiox-CORE.zip" -C "%TARGET_DIR%"
    
    echo Cleaning up old source files...
    if exist "%TARGET_DIR%\src" rmdir /S /Q "%TARGET_DIR%\src"
    if exist "%TARGET_DIR%\prompts" rmdir /S /Q "%TARGET_DIR%\prompts"
    if exist "%TARGET_DIR%\docs" rmdir /S /Q "%TARGET_DIR%\docs"
    if exist "%TARGET_DIR%\config" rmdir /S /Q "%TARGET_DIR%\config"
    if exist "%TARGET_DIR%\backend" rmdir /S /Q "%TARGET_DIR%\backend"
    if exist "%TARGET_DIR%\TOOLS" rmdir /S /Q "%TARGET_DIR%\TOOLS"
    if exist "%TARGET_DIR%\MCP" rmdir /S /Q "%TARGET_DIR%\MCP"
    if exist "%TARGET_DIR%\SKILLS" rmdir /S /Q "%TARGET_DIR%\SKILLS"
    if exist "%TARGET_DIR%\scripts" rmdir /S /Q "%TARGET_DIR%\scripts"
    if exist "%TARGET_DIR%\frontend" rmdir /S /Q "%TARGET_DIR%\frontend"
    if exist "%TARGET_DIR%\test" rmdir /S /Q "%TARGET_DIR%\test"
    del /q "%TARGET_DIR%\*.py" 2>nul
    
    xcopy /Y /E "%TARGET_DIR%\Syntiox-CORE-master\*" "%TARGET_DIR%\" >nul
    rmdir /S /Q "%TARGET_DIR%\Syntiox-CORE-master"
    del /q "%TARGET_DIR%\Syntiox-CORE.zip"
) else (
    echo [ERROR] Download failed. Please check your internet connection.
    pause
    exit /b 1
)

:: Copy config defaults (only new files, don't overwrite user's existing config)
if exist "%TARGET_DIR%\config\examples" (
    xcopy /Y /E /D "%TARGET_DIR%\config\examples\*" "%CONFIG_DIR%\examples\" >nul 2>nul
)
if not exist "%CONFIG_DIR%\prompts\SYNTIOX_CORE.md" (
    if exist "%TARGET_DIR%\config\prompts\SYNTIOX_CORE.md" copy /Y "%TARGET_DIR%\config\prompts\SYNTIOX_CORE.md" "%CONFIG_DIR%\prompts\SYNTIOX_CORE.md" >nul 2>nul
)
if exist "%TARGET_DIR%\src\syntiox_core\skills" (
    xcopy /Y /E /D "%TARGET_DIR%\src\syntiox_core\skills\*" "%SKILLS_DIR%\" >nul
)
if not exist "%CONFIG_DIR%\local\.env" (
    if exist "%CONFIG_DIR%\examples\.env.example" (
        copy /Y "%CONFIG_DIR%\examples\.env.example" "%CONFIG_DIR%\local\.env" >nul
    ) else (
        echo. > "%CONFIG_DIR%\local\.env"
    )
)
if not exist "%CONFIG_DIR%\local\mcp_permissions.json" (
    if exist "%CONFIG_DIR%\examples\mcp_permissions.json" (
        copy /Y "%CONFIG_DIR%\examples\mcp_permissions.json" "%CONFIG_DIR%\local\mcp_permissions.json" >nul
    )
)

echo [3/5] Setting up Virtual Environment...
if exist "%TARGET_DIR%\venv\Scripts\python.exe" (
    "%TARGET_DIR%\venv\Scripts\python.exe" -m pip --version >nul 2>nul
    if errorlevel 1 (
        echo Existing virtual environment is broken, recreating...
        rmdir /S /Q "%TARGET_DIR%\venv"
    )
)
if not exist "%TARGET_DIR%\venv\Scripts\python.exe" (
    python -m venv "%TARGET_DIR%\venv" 2>nul
    if not exist "%TARGET_DIR%\venv\Scripts\python.exe" (
        py -m venv "%TARGET_DIR%\venv" 2>nul
    )
)
if not exist "%TARGET_DIR%\venv\Scripts\python.exe" (
    echo [ERROR] Failed to create virtual environment. Please ensure Python is installed and on PATH.
    pause
    exit /b 1
)

echo [4/5] Installing Core Requirements...
"%TARGET_DIR%\venv\Scripts\python.exe" -m pip install -r "%TARGET_DIR%\requirements.txt"

echo.
echo [5/5] Setting up 'stx' commands...
echo @echo off > "%BIN_DIR%\stx.cmd"
echo if "%%~1"=="--update" ( >> "%BIN_DIR%\stx.cmd"
echo     powershell -NoProfile -Command "irm https://raw.githubusercontent.com/sh4lu-z/Syntiox-CORE/master/install.cmd -OutFile install.cmd ; .\install.cmd" >> "%BIN_DIR%\stx.cmd"
echo     exit /b >> "%BIN_DIR%\stx.cmd"
echo ) >> "%BIN_DIR%\stx.cmd"
echo set "SYNTIOX_DATA_DIR=%DATA_DIR%" >> "%BIN_DIR%\stx.cmd"
echo cd /d "%TARGET_DIR%" >> "%BIN_DIR%\stx.cmd"
echo call venv\Scripts\activate >> "%BIN_DIR%\stx.cmd"
echo python src\syntiox_core\server.py %%* >> "%BIN_DIR%\stx.cmd"

echo @echo off > "%BIN_DIR%\stx-google-login.cmd"
echo set "SYNTIOX_DATA_DIR=%DATA_DIR%" >> "%BIN_DIR%\stx-google-login.cmd"
echo cd /d "%TARGET_DIR%" >> "%BIN_DIR%\stx-google-login.cmd"
echo call venv\Scripts\activate >> "%BIN_DIR%\stx-google-login.cmd"
echo if exist "%%SYNTIOX_DATA_DIR%%\config\local\token.json" del /q "%%SYNTIOX_DATA_DIR%%\config\local\token.json" >> "%BIN_DIR%\stx-google-login.cmd"
echo python src\syntiox_core\mcp_servers\google\auth_setup.py >> "%BIN_DIR%\stx-google-login.cmd"

:: Add BIN_DIR to PATH if not already there safely (avoids 1024 char limit of setx)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$b = '%BIN_DIR%'; $p = [Environment]::GetEnvironmentVariable('PATH', 'User'); if ($p -notlike ('*' + $b + '*')) { [Environment]::SetEnvironmentVariable('PATH', ($p.TrimEnd(';') + ';' + $b).TrimStart(';'), 'User'); Write-Host 'Added %BIN_DIR% to User PATH.'; Write-Host 'Notice: You may need to restart your terminal for ''stx'' command to work globally.' }"

echo.
echo =================================================================
echo Syntiox CORE installed successfully!
echo You can now use 'stx' from anywhere in your terminal.
echo Data, history, and scratch files are saved in: %DATA_DIR%
echo =================================================================
pause
