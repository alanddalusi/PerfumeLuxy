#!/usr/bin/env bash
set -eu

export DJANGO_ENV=production
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
