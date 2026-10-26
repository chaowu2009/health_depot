# Deploying Health Depot on DigitalOcean App Platform (demo)

App Platform does **not** run `compose.yaml`, so the `db`, `s3`, `mailpit` and `migrate`
services from the local stack don't exist there. You supply them as App Platform pieces:

| Local (compose) | App Platform |
|---|---|
| `db` (postgres) | Database component (dev database or managed PostgreSQL cluster) |
| `migrate` | **PRE_DEPLOY job** running `entrypoint.sh migrate` |
| `web` | Service, HTTP port 8000, `entrypoint.sh web` |
| `worker` | Worker, `entrypoint.sh worker` |
| `s3` (SeaweedFS) | DigitalOcean Spaces (S3-compatible) — optional for a first demo |
| `mailpit` | Any SMTP provider |
| `proxy` (Caddy) | App Platform's built-in HTTPS (sends `X-Forwarded-Proto`) |

The ready-made spec is **`.do/app.yaml`**.

## Why a first deploy shows no tables / 503 on login

If only the web service runs, nothing ever runs `migrate`, so the database has no tables
(no users, no `django_cache` table used by the login rate limiter). The login page renders,
but posting the form fails. If the database isn't attached or reachable at all, requests hang
until Gunicorn kills the worker and the platform answers 502/503.

## Deploy

1. Push the code to GitHub (`.env` is gitignored — keep it that way).
2. Edit `.do/app.yaml`: replace `OWNER/REPO` (3 places) and every `CHANGE-ME` value.
   Generate a secret key with
   `python -c "import secrets; print(secrets.token_urlsafe(50))"`.
3. Create or update the app:
   - New: `doctl apps create --spec .do/app.yaml`
   - Existing: Control Panel → app → **Settings → App Spec → Edit**, paste, Save.
4. Watch **Activity → Deploy logs → migrate**. You should see `Database is ready.`,
   migrations, `Bootstrap complete.` and the demo seed summary.
5. Open the app URL and sign in with a demo login from README.md
   (e.g. `admin@demo.healthdepot.local` / `HealthDepot-Demo-2026!`, TOTP key
   `HEALTHDEPOTDEMOKEYCALVERTCOUNTYM`).

## Fix an app that is already deployed (no redeploy needed)

Control Panel → app → **Console** → choose `web`, then run:

```
entrypoint.sh migrate
```

(With `DEMO_MODE=true` this also loads demo users. Otherwise create an admin with
`entrypoint.sh manage createsuperuser`.) Then add the PRE_DEPLOY job so future deploys
migrate automatically.

## Checklist when something is still wrong

- **Database attached?** `DATABASE_URL` must be `${db.DATABASE_URL}` on web, worker **and**
  the job. With a managed cluster, add the app to the cluster's **Trusted Sources**.
- `https://<app>.ondigitalocean.app/health/ready` → `{"database": "up"}`.
- **400 Bad Request** → `ALLOWED_HOSTS` doesn't include the app domain.
- **403 CSRF** on login → `CSRF_TRUSTED_ORIGINS` must be the full `https://...` URL.
- **Job fails on storage** → set `S3_CHECK_BUCKET=false` until Spaces is configured.
- **Out of memory / restarts** → use a 1 GB instance or `GUNICORN_WORKERS=2`.
- **Custom domain** → add it to `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and
  `PUBLIC_BASE_URL`.

## Storage (Spaces)

Create a Space (e.g. `health-depot-demo` in `nyc3`) and a Spaces access key, fill in the
`AWS_*` values in the spec, set `S3_CHECK_BUCKET=true`, and redeploy. Keep the Space private
— the app only hands out short-lived presigned URLs.

## Not for production

`DEMO_MODE=true` loads synthetic data and enables the demo reset tool. A real deployment
turns it off and follows DEPLOYMENT_AWS_GOVCLOUD.md.
