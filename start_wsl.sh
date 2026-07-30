#!/bin/bash
cd "$(dirname "$0")"
source env/bin/activate
setsid python manage.py runserver 0.0.0.0:8000 &>/tmp/django_server.log &
disown
echo "Server PID: $!"
