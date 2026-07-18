# DCMS — دليل التثبيت والنشر للإنتاج

**الإصدار:** 1.1.0-enterprise  
**نظام إدارة مراكز البيانات — مديرية المرور / قسم الاتصالات**

---

## 1. نظرة عامة

DCMS نظام متكامل لإدارة مراكز البيانات يشمل:

| الوحدة | الوصف |
|--------|--------|
| مراكز البيانات | إدارة DC، الرفوف، الأصول |
| الشبكة | Cisco, Juniper, Fortinet — SNMP/SSH/NETCONF |
| IPAM | إدارة عناوين IP والبادئات |
| المراقبة | SNMP + حساسات PRTG-style |
| النسخ الاحتياطي | إعدادات Cisco/Juniper عبر SSH |
| التكاملات | PRTG, VMware vSphere |
| الواجهة | عربي/English + استوديو المظهر (نهاري/ليلي) |

---

## 2. متطلبات السيرفر

### الحد الأدنى (حتى 500 جهاز)

| المورد | المواصفة |
|--------|----------|
| نظام التشغيل | Ubuntu 22.04/24.04 LTS أو RHEL 8/9 أو Windows Server 2019+ |
| المعالج | 4 أن cores |
| الذاكرة | 8 GB RAM |
| التخزين | 50 GB SSD |
| الشبكة | وصول SNMP/SSH إلى أجهزة الشبكة |

### الموصى به (إنتاج)

| المورد | المواصفة |
|--------|----------|
| المعالج | 8 cores |
| الذاكرة | 16 GB RAM |
| التخزين | 100 GB SSD + نسخ احتياطي DB |
| HTTPS | Nginx + شهادة SSL |

### البرمجيات المطلوبة

- **Python 3.11+**
- **PostgreSQL 16**
- **Redis 7**
- **Docker** (موصى به) أو تثبيت PostgreSQL/Redis يدوياً

---

## 3. تحميل النسخة الكاملة

### تحميل الحزمة

| المنصة | الملف |
|--------|-------|
| **Linux** | `dist/dcms-1.1.0-enterprise.tar.gz` |
| **Windows Server** | `dist/dcms-1.1.0-enterprise-windows.zip` |

```bash
bash scripts/build_release.sh
```

### نقل إلى السيرفر

```bash
scp dist/dcms-1.1.0-enterprise.tar.gz user@SERVER:/tmp/
ssh user@SERVER
cd /opt
sudo tar -xzf /tmp/dcms-1.1.0-enterprise.tar.gz
cd dcms-1.1.0-enterprise
```

### التحقق من سلامة الملف (اختياري)

```bash
sha256sum -c dcms-1.1.0-enterprise.tar.gz.sha256
```

---

## 4. التثبيت السريع (Linux — موصى به)

```bash
cd dcms-1.1.0-enterprise
sudo bash scripts/install_linux.sh
```

يقوم المثبت تلقائياً بـ:
1. تثبيت الحزم البرمجية
2. إنشاء مستخدم `dcms`
3. نسخ النظام إلى `/opt/dcms`
4. إنشاء بيئة Python
5. توليد `SECRET_KEY` عشوائي
6. تشغيل PostgreSQL + Redis عبر Docker
7. تهيئة قاعدة البيانات
8. تفعيل خدمة systemd

**بعد التثبيت:** http://SERVER_IP:8080  
**الدخول:** `admin` / `admin123`

---

## 5. التثبيت اليدوي (خطوة بخطوة)

### 5.1 استخراج الملفات

```bash
sudo mkdir -p /opt/dcms
sudo tar -xzf dcms-1.1.0-enterprise.tar.gz -C /opt --strip-components=1
# أو: sudo cp -r dcms-1.1.0-enterprise/* /opt/dcms/
cd /opt/dcms
```

### 5.2 بيئة Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5.3 إعداد المتغيرات (.env)

```bash
cp .env.example .env
nano .env
```

**أهم الإعدادات للإنتاج:**

```env
SECRET_KEY=<مفتاح-عشوائي-طويل-64-حرف>
DEBUG=false
DATABASE_URL=postgresql+asyncpg://dcms:STRONG_PASSWORD@localhost:5432/dcms
REDIS_URL=redis://localhost:6379/0
POLL_INTERVAL_SECONDS=300
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

> ⚠️ **غيّر `SECRET_KEY` وكلمة مرور PostgreSQL قبل الإنتاج**

### 5.4 تشغيل PostgreSQL و Redis

**باستخدام Docker (موصى به):**

```bash
docker compose up -d
docker compose ps   # تأكد أن postgres و redis healthy
```

**أو Docker Production (يشمل التطبيق):**

```bash
cp .env.example .env
# عدّل POSTGRES_PASSWORD في .env
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec dcms python scripts/init_db.py
```

### 5.5 تهيئة قاعدة البيانات

```bash
source venv/bin/activate
export PYTHONPATH=/opt/dcms
python scripts/init_db.py
```

### 5.6 تشغيل التطبيق

**تجريبي:**

```bash
bash scripts/start_production.sh
```

**خدمة systemd (إنتاج):**

```bash
sudo cp deploy/dcms.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dcms
sudo systemctl start dcms
sudo systemctl status dcms
```

**سجلات التشغيل:**

```bash
journalctl -u dcms -f
```

---

## 6. التثبيت على Windows Server

**📖 الدليل الكامل:** [docs/INSTALL_WINDOWS_AR.md](docs/INSTALL_WINDOWS_AR.md)

```powershell
# 1. فك الضغط
Expand-Archive dcms-1.1.0-enterprise-windows.zip -DestinationPath C:\DCMS

# 2. PowerShell كمسؤول
cd C:\DCMS
Set-ExecutionPolicy -Scope Process Bypass
.\INSTALL.bat
# أو: .\scripts\install_windows_server.ps1 -RegisterService
```

**الدخول:** http://localhost:8080 — `admin` / `admin123`

---

## 7. Nginx + HTTPS (إنتاج)

```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo cp deploy/nginx-dcms.conf /etc/nginx/sites-available/dcms
# عدّل server_name إلى نطاقك
sudo ln -s /etc/nginx/sites-available/dcms /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d dcms.yourdomain.gov.iq
```

---

## 8. إعداد بيئة العمل الحقيقية

### 8.1 تغيير كلمة مرور المدير

1. سجّل الدخول بـ `admin` / `admin123`
2. **المستخدمين** → تعديل admin → كلمة مرور قوية (12+ حرف)

### 8.2 إضافة مراكز البيانات

**لوحة التحكم** → **+ إضافة مركز بيانات**

أو استيراد Excel: **استيراد Excel** → تحميل القالب → رفع الملف

### 8.3 ربط PRTG

**التكاملات** → **+ إضافة تكامل**
- النوع: PRTG
- Base URL: `https://prtg-server.local`
- API Token: من PRTG → Setup → Account → API Keys

### 8.4 ربط VMware

**التكاملات** → VMware
- URL: `https://vcenter.local`
- Username + Password (Token field)

### 8.5 نسخ إعدادات الشبكة

1. أضف أجهزة Cisco/Juniper مع credentials **SSH**
2. **النسخ الاحتياطي** → **نسخ الكل**
3. النسخ التلقائي يومياً الساعة 02:00

### 8.6 IPAM

**IPAM** → **+ إضافة بادئة** → CIDR مثل `172.16.10.0/24` → **مزامنة الأصول**

---

## 9. الجدار الناري

```bash
# Ubuntu UFW
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
# لا تفتح 8080 للعامة — استخدم Nginx فقط
```

---

## 10. النسخ الاحتياطي

### قاعدة البيانات (يومياً)

```bash
# crontab -e
0 1 * * * docker exec dcms-postgres pg_dump -U dcms dcms | gzip > /backup/dcms_$(date +\%Y\%m\%d).sql.gz
```

### استعادة

```bash
gunzip -c /backup/dcms_20260717.sql.gz | docker exec -i dcms-postgres psql -U dcms dcms
```

---

## 11. استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| لا يفتح المنفذ 8080 | `systemctl status dcms` أو `docker compose logs dcms` |
| خطأ DB connection | تحقق DATABASE_URL في .env و `docker compose ps` |
| ModuleNotFoundError: app | `export PYTHONPATH=/opt/dcms` |
| SNMP لا يعمل | تأكد community صحيح + UDP 161 مفتوح من السيرفر |
| SSH backup فشل | credentials + TCP 22 من DCMS إلى الجهاز |
| PRTG فشل | URL بدون `/` + API Token صالح |

---

## 12. API والوثائق

| الرابط | الوصف |
|--------|--------|
| `http://SERVER:8080` | الواجهة |
| `http://SERVER:8080/docs` | Swagger API |
| `POST /api/v1/auth/login` | تسجيل الدخول |

---

## 13. هيكل الملفات

```
dcms-1.1.0-enterprise/
├── app/                  # Backend FastAPI
├── frontend/             # واجهة الويب
├── scripts/
│   ├── install_linux.sh  # مثبت Linux
│   ├── install_windows.ps1
│   ├── init_db.py        # تهيئة DB
│   ├── build_release.sh  # بناء الحزمة
│   └── start_production.sh
├── deploy/
│   ├── dcms.service      # systemd
│   └── nginx-dcms.conf
├── docs/
│   ├── INSTALL_AR.md     # هذا الملف
│   └── INSTALL_EN.md
├── docker-compose.yml      # DB + Redis
├── docker-compose.prod.yml # Stack كامل
├── Dockerfile
├── .env.example
├── requirements.txt
└── VERSION
```

---

## 14. الدعم

**قسم الاتصالات — مديرية المرور**  
© 2026 — جميع الحقوق محفوظة

---

*آخر تحديث: يوليو 2026 — الإصدار 1.1.0-enterprise*
