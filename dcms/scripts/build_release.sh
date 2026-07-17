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

# ── Windows ZIP ──
WIN_NAME="dcms-${VERSION}-windows"
WIN_STAGE="$OUT_DIR/$WIN_NAME"
WIN_ZIP="$OUT_DIR/${WIN_NAME}.zip"
rm -rf "$WIN_STAGE" "$WIN_ZIP"
mkdir -p "$WIN_STAGE"
if command -v rsync &>/dev/null; then
  rsync -a "$ROOT/" "$WIN_STAGE/" \
    --exclude venv --exclude __pycache__ --exclude .pytest_cache \
    --exclude .env --exclude dist --exclude .git --exclude '*.pyc'
else
  (cd "$ROOT" && tar cf - \
    --exclude=venv --exclude=__pycache__ --exclude=.pytest_cache \
    --exclude=.env --exclude=dist --exclude=.git --exclude='*.pyc' .) | (cd "$WIN_STAGE" && tar xf -)
fi
if command -v zip &>/dev/null; then
  (cd "$OUT_DIR" && zip -rq "${WIN_NAME}.zip" "$WIN_NAME")
  sha256sum "${WIN_NAME}.zip" > "${WIN_NAME}.zip.sha256"
  WIN_SIZE=$(du -h "$WIN_ZIP" | cut -f1)
  echo "✅ Windows release: $WIN_ZIP ($WIN_SIZE)"
  echo "   SHA256:  $OUT_DIR/${WIN_NAME}.zip.sha256"
else
  echo "⚠ zip not found — build Windows package on Windows: .\\scripts\\build_release.ps1"
fi
echo ""
echo "Linux:  tar -xzf ${NAME}.tar.gz && sudo bash scripts/install_linux.sh"
echo "Windows: Expand-Archive ${WIN_NAME}.zip C:\\DCMS && .\\INSTALL.bat"
