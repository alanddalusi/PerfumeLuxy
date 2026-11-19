#!/bin/sh
# "serve" runs the release checks and Gunicorn; any other command runs as given
# (e.g. "python manage.py migrate"). Migrations are never applied automatically.
set -eu

if [ "${1:-serve}" = "serve" ]; then
    if [ "${STORE_MODE:-prelaunch}" != "prelaunch" ]; then
        echo "Refusing to start: STORE_MODE must stay 'prelaunch' for this release." >&2
        exit 1
    fi
    python manage.py check --deploy --fail-level ERROR
    if ! python manage.py migrate --check >/dev/null 2>&1; then
        echo "Unapplied migrations. Back up, then run: docker compose run --rm web python manage.py migrate" >&2
        exit 1
    fi
    python manage.py collectstatic --noinput --verbosity 0
    exec gunicorn --config deploy/gunicorn.conf.py eau_royal.wsgi
fi
exec "$@"
