#!/usr/bin/env bash
# Build release tarball for offline deployment
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(cat "$ROOT/VERSION" | tr -d '[:space:]')"
NAME="dcms-${VERSION}"
OUT_DIR="$ROOT/dist"
STAGE="$OUT_DIR/$NAME"

echo "Building DCMS release $VERSION..."

rm -rf "$STAGE" "$OUT_DIR/${NAME}.tar.gz"
mkdir -p "$STAGE"

rsync -a "$ROOT/" "$STAGE/" \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.env' \
  --exclude 'dist' \
  --exclude '.git' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  --exclude '.DS_Store' 2>/dev/null || {
  echo "rsync not found, using tar..."
  (cd "$ROOT" && tar cf - \
    --exclude=venv --exclude=__pycache__ --exclude=.pytest_cache \
    --exclude=.env --exclude=dist --exclude=.git \
    --exclude='*.pyc' .) | (cd "$STAGE" && tar xf -)
}

# Ensure scripts are executable
chmod +x "$STAGE/scripts/"*.sh 2>/dev/null || true

# Create checksums
cd "$OUT_DIR"
tar -czf "${NAME}.tar.gz" "$NAME"
sha256sum "${NAME}.tar.gz" > "${NAME}.tar.gz.sha256"

SIZE=$(du -h "${NAME}.tar.gz" | cut -f1)
echo ""
echo "✅ Release built successfully"
echo "   Package: $OUT_DIR/${NAME}.tar.gz ($SIZE)"
echo "   SHA256:  $OUT_DIR/${NAME}.tar.gz.sha256"
echo ""
echo "Deploy steps:"
echo "  1. Copy ${NAME}.tar.gz to your server"
echo "  2. tar -xzf ${NAME}.tar.gz"
echo "  3. cd $NAME && sudo bash scripts/install_linux.sh"
echo "  Or read docs/INSTALL_AR.md for manual steps"
