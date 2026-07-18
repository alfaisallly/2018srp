# DCMS — دليل التثبيت على Windows Server

**الإصدار:** 1.1.0-enterprise  
**أنظمة مدعومة:** Windows Server 2019 / 2022 / 2025

---

## 1. المتطلبات

| المورد | الحد الأدنى | الموصى به |
|--------|-------------|-----------|
| المعالج | 4 cores | 8 cores |
| الذاكرة | 8 GB | 16 GB |
| القرص | 50 GB | 100 GB SSD |
| نظام التشغيل | Server 2019+ | Server 2022 |

### البرمجيات

| البرنامج | الإصدار | الرابط |
|----------|---------|--------|
| **Python** | 3.11 أو 3.12 | https://www.python.org/downloads/ |
| **Docker** | Engine on Windows Server | https://docs.docker.com/engine/install/windows-server/ |
| **NSSM** (اختياري — للخدمة) | Latest | https://nssm.cc/download |

> عند تثبيت Python: ✅ فعّل **Add Python to PATH**

---

## 2. تحميل الحزمة

حمّل الملف:
```
dcms-1.1.0-enterprise-windows.zip
```

من GitHub:
```
dcms/dist/dcms-1.1.0-enterprise-windows.zip
```

---

## 3. التثبيت السريع (موصى به)

### 3.1 فك الضغط

```powershell
# فك إلى C:\DCMS
Expand-Archive -Path C:\Downloads\dcms-1.1.0-enterprise-windows.zip -DestinationPath C:\DCMS -Force
cd C:\DCMS
```

### 3.2 تشغيل المثبت

**افتح PowerShell كمسؤول (Run as Administrator):**

```powershell
cd C:\DCMS
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows_server.ps1
```

**خيارات متقدمة:**

```powershell
.\scripts\install_windows_server.ps1 `
  -InstallPath "D:\Apps\DCMS" `
  -Port 8080 `
  -RegisterService `
  -OpenFirewall
```

**بدون Docker** (PostgreSQL/Redis مثبتة يدوياً):

```powershell
.\scripts\install_windows_server.ps1 -SkipDocker
# ثم عدّل .env قبل التشغيل
```

---

## 4. التثبيت اليدوي (خطوة بخطوة)

### 4.1 Python

```powershell
python --version   # يجب 3.11+
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4.2 ملف البيئة

```powershell
copy .env.example .env
notepad .env
```

**أهم الإعدادات:**

```env
SECRET_KEY=<مفتاح-عشوائي-طويل>
DEBUG=false
DATABASE_URL=postgresql+asyncpg://dcms:PASSWORD@localhost:5432/dcms
REDIS_URL=redis://localhost:6379/0
DCMS_PORT=8080
```

### 4.3 PostgreSQL + Redis

**الطريقة أ — Docker (موصى به):**

```powershell
docker compose up -d
docker compose ps
```

**الطريقة ب — تثبيت Windows native:**

1. **PostgreSQL 16:** https://www.postgresql.org/download/windows/
   - أنشئ مستخدم `dcms` وقاعدة `dcms`
2. **Redis (Memurai):** https://www.memurai.com/ — أو Redis for Windows
3. حدّث `DATABASE_URL` و `REDIS_URL` في `.env`

### 4.4 تهيئة قاعدة البيانات

```powershell
$env:PYTHONPATH = "C:\DCMS"
python scripts\init_db.py
```

### 4.5 التشغيل

```powershell
# تجريبي
.\Start-DCMS.bat

# أو يدوياً
$env:PYTHONPATH = "C:\DCMS"
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8080 --workers 2
```

---

## 5. تشغيل كخدمة Windows

### الطريقة أ — NSSM (موصى به)

```powershell
# بعد تثبيت NSSM وإضافته للـ PATH
.\scripts\install_windows_server.ps1 -RegisterService
```

**أو يدوياً:**

```powershell
nssm install DCMS C:\DCMS\venv\Scripts\uvicorn.exe "app.main:app --host 0.0.0.0 --port 8080 --workers 2"
nssm set DCMS AppDirectory C:\DCMS
nssm set DCMS AppEnvironmentExtra PYTHONPATH=C:\DCMS
nssm set DCMS Start SERVICE_AUTO_START
nssm start DCMS
```

**إدارة الخدمة:**

```powershell
nssm status DCMS
nssm restart DCMS
nssm stop DCMS
```

### الطريقة ب — Task Scheduler (تلقائي عند الإقلاع)

المثبت ينشئ مهمة `DCMS-AutoStart` تلقائياً إذا لم يتوفر NSSM.

---

## 6. الجدار الناري (Windows Firewall)

```powershell
New-NetFirewallRule -DisplayName "DCMS-HTTP-8080" `
  -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

---

## 7. IIS Reverse Proxy + HTTPS (إنتاج)

### 7.1 تثبيت IIS + URL Rewrite + ARR

```powershell
Install-WindowsFeature -Name Web-Server, Web-WebSockets
# Install URL Rewrite + Application Request Routing from Microsoft Web Platform
```

### 7.2 إعداد Reverse Proxy

1. IIS Manager → Server → Application Request Routing → Enable proxy
2. أنشئ موقع `dcms.yourdomain.gov.iq`
3. URL Rewrite → Reverse Proxy → `http://localhost:8080`
4. أضف شهادة SSL من CA أو Let's Encrypt (win-acme)

---

## 8. النسخ الاحتياطي

### PostgreSQL (Docker)

```powershell
docker exec dcms-postgres pg_dump -U dcms dcms > C:\Backup\dcms_backup.sql
```

### PostgreSQL (Native)

```powershell
& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U dcms dcms > C:\Backup\dcms_backup.sql
```

### جدولة يومية (Task Scheduler)

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-Command docker exec dcms-postgres pg_dump -U dcms dcms | Out-File C:\Backup\dcms_$(Get-Date -Format yyyyMMdd).sql"
$trigger = New-ScheduledTaskTrigger -Daily -At 1am
Register-ScheduledTask -TaskName "DCMS-DB-Backup" -Action $action -Trigger $trigger -User SYSTEM
```

---

## 9. إعداد بيئة العمل

| الخطوة | الإجراء |
|--------|---------|
| 1 | غيّر كلمة مرور admin |
| 2 | أضف مراكز البيانات |
| 3 | استورد الأجهزة (Excel أو يدوي) |
| 4 | اربط PRTG من **التكاملات** |
| 5 | أضف credentials SSH لـ Cisco/Juniper |
| 6 | فعّ IPAM prefixes |

---

## 10. استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| `python not found` | أعد تثبيت Python مع Add to PATH |
| `ModuleNotFoundError: app` | `$env:PYTHONPATH = "C:\DCMS"` |
| DB connection error | `docker compose ps` أو تحقق PostgreSQL service |
| Port 8080 in use | `netstat -ano \| findstr :8080` ثم `Stop-DCMS.bat` |
| Docker not starting | تأكد Docker service يعمل: `Get-Service docker` |
| PDF reports fail | ثبّت GTK3 for WeasyPrint أو استخدم HTML reports |
| ExecutionPolicy | `Set-ExecutionPolicy -Scope Process Bypass` |

---

## 11. الملفات المهمة

```
C:\DCMS\
├── Start-DCMS.bat              ← تشغيل
├── Stop-DCMS.bat               ← إيقاف
├── .env                        ← الإعدادات
├── scripts\install_windows_server.ps1
├── docs\INSTALL_WINDOWS_AR.md  ← هذا الملف
└── venv\                       ← Python environment
```

---

## 12. الوصول

| | |
|---|---|
| **URL** | http://localhost:8080 |
| **API** | http://localhost:8080/docs |
| **Login** | admin / admin123 |

---

© 2026 — مديرية المرور — قسم الاتصالات
