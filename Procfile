release: bash setup.sh
web: gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers=2 --access-logfile=-
worker: python manage.py run_worker --poll 5 --limit 25
