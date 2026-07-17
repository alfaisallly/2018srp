# DCMS - Data Center Management System

**الإصدار:** 1.1.0-enterprise — نظام متكامل لإدارة مراكز البيانات

## التحميل والتثبيت

| المنصة | الحزمة | الدليل |
|--------|--------|--------|
| **Linux** | `dist/dcms-1.1.0-enterprise.tar.gz` | [INSTALL_AR.md](docs/INSTALL_AR.md) |
| **Windows Server** | `dist/dcms-1.1.0-enterprise-windows.zip` | [INSTALL_WINDOWS_AR.md](docs/INSTALL_WINDOWS_AR.md) |

```bash
bash scripts/build_release.sh
```

### Windows Server (سريع)

```powershell
Expand-Archive dcms-1.1.0-enterprise-windows.zip -DestinationPath C:\DCMS
cd C:\DCMS
.\INSTALL.bat
```

### Docker (Stack كامل)

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml up -d --build
```

## الميزات

| الوحدة | التفاصيل |
|--------|----------|
| مراكز البيانات | إدارة DC، KPIs، تقارير PDF |
| الشبكة | Cisco, Juniper, Fortinet — SNMP/SSH/NETCONF |
| IPAM | بادئات، تخصيص، تعارضات IP |
| المراقبة | SNMP + حساسات + جدولة APScheduler |
| النسخ الاحتياطي | Cisco/Juniper SSH — يومياً |
| التكاملات | PRTG, VMware REST |
| الواجهة | عربي/EN + Theme Studio (نهاري/ليلي) |

## الوصول الافتراضي

| | |
|---|---|
| URL | http://localhost:8080 |
| API | http://localhost:8080/docs |
| Login | admin / admin123 ⚠️ غيّر فوراً |

## هيكل المشروع

```
dcms/
├── app/                    # Backend FastAPI
├── frontend/               # SPA + Theme Studio
├── docs/                   # دليل التثبيت
├── deploy/                 # systemd + nginx
├── scripts/                # install, build, init
├── docker-compose.yml      # PostgreSQL + Redis
├── docker-compose.prod.yml # Stack كامل
└── Dockerfile
```

## API الرئيسية

```
POST   /api/v1/auth/login
GET    /api/v1/datacenters
GET    /api/v1/platform/capabilities
GET    /api/v1/ipam/prefixes
POST   /api/v1/backups/run-all
POST   /api/v1/integrations
POST   /api/v1/devices/poll-all
GET    /api/v1/reports/datacenter/{id}/pdf
```

## الترخيص

MIT — © 2026 مديرية المرور — قسم الاتصالات
