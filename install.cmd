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

:: Define Paths
set "TARGET_DIR=%APPDATA%\.sh4lu-z\Syntiox CORE"
set "BIN_DIR=%APPDATA%\.sh4lu-z\bin"
set "DATA_DIR=%USERPROFILE%\.sh4lu-z\Syntiox CORE"
set "CONFIG_DIR=%DATA_DIR%\config"
set "HISTORY_DIR=%DATA_DIR%\history"
set "WORKSPACE_DIR=%DATA_DIR%\workspace"
set "SKILLS_DIR=%DATA_DIR%\SKILLS"

echo [1/5] Creating directories...
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
if not exist "%HISTORY_DIR%" mkdir "%HISTORY_DIR%"
if not exist "%WORKSPACE_DIR%" mkdir "%WORKSPACE_DIR%"
if not exist "%SKILLS_DIR%" mkdir "%SKILLS_DIR%"
attrib +h "%APPDATA%\.sh4lu-z" 2>nul
attrib +h "%USERPROFILE%\.sh4lu-z" 2>nul

echo [2/5] Downloading Syntiox CORE...
curl -L -o "%TARGET_DIR%\Syntiox-CORE.zip" https://github.com/sh4lu-z/Syntiox-CORE/archive/refs/heads/master.zip
if exist "%TARGET_DIR%\Syntiox-CORE.zip" (
    tar -xf "%TARGET_DIR%\Syntiox-CORE.zip" -C "%TARGET_DIR%"
    xcopy /Y /E "%TARGET_DIR%\Syntiox-CORE-master\*" "%TARGET_DIR%\" >nul
    rmdir /S /Q "%TARGET_DIR%\Syntiox-CORE-master"
    del /q "%TARGET_DIR%\Syntiox-CORE.zip"
) else (
    echo [ERROR] Download failed. Please check your internet connection.
    pause
    exit /b 1
)

:: Copy config defaults (only new files, don't overwrite user's existing config)
if exist "%TARGET_DIR%\config\.env.example" copy /Y "%TARGET_DIR%\config\.env.example" "%CONFIG_DIR%\.env.example" >nul 2>nul
if exist "%TARGET_DIR%\config\credentials.example.json" copy /Y "%TARGET_DIR%\config\credentials.example.json" "%CONFIG_DIR%\credentials.example.json" >nul 2>nul
if exist "%TARGET_DIR%\config\token.example.json" copy /Y "%TARGET_DIR%\config\token.example.json" "%CONFIG_DIR%\token.example.json" >nul 2>nul
if exist "%TARGET_DIR%\SKILLS" (
    xcopy /Y /E /D "%TARGET_DIR%\SKILLS\*" "%SKILLS_DIR%\" >nul
)
if not exist "%CONFIG_DIR%\.env" (
    if exist "%CONFIG_DIR%\.env.example" (
        copy /Y "%CONFIG_DIR%\.env.example" "%CONFIG_DIR%\.env" >nul
    ) else (
        echo. > "%CONFIG_DIR%\.env"
    )
)

echo [3/5] Setting up Virtual Environment...
if not exist "%TARGET_DIR%\venv" (
    python -m venv "%TARGET_DIR%\venv"
)
if not exist "%TARGET_DIR%\venv\Scripts\python.exe" (
    echo [ERROR] Failed to create virtual environment. Please ensure Python is installed and on PATH.
    pause
    exit /b 1
)

echo [4/5] Installing Core Requirements...
"%TARGET_DIR%\venv\Scripts\pip.exe" install -r "%TARGET_DIR%\requirements.txt"
echo Installing Playwright browsers...
"%TARGET_DIR%\venv\Scripts\playwright.exe" install chromium

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
echo python server.py %%* >> "%BIN_DIR%\stx.cmd"

echo @echo off > "%BIN_DIR%\stx-google-login.cmd"
echo set "SYNTIOX_DATA_DIR=%DATA_DIR%" >> "%BIN_DIR%\stx-google-login.cmd"
echo cd /d "%TARGET_DIR%" >> "%BIN_DIR%\stx-google-login.cmd"
echo call venv\Scripts\activate >> "%BIN_DIR%\stx-google-login.cmd"
echo if exist "%%SYNTIOX_DATA_DIR%%\config\token.json" del /q "%%SYNTIOX_DATA_DIR%%\config\token.json" >> "%BIN_DIR%\stx-google-login.cmd"
echo python MCP\google\auth_setup.py >> "%BIN_DIR%\stx-google-login.cmd"

:: Add BIN_DIR to PATH if not already there safely (avoids 1024 char limit of setx)
set "PATH_CHECK=%PATH%"
echo !PATH_CHECK! | find /I "%BIN_DIR%" >nul
if errorlevel 1 (
    echo Adding %BIN_DIR% to User PATH...
    powershell -NoProfile -Command "$oldPath=[Environment]::GetEnvironmentVariable('PATH', 'User'); if ($oldPath -and $oldPath -notmatch '.*(;|^)$') { $oldPath += ';' }; [Environment]::SetEnvironmentVariable('PATH', $oldPath + '%BIN_DIR%', 'User')"
    echo Notice: You may need to restart your terminal for 'stx' command to work globally.
)

echo.
echo =================================================================
echo Syntiox CORE installed successfully!
echo You can now use 'stx' from anywhere in your terminal.
echo Data, history, and workspaces are saved in: %DATA_DIR%
echo =================================================================
pause
