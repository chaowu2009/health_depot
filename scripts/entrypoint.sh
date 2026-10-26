#!/bin/sh
# Health Depot container entrypoint. Usage: entrypoint.sh {web|worker|migrate|dev|manage ...}
set -eu
ROLE="${1:-web}"
echo "$ROLE" > /tmp/hd-role 2>/dev/null || true

case "$ROLE" in
  web|dev|worker|migrate|manage) cd /app/src ;;
esac

case "$ROLE" in
  web)
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --worker-tmp-dir /tmp \
      --no-control-socket \
      --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
      --access-logfile - --error-logfile - \
      --access-logformat '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)s'
    ;;
  dev)
    python manage.py wait_for_db
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  worker)
    python manage.py wait_for_db
    exec python manage.py run_worker
    ;;
  migrate)
    # Hosted platforms (e.g. DigitalOcean App Platform) run this as a pre-deploy job.
    python manage.py wait_for_db --timeout "${DB_WAIT_TIMEOUT:-120}"
    python manage.py migrate --noinput
    python manage.py createcachetable
    python manage.py bootstrap
    if [ "${DEMO_MODE:-false}" = "true" ]; then
      python manage.py seed_demo  # loads synthetic demo data only if the database is empty
    fi
    # S3_CHECK_BUCKET=false skips the storage check (storage not configured yet). Login and
    # referrals still work; only file uploads/downloads need storage.
    if [ "${S3_CHECK_BUCKET:-true}" != "true" ]; then
      echo "Skipping storage bucket check (S3_CHECK_BUCKET=${S3_CHECK_BUCKET})."
    elif [ "${S3_CREATE_BUCKET:-false}" = "true" ]; then
      python manage.py ensure_bucket
    else
      python manage.py ensure_bucket --no-create
    fi
    ;;
  manage)
    shift
    exec python manage.py "$@"
    ;;
  *)
    # Any other command runs from the project root (/app), e.g. pytest, ruff, mypy.
    exec "$@"
    ;;
esac
