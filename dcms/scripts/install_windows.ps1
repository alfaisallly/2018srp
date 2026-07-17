#Requires -RunAsAdministrator
# Quick install — delegates to install_windows_server.ps1
& "$PSScriptRoot\install_windows_server.ps1" -InstallPath (Split-Path -Parent $PSScriptRoot) -OpenFirewall -RegisterService
