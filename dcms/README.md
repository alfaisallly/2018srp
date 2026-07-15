# DCMS - Data Center Management System

نظام متكامل لإدارة مراكز البيانات يعمل على **Windows 11**، مبني بـ **Python + FastAPI + PostgreSQL + Redis**.

## الميزات

| الميزة | التفاصيل |
|--------|----------|
| **المورّدون** | Cisco, Juniper, Fortinet |
| **البروتوكولات** | SNMP, SSH, NETCONF, REST API |
| **خريطة الشبكة** | تصور تفاعلي بـ vis.js |
| **الصلاحيات** | RBAC (admin, operator, viewer) |
| **التقارير** | PDF/HTML لكل مركز بيانات |
| **التنبيهات** | CPU/ذاكرة/انقطاع + Redis pub/sub |
| **المراقبة** | جدولة تلقائية APScheduler |

## المتطلبات

- Windows 11 (أو Linux/macOS للتطوير)
- Python 3.11+
- PostgreSQL 16
- Redis 7
- Docker Desktop (موصى به على Windows)

## التثبيت على Windows 11

```powershell
cd dcms
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
```

أو يدوياً:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
python scripts\init_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## الوصول

| الرابط | الوصف |
|--------|-------|
| http://localhost:8080 | واجهة الويب (عربية) |
| http://localhost:8080/docs | Swagger API |
| admin / admin123 | حساب المدير الافتراضي |

## هيكل المشروع

```
dcms/
├── app/
│   ├── main.py              # FastAPI + APScheduler
│   ├── models/              # SQLAlchemy ORM
│   ├── api/                 # REST endpoints
│   ├── vendors/             # Cisco/Juniper/Fortinet adapters
│   ├── services/            # SNMP, SSH, NETCONF, REST
│   └── core/                # JWT + RBAC
├── frontend/                # واجهة عربية + خريطة شبكة
├── scripts/
│   ├── install_windows.ps1  # مثبت Windows 11
│   └── init_db.py           # بيانات أولية
├── docker-compose.yml       # PostgreSQL + Redis
└── requirements.txt
```

## API الرئيسية

```
POST   /api/v1/auth/login
GET    /api/v1/auth/me
GET    /api/v1/datacenters
POST   /api/v1/devices
POST   /api/v1/devices/discover          # مسح SNMP لنطاق IP
POST   /api/v1/devices/import-discovered # استيراد الأجهزة المكتشفة
POST   /api/v1/devices/poll-all          # فحص جميع الأجهزة
POST   /api/v1/devices/{id}/poll
GET    /api/v1/network-maps
GET    /api/v1/alerts
PATCH  /api/v1/alerts/{id}
GET    /api/v1/reports/dashboard
GET    /api/v1/reports/datacenter/{id}/pdf
```

## الأدوار والصلاحيات

| الدور | الصلاحيات |
|-------|-----------|
| **admin** | جميع الصلاحيات |
| **operator** | إدارة الأجهزة، التنبيهات، الخرائط، التقارير |
| **viewer** | عرض فقط + التقارير |

## مراكز البيانات (العراق)

| المركز | الاسم | التخزين | IP |
|--------|-------|---------|-----|
| مديرية المرور العامة | DC-MOROOR-01 | Pure Storage //R40 | 172.16.10.20 |
| وزارة الداخلية | DC-MOI-01 | Pure Storage //R40 | 172.16.20.20 |

لتحديث البيانات وحذف أي بيانات تجريبية قديمة (مثل الرياض):

```powershell
python scripts\reset_iraq_sites.py
```

## إضافة جهاز

```json
POST /api/v1/devices
{
  "datacenter_id": 1,
  "name": "MR-Core-SW-01",
  "hostname": "mr-core-sw-01",
  "ip_address": "172.16.10.1",
  "vendor": "cisco",
  "credentials": [
    { "protocol": "snmp", "community": "public", "port": 161 }
  ]
}
```

## الترخيص

MIT
