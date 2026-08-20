@echo off
title Syntiox CORE System Launcher
chcp 65001 > nul
cls
echo ========================================
echo        Syntiox CORE Launcher      
echo ========================================
echo.
echo Starting Terminal CLI...
echo.
set LAUNCH_UI=terminal
python server.py
pause
