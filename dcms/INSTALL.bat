@echo off
chcp 65001 >nul
title DCMS - Windows Server Installer
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  DCMS - Windows Server Installer         ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  Run as Administrator!
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_windows_server.ps1" -InstallPath "%~dp0." -OpenFirewall
echo.
pause
