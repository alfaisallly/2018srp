#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# DCMS — Linux Production Installer (Ubuntu/Debian/RHEL)
# Run: sudo bash scripts/install_linux.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

DCMS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="${DCMS_INSTALL_DIR:-/opt/dcms}"
DCMS_USER="${DCMS_USER:-dcms}"
DCMS_PORT="${DCMS_PORT:-8080}"

echo "╔══════════════════════════════════════════════════╗"
echo "║  DCMS — Enterprise Installation (Linux)          ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Source: $DCMS_ROOT"
echo "Target: $INSTALL_DIR"

# ── 1. System packages ──
if command -v apt-get &>/dev/null; then
  apt-get update -qq
  apt-get install -y -qq python3 python3-venv python3-pip curl git \
    libpq-dev build-essential \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info \
    docker.io docker-compose-plugin 2>/dev/null || apt-get install -y docker.io docker-compose
elif command -v dnf &>/dev/null; then
  dnf install -y python3 python3-pip curl git postgresql-devel gcc \
    pango cairo gdk-pixbuf2 libffi-devel docker docker-compose
else
  echo "⚠ Unsupported package manager. Install Python 3.11+, Docker manually."
fi

# ── 2. Create system user ──
if ! id "$DCMS_USER" &>/dev/null; then
  useradd -r -m -d "$INSTALL_DIR" -s /bin/bash "$DCMS_USER" 2>/dev/null || useradd -r -d "$INSTALL_DIR" -s /bin/bash "$DCMS_USER"
  echo "✓ Created user: $DCMS_USER"
fi

# ── 3. Copy application ──
mkdir -p "$INSTALL_DIR"
if command -v rsync &>/dev/null; then
  rsync -a --delete \
    --exclude 'venv' --exclude '__pycache__' --exclude '.pytest_cache' \
    --exclude '.env' --exclude '*.pyc' --exclude '.git' --exclude 'dist' \
    "$DCMS_ROOT/" "$INSTALL_DIR/"
else
  rm -rf "$INSTALL_DIR"/*
  (cd "$DCMS_ROOT" && tar cf - --exclude=venv --exclude=__pycache__ --exclude=.pytest_cache \
    --exclude=.env --exclude=dist --exclude=.git --exclude='*.pyc' .) | (cd "$INSTALL_DIR" && tar xf -)
fi
chown -R "$DCMS_USER:$DCMS_USER" "$INSTALL_DIR"

# ── 4. Python virtual environment ──
sudo -u "$DCMS_USER" bash -c "
  cd '$INSTALL_DIR'
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
"

# ── 5. Environment file ──
if [ ! -f "$INSTALL_DIR/.env" ]; then
  SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET|" "$INSTALL_DIR/.env"
  chown "$DCMS_USER:$DCMS_USER" "$INSTALL_DIR/.env"
  echo "✓ Created .env with random SECRET_KEY"
fi

# ── 6. Start PostgreSQL + Redis ──
cd "$INSTALL_DIR"
if command -v docker &>/dev/null; then
  docker compose up -d
  echo "⏳ Waiting for database..."
  sleep 8
  sudo -u "$DCMS_USER" bash -c "
    cd '$INSTALL_DIR'
    source venv/bin/activate
    export PYTHONPATH='$INSTALL_DIR'
    python scripts/init_db.py
  "
  echo "✓ Database initialized"
else
  echo "⚠ Docker not available — configure PostgreSQL/Redis manually in .env"
fi

# ── 7. Systemd service ──
if [ -d /etc/systemd/system ]; then
  sed "s|/opt/dcms|$INSTALL_DIR|g" "$INSTALL_DIR/deploy/dcms.service" > /etc/systemd/system/dcms.service
  systemctl daemon-reload
  systemctl enable dcms
  systemctl restart dcms
  echo "✓ DCMS service enabled (systemctl status dcms)"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ Installation Complete                       ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  URL:    http://$(hostname -I | awk '{print $1}'):$DCMS_PORT"
echo "║  Login:  admin / admin123  (⚠ change immediately)"
echo "║  Docs:   $INSTALL_DIR/docs/INSTALL_AR.md"
echo "╚══════════════════════════════════════════════════╝"
