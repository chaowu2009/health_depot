# Health Depot — Demo on DigitalOcean App Platform

For a **public demo with synthetic data only**. This isn't the planned production hosting
(see DEPLOYMENT_AWS_GOVCLOUD.md), and it must never hold real client information.

## What runs

| Component | App Platform type | Size | Command |
|---|---|---|---|
| `web` | Service (public HTTPS) | 1 GB (`apps-s-1vcpu-1gb`) | `entrypoint.sh web` |
| `worker` | Worker | 512 MB | `entrypoint.sh worker` |
| `migrate` | Pre-deploy job | 1 GB | `entrypoint.sh migrate` (migrations + demo data on first deploy) |
| `db` | Dev PostgreSQL 16 | — | provides `${db.DATABASE_URL}` |
| File storage | A DigitalOcean **Space** (S3-compatible) | — | logos, documents |

Email has no SMTP server here, so notification emails are written to the app log
(`EMAIL_BACKEND=…console…`). Add an SMTP provider later by changing the `EMAIL_*` settings.

## Steps

1. **Push the project to GitHub.** Don't push `.env`; `.gitignore` already excludes it.
2. **Create a Space:** Spaces Object Storage → Create, region `nyc3`, private. Then
   **API → Spaces Keys → Generate** and copy the key and secret.
3. **Create or fix the app:** in your app, open **Settings → App Spec → Edit**. Paste
   `.do/app.yaml` and replace every `CHANGE-ME`:
   - the GitHub `repo` (3 places)
   - `DJANGO_SECRET_KEY`: a long random string, for example from
     `python -c "import secrets; print(secrets.token_urlsafe(50))"`
   - the Space name (2 places) and the Spaces key and secret
4. **Save.** App Platform builds the image, runs `migrate`, then starts `web` and `worker`.
   The first deploy takes about 5–10 minutes.
5. Open the app URL and sign in, for example as `test` / `test2026` plus the 2-factor code.

## If a deploy fails

Open the app → **Activity** → the failed deploy, then check **Deploy logs** and **Runtime logs**
for the failing component.

| Log shows | Cause | Fix |
|---|---|---|
| `ImproperlyConfigured: Set the … environment variable` | A setting is missing | Add it in the App Spec (`envs`) |
| `NoCredentialsError: Unable to locate credentials` or `Bucket … not reachable` (migrate job) | No Spaces keys, or wrong Space name/region | Add the Space and its keys, or set `S3_CHECK_BUCKET=false` to skip the check for now (uploads and logos won't work until keys are added) |
| `permission denied for schema public` (migrate job) | Database user can't create tables (PostgreSQL 15+ dev databases) | Set `DATABASE_SCHEMA=healthdepot`, or use a managed database cluster |
| `OOMKilled` / "exceeding resource limits" | Too little memory | Use the 1 GB size, keep `GUNICORN_WORKERS=2` |
| Health check failures | Wrong port | `http_port: 8000` with `PORT=8000` (both already in the spec) |
| `exec format error` | Image built on an ARM computer and pushed | Deploy from GitHub (App Platform builds for its own servers) or build with `--platform linux/amd64` |

## Security note for a public demo

`DEMO_MODE=true` loads the demo accounts, and their passwords and 2-factor key are published in
the docs. Anyone who finds the URL can sign in, including as an administrator. That's
acceptable for synthetic data, but:

- Share the URL only with evaluators, and delete the app after the evaluation.
- Or change the demo passwords, including `test`'s, under **Users & access** after the first
  deploy. Changed passwords are kept on later deploys.
- The site footer states it's a demonstration system and not an official county website.
  Keep that wording.
