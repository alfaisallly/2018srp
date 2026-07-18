#Requires -RunAsAdministrator
<#
.SYNOPSIS
    DCMS v1.1.0-enterprise — Windows Server 2019/2022 Production Installer
.DESCRIPTION
    Installs DCMS on Windows Server with Python venv, Docker (PostgreSQL+Redis),
    firewall rule, and optional Windows Service (NSSM).
.PARAMETER InstallPath
    Installation directory (default: C:\DCMS)
.PARAMETER Port
    HTTP port (default: 8080)
.PARAMETER SkipDocker
    Skip Docker — use existing PostgreSQL/Redis (configure .env manually)
.PARAMETER RegisterService
    Register DCMS as Windows Service via NSSM if available
.EXAMPLE
    .\scripts\install_windows_server.ps1
.EXAMPLE
    .\scripts\install_windows_server.ps1 -InstallPath D:\Apps\DCMS -Port 8080 -RegisterService
#>
param(
    [string]$InstallPath = "C:\DCMS",
    [int]$Port = 8080,
    [switch]$SkipDocker,
    [switch]$RegisterService,
    [switch]$OpenFirewall
)

$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Version = "1.1.0-enterprise"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  DCMS $Version — Windows Server Installer          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. OS Check ──
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "OS: $($os.Caption) ($($os.Version))"
if ($os.ProductType -lt 2) {
    Write-Host "⚠ Warning: Not a Windows Server edition. Proceeding anyway..." -ForegroundColor Yellow
}

# ── 2. Python 3.11+ ──
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "❌ Python not found." -ForegroundColor Red
    Write-Host "   Install Python 3.11+ from https://www.python.org/downloads/"
    Write-Host "   ✓ Check 'Add Python to PATH' during installation"
    exit 1
}
$pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "✓ Python $pyVer"

# ── 3. Copy files to InstallPath ──
if ($SourceRoot -ne $InstallPath) {
    Write-Host "Copying DCMS to $InstallPath ..."
    New-Item -ItemType Directory -Force -Path $InstallPath | Out-Null
    $exclude = @('venv', '__pycache__', '.pytest_cache', '.env', 'dist', '.git')
    Get-ChildItem $SourceRoot -Force | Where-Object { $_.Name -notin $exclude } | ForEach-Object {
        $dest = Join-Path $InstallPath $_.Name
        if ($_.PSIsContainer) {
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }
            Copy-Item $_.FullName $dest -Recurse -Force
        } else {
            Copy-Item $_.FullName $dest -Force
        }
    }
}
Set-Location $InstallPath
Write-Host "✓ Install path: $InstallPath"

# ── 4. Virtual environment ──
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    python -m venv venv
    Write-Host "✓ Created virtual environment"
}
& ".\venv\Scripts\Activate.ps1"
$env:PYTHONPATH = $InstallPath
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
Write-Host "✓ Python dependencies installed"

# ── 5. Environment file ──
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}
$secret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
$envContent = Get-Content ".env" -Raw
if ($envContent -match "SECRET_KEY=change-this") {
    $envContent = $envContent -replace "SECRET_KEY=.*", "SECRET_KEY=$secret"
    Set-Content ".env" $envContent -NoNewline
    Write-Host "✓ Generated random SECRET_KEY in .env"
}
# Update port in .env if needed
(Get-Content ".env") -replace "DCMS_PORT=.*", "DCMS_PORT=$Port" | Set-Content ".env"

# ── 6. Docker — PostgreSQL + Redis ──
if (-not $SkipDocker) {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        Write-Host "Starting PostgreSQL + Redis via Docker..."
        docker compose up -d
        Start-Sleep -Seconds 10
        $healthy = docker compose ps --format json 2>$null | ConvertFrom-Json -ErrorAction SilentlyContinue
        Write-Host "✓ Docker containers started"
    } else {
        Write-Host "⚠ Docker not found. Options:" -ForegroundColor Yellow
        Write-Host "  1. Install Docker on Windows Server:"
        Write-Host "     https://docs.docker.com/engine/install/windows-server/"
        Write-Host "  2. Install PostgreSQL 16 + Redis (Memurai) manually"
        Write-Host "  3. Update DATABASE_URL and REDIS_URL in .env"
        Write-Host ""
        $cont = Read-Host "Continue without Docker? (y/N)"
        if ($cont -ne 'y') { exit 1 }
    }
}

# ── 7. Initialize database ──
Write-Host "Initializing database..."
$env:PYTHONPATH = $InstallPath
python scripts\init_db.py
Write-Host "✓ Database initialized (admin / admin123)" -ForegroundColor Green

# ── 8. Startup scripts ──
@(
"@echo off",
"title DCMS Server",
"cd /d `"$InstallPath`"",
"set PYTHONPATH=$InstallPath",
"call venv\Scripts\activate.bat",
"echo Starting DCMS on port $Port ...",
"uvicorn app.main:app --host 0.0.0.0 --port $Port --workers 2",
"pause"
) | Set-Content "$InstallPath\Start-DCMS.bat" -Encoding ASCII

@(
"@echo off",
"echo Stopping DCMS ...",
"for /f `"tokens=5`" %%a in ('netstat -aon ^| findstr :$Port ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul",
"echo Done."
) | Set-Content "$InstallPath\Stop-DCMS.bat" -Encoding ASCII

Write-Host "✓ Created Start-DCMS.bat and Stop-DCMS.bat"

# ── 9. Firewall ──
if ($OpenFirewall) {
    try {
        $ruleName = "DCMS-HTTP-$Port"
        if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
            Write-Host "✓ Firewall rule added for port $Port"
        }
    } catch {
        Write-Host "⚠ Could not add firewall rule (configure manually)" -ForegroundColor Yellow
    }
} else {
    try {
        New-NetFirewallRule -DisplayName "DCMS-HTTP-$Port" -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -ErrorAction SilentlyContinue | Out-Null
        Write-Host "✓ Firewall rule added for port $Port"
    } catch { }
}

# ── 10. Windows Service (NSSM) ──
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if ($RegisterService -and $nssm) {
    $uvicorn = Join-Path $InstallPath "venv\Scripts\uvicorn.exe"
    & nssm stop DCMS 2>$null
    & nssm remove DCMS confirm 2>$null
    & nssm install DCMS $uvicorn "app.main:app --host 0.0.0.0 --port $Port --workers 2"
    & nssm set DCMS AppDirectory $InstallPath
    & nssm set DCMS AppEnvironmentExtra "PYTHONPATH=$InstallPath"
    & nssm set DCMS DisplayName "DCMS - Data Center Management"
    & nssm set DCMS Description "DCMS Enterprise Platform v$Version"
    & nssm set DCMS Start SERVICE_AUTO_START
    & nssm start DCMS
    Write-Host "✓ DCMS registered as Windows Service (DCMS)" -ForegroundColor Green
} elseif ($RegisterService) {
    Write-Host "⚠ NSSM not found. Install from https://nssm.cc/download" -ForegroundColor Yellow
    Write-Host "  Or use Start-DCMS.bat / Task Scheduler"
}

# ── 11. Scheduled Task (auto-start on boot, fallback) ──
$taskName = "DCMS-AutoStart"
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $existingTask -and -not ($RegisterService -and $nssm)) {
    $action = New-ScheduledTaskAction -Execute "$InstallPath\Start-DCMS.bat"
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Description "DCMS Auto Start" | Out-Null
    Write-Host "✓ Scheduled task '$taskName' created (starts on boot)"
}

# ── Done ──
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ Installation Complete                               ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  URL:    http://localhost:$Port" -ForegroundColor Green
if ($ip) { Write-Host "║  LAN:    http://${ip}:$Port" -ForegroundColor Green }
Write-Host "║  Login:  admin / admin123  (⚠ change immediately!)" -ForegroundColor Green
Write-Host "║  Docs:   $InstallPath\docs\INSTALL_WINDOWS_AR.md" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  Start:  $InstallPath\Start-DCMS.bat" -ForegroundColor Green
Write-Host "║  Stop:   $InstallPath\Stop-DCMS.bat" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
