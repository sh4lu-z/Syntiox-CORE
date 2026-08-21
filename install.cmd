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
echo irm https://raw.githubusercontent.com/sh4lu-z/Syntiox-CORE/main/install.cmd -OutFile install.cmd ; .\install.cmd
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
set "DATA_DIR=%USERPROFILE%\.sh4lu-z\Syntiox CORE"
set "CONFIG_DIR=%DATA_DIR%\config"
set "HISTORY_DIR=%DATA_DIR%\history"
set "WORKSPACE_DIR=%DATA_DIR%\workspace"

echo [1/6] Creating directories...
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
if not exist "%HISTORY_DIR%" mkdir "%HISTORY_DIR%"
if not exist "%WORKSPACE_DIR%" mkdir "%WORKSPACE_DIR%"
attrib +h "%APPDATA%\.sh4lu-z" 2>nul
attrib +h "%USERPROFILE%\.sh4lu-z" 2>nul

cd /d "%TARGET_DIR%"

echo [2/6] Downloading Syntiox CORE...
curl -L -o Syntiox-CORE.zip https://github.com/sh4lu-z/Syntiox-CORE/archive/refs/heads/main.zip
if exist Syntiox-CORE.zip (
    tar -xf Syntiox-CORE.zip
    xcopy /Y /E Syntiox-CORE-main\* .
    rmdir /S /Q Syntiox-CORE-main
    del Syntiox-CORE.zip
) else (
    echo [ERROR] Download failed. Please check your internet connection.
    pause
    exit /b 1
)

:: Ensure config exists in DATA_DIR (Preserve existing config)
if not exist "%CONFIG_DIR%\.env" (
    if exist "config\.env.example" (
        copy /Y "config\.env.example" "%CONFIG_DIR%\.env"
    ) else if exist "config\.env" (
        copy /Y "config\.env" "%CONFIG_DIR%\.env"
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

echo [6/6] Setting up 'stx' command...
echo @echo off > stx.cmd
echo set "SYNTIOX_DATA_DIR=%DATA_DIR%" >> stx.cmd
echo cd /d "%%~dp0" >> stx.cmd
echo call venv\Scripts\activate >> stx.cmd
echo python server.py %%* >> stx.cmd

:: Add TARGET_DIR to PATH if not already there
set "PATH_CHECK=%PATH%"
echo !PATH_CHECK! | find /I "%TARGET_DIR%" >nul
if errorlevel 1 (
    echo Adding %TARGET_DIR% to User PATH...
    for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%B"
    if defined USER_PATH (
        setx PATH "!USER_PATH!;%TARGET_DIR%" >nul
    ) else (
        setx PATH "%TARGET_DIR%" >nul
    )
    echo Notice: You may need to restart your terminal for 'stx' command to work globally.
)

echo.
echo =================================================================
echo Syntiox CORE installed successfully!
echo You can now use 'stx' from anywhere in your terminal.
echo Data, history, and workspaces are saved in: %DATA_DIR%
echo =================================================================
pause
