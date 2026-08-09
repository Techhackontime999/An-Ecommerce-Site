release: bash setup.sh
web: gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers=2 --access-logfile=-
