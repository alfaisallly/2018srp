#Requires -RunAsAdministrator
<#
.SYNOPSIS
    DCMS - Data Center Management System installer for Windows 11
.DESCRIPTION
    Installs Python dependencies, PostgreSQL/Redis via Docker, and configures DCMS
#>

$ErrorActionPreference = "Stop"
$DCMSRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=== DCMS Installer for Windows 11 ===" -ForegroundColor Cyan
Write-Host "Install directory: $DCMSRoot"

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python not found. Install Python 3.11+ from https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
Write-Host "Python: $(python --version)"

# Create virtual environment
Set-Location $DCMSRoot
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "Created virtual environment"
}
& ".\venv\Scripts\Activate.ps1"

pip install --upgrade pip
pip install -r requirements.txt
Write-Host "Python dependencies installed" -ForegroundColor Green

# Copy env file
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — edit SECRET_KEY before production"
}

# Docker for PostgreSQL + Redis
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    docker compose up -d
    Write-Host "PostgreSQL and Redis started via Docker" -ForegroundColor Green
    Start-Sleep -Seconds 5
} else {
    Write-Host "Docker not found. Install Docker Desktop for Windows:" -ForegroundColor Yellow
    Write-Host "  https://docs.docker.com/desktop/install/windows-install/"
    Write-Host "Or install PostgreSQL and Redis manually and update .env"
}

# Initialize database
python scripts/init_db.py
Write-Host "Database initialized with admin/admin123" -ForegroundColor Green

# Register Windows Service (optional, using NSSM if available)
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if ($nssm) {
    nssm install DCMS "$DCMSRoot\venv\Scripts\uvicorn.exe" "app.main:app --host 0.0.0.0 --port 8080"
    nssm set DCMS AppDirectory $DCMSRoot
    nssm start DCMS
    Write-Host "DCMS registered as Windows service" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "To start DCMS manually:" -ForegroundColor Cyan
    Write-Host "  cd $DCMSRoot"
    Write-Host "  .\venv\Scripts\Activate.ps1"
    Write-Host "  uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"
}

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Green
Write-Host "Open http://localhost:8080 in your browser"
Write-Host "Default login: admin / admin123"
Write-Host "API docs: http://localhost:8080/docs"
