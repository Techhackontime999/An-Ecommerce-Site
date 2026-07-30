#!/usr/bin/env bash
# =============================================================================
# Setup Script for Django E-Commerce Site
# =============================================================================
# Runs migrations, collects static files, and creates a superuser if configured.
# Designed to be idempotent — safe to run on every deployment.
# Usage: bash setup.sh
# =============================================================================

set -e  # exit on any error

echo "=== Running database migrations ==="
python manage.py migrate --noinput

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput --clear

# Create superuser if DJANGO_SUPERUSER_* env vars are set
if [[ -n "$DJANGO_SUPERUSER_USERNAME" && -n "$DJANGO_SUPERUSER_EMAIL" && -n "$DJANGO_SUPERUSER_PASSWORD" ]]; then
    echo "=== Creating/updating superuser ==="
    # Use shell to check if user exists; createsuperuser --noinput skips if exists
    python manage.py createsuperuser --noinput 2>/dev/null || {
        echo "Superuser already exists or creation failed. Updating password instead."
        python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ['DJANGO_SUPERUSER_USERNAME']
email = os.environ['DJANGO_SUPERUSER_EMAIL']
password = os.environ['DJANGO_SUPERUSER_PASSWORD']
try:
    user = User.objects.get(username=username)
    user.set_password(password)
    user.email = email
    user.save()
    print(f'Superuser \"{username}\" password updated.')
except User.DoesNotExist:
    print(f'Could not create superuser \"{username}\".')
"
    }
fi

echo "=== Setup complete ==="
