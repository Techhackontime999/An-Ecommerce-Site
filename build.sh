#!/usr/bin/env bash
# =============================================================================
# Build Script — runs during the build phase on Render
# =============================================================================
set -e

echo "=== Creating static directory ==="
mkdir -p static

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== Build complete ==="
