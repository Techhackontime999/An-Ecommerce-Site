release: bash setup.sh
web: bash setup.sh && gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers=3 --access-logfile=-
