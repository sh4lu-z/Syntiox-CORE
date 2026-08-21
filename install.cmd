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

echo [1/6] Creating directories...
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
if not exist "%HISTORY_DIR%" mkdir "%HISTORY_DIR%"
if not exist "%WORKSPACE_DIR%" mkdir "%WORKSPACE_DIR%"
if not exist "%SKILLS_DIR%" mkdir "%SKILLS_DIR%"
attrib +h "%APPDATA%\.sh4lu-z" 2>nul
attrib +h "%USERPROFILE%\.sh4lu-z" 2>nul

cd /d "%TARGET_DIR%"

echo [2/6] Downloading Syntiox CORE...
curl -L -o Syntiox-CORE.zip https://github.com/sh4lu-z/Syntiox-CORE/archive/refs/heads/master.zip
if exist Syntiox-CORE.zip (
    tar -xf Syntiox-CORE.zip
    xcopy /Y /E Syntiox-CORE-master\* .
    rmdir /S /Q Syntiox-CORE-master
    del Syntiox-CORE.zip
) else (
    echo [ERROR] Download failed. Please check your internet connection.
    pause
    exit /b 1
)

:: Copy config and default skills from repo to DATA_DIR (Preserve existing user modifications where possible)
xcopy /Y /E "config\*" "%CONFIG_DIR%\" >nul
if exist "SKILLS" (
    xcopy /Y /E /D "SKILLS\*" "%SKILLS_DIR%\" >nul
)
if not exist "%CONFIG_DIR%\.env" (
    if exist "%CONFIG_DIR%\.env.example" (
        copy /Y "%CONFIG_DIR%\.env.example" "%CONFIG_DIR%\.env" >nul
    ) else (
        echo. > "%CONFIG_DIR%\.env"
    )
)

echo [3/6] Setting up Virtual Environment...
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate

echo [4/6] Installing Core Requirements...
pip install -r requirements.txt
echo Installing Playwright browsers...
playwright install chromium

echo.
echo =================================================================
echo [5/6] Local LLM Setup
echo =================================================================
echo Syntiox CORE can run using Google's Cloud LLMs or Local LLMs.
echo Local LLMs require installing 'llama-cpp-python', which is large (~1.5GB).
echo.
set /p USE_LOCAL="Do you want to install support for Local LLMs? (Y/N): "
if /I "%USE_LOCAL%"=="Y" (
    echo Installing local LLM dependencies...
    pip install llama-cpp-python
) else (
    echo Skipping local LLM dependencies.
)

echo [6/6] Setting up 'stx' commands...
echo @echo off > "%BIN_DIR%\stx.cmd"
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
