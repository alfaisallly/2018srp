#Requires -Version 5.1
<#
.SYNOPSIS
    Build DCMS Windows release ZIP package
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Version = (Get-Content "$Root\VERSION" -Raw).Trim()
$Name = "dcms-$Version-windows"
$OutDir = Join-Path $Root "dist"
$ZipPath = Join-Path $OutDir "$Name.zip"

Write-Host "Building Windows release $Name..."

$Stage = Join-Path $env:TEMP $Name
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage | Out-Null

$exclude = @('venv', '__pycache__', '.pytest_cache', '.env', 'dist', '.git')
Get-ChildItem $Root -Force | Where-Object { $_.Name -notin $exclude } | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $Stage $_.Name) -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "$Stage\*" -DestinationPath $ZipPath -Force
Remove-Item $Stage -Recurse -Force

$hash = (Get-FileHash $ZipPath -Algorithm SHA256).Hash
Set-Content "$ZipPath.sha256" "$hash  $(Split-Path $ZipPath -Leaf)"
$size = [math]::Round((Get-Item $ZipPath).Length / 1KB, 1)

Write-Host ""
Write-Host "Release built: $ZipPath ($size KB)" -ForegroundColor Green
Write-Host "SHA256: $hash"
Write-Host ""
Write-Host "Install on Windows Server:"
Write-Host "  1. Expand-Archive $Name.zip -DestinationPath C:\DCMS"
Write-Host "  2. cd C:\DCMS"
Write-Host "  3. .\scripts\install_windows_server.ps1"
