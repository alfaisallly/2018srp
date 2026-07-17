# DCMS — Production Installation Guide (English)

**Version:** 1.1.0-enterprise

See [INSTALL_AR.md](./INSTALL_AR.md) for the full Arabic guide.

## Quick Start (Linux)

```bash
tar -xzf dcms-1.1.0-enterprise.tar.gz
cd dcms-1.1.0-enterprise
sudo bash scripts/install_linux.sh
```

Open http://SERVER:8080 — login `admin` / `admin123` (change immediately).

## Docker Full Stack

```bash
cp .env.example .env
# Edit SECRET_KEY and POSTGRES_PASSWORD
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec dcms python scripts/init_db.py
```

## Manual Install

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
export PYTHONPATH=.
python scripts/init_db.py
bash scripts/start_production.sh
```

## Production Checklist

- [ ] Change `SECRET_KEY` in `.env`
- [ ] Change PostgreSQL password
- [ ] Change admin password in UI
- [ ] Configure Nginx + HTTPS (`deploy/nginx-dcms.conf`)
- [ ] Enable systemd service (`deploy/dcms.service`)
- [ ] Configure firewall (443 only, not 8080 public)
- [ ] Set up daily DB backup
- [ ] Add PRTG/VMware integrations
- [ ] Add network devices with SNMP/SSH credentials

## Build Release Package

```bash
bash scripts/build_release.sh
# Output: dist/dcms-1.1.0-enterprise.tar.gz
```
