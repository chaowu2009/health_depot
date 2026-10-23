# Health Depot

Closed-loop referral and case management platform for public health departments and their
community partners. Built by Columbia Technology LLC.

> **Demo environment — synthetic data only.** Never enter real client information.

## What you need

- Docker Desktop (Windows: WSL 2 backend), with at least 4 CPUs and 8 GB memory
- Git
- Optional: `make` (macOS/Linux/WSL). On Windows PowerShell use `.\tasks.ps1` instead.
- Optional: [mkcert](https://github.com/FiloSottile/mkcert) for browser-trusted HTTPS

## Quick start for the demo

```
.\tasks.ps1 up-prod            # or: make up-prod      (first build takes a few minutes)
.\tasks.ps1 check-stack -Prod  # or: make check-stack STACK=prod
```

Open **https://localhost**. Synthetic demo data (10 fictional partners, ~300 clients,
800 referrals, 90 cases) loads automatically the first time, because `DEMO_MODE` is on in the
local compose files.

| Demo login (`@demo.healthdepot.local`) | Role |
|---|---|
| `admin` | System administrator (Avery Morgan) |
| `manager` | Program manager (Dana Whitfield) |
| `staff` | CCHD staff (Jordan Rivera) |
| `leader` | Read-only leadership (Dr. Patricia Hale) |
| `partner` | Community partner (Sam Okonkwo, food bank) |

Password for all: `HealthDepot-Demo-2026!` · Two-factor: add the key
`HEALTHDEPOTDEMOKEYCALVERTCOUNTYM` to any authenticator app (time-based, 6 digits).
Walkthrough: **DEMO_SCRIPT.md** · Reset demo data: `.\tasks.ps1 reset-demo -Prod` or
**Users & access → Tools** · Proposal materials: **PROPOSAL_NOTES.md**, `screenshots/`,
`DEMO_VIDEO_NARRATION.md`. More: **DEPLOYMENT_LOCAL.md**, **DEPLOYMENT_AWS_GOVCLOUD.md**,
**SECURITY.md**.

## Start it (one command)

| | macOS / Linux / WSL | Windows PowerShell |
|---|---|---|
| Start development stack | `make up` | `.\tasks.ps1 up` |
| Create an admin account | `make superuser` | `.\tasks.ps1 superuser` |
| Stop | `make down` | `.\tasks.ps1 down` |

The first start creates `.env` from `.env.example` with a random secret key, builds the image,
runs database migrations and creates the storage bucket.

If PowerShell blocks the script: `powershell -ExecutionPolicy Bypass -File .\tasks.ps1 up`

## Addresses

| What | URL |
|---|---|
| Health Depot | https://localhost |
| Admin (system administrators only) | https://localhost/admin/ |
| Email inbox (Mailpit — catches all outgoing email) | http://localhost:8025 |
| Health checks | https://localhost/health/live · https://localhost/health/ready |

Sign in with the admin account you created. On first sign-in every user sets up an
authenticator app (Google Authenticator, Microsoft Authenticator, Authy, 1Password, etc.)
and saves recovery codes. Add more users at **Users & access** (https://localhost/manage/users/).
After 5 wrong passwords an account is locked for 15 minutes; sessions end after 15 minutes idle.

### Browser certificate warning

Out of the box Caddy uses its own certificate, so your browser shows a warning the first time
(click "Advanced → Continue"). To remove the warning, run once:

```
make certs            # or: .\tasks.ps1 certs
```

then set this line in `.env` and restart (`make down && make up`):

```
CADDY_TLS=/certs/localhost.pem /certs/localhost-key.pem
```

### Port already in use?

Windows sometimes uses ports 80/443. Change `HTTP_PORT` / `HTTPS_PORT` in `.env`
(e.g., 8080 / 8443), add the port to `CSRF_TRUSTED_ORIGINS` (e.g., `https://localhost:8443`),
and open https://localhost:8443.

## The services

| Service | What it is | Future AWS equivalent |
|---|---|---|
| `proxy` | Caddy — HTTPS in front of the app and file storage | Application Load Balancer + WAF |
| `web` | Django app (dev: auto-reload; prod: Gunicorn) | ECS Fargate service |
| `worker` | Background jobs and scheduled tasks | Second ECS Fargate service |
| `migrate` | One-off: migrations + bucket setup | One-off ECS task |
| `db` | PostgreSQL 16 | Amazon RDS for PostgreSQL |
| `s3` | SeaweedFS (S3-compatible storage) | Amazon S3 |
| `mailpit` | Email catcher | Amazon SES |
| `tailwind` | Dev only — rebuilds CSS when templates change | (built into the image) |

## Everyday commands

| Task | make | PowerShell |
|---|---|---|
| Run tests | `make test` | `.\tasks.ps1 test` |
| Lint + type check | `make lint` | `.\tasks.ps1 lint` |
| Auto-format | `make fmt` | `.\tasks.ps1 fmt` |
| Logs | `make logs` | `.\tasks.ps1 logs` |
| Container status | `make ps` | `.\tasks.ps1 ps` |
| Django shell | `make shell` | `.\tasks.ps1 shell` |
| Production-like stack | `make up-prod` / `make down-prod` | `.\tasks.ps1 up-prod` / `down-prod` |
| Deployment checks | `make check` | `.\tasks.ps1 check` |
| Full stack check | `make check-stack` (add `STACK=prod`) | `.\tasks.ps1 check-stack [-Prod]` |
| Load / reset demo data | `make seed-demo` / `make reset-demo` | `.\tasks.ps1 seed-demo` / `reset-demo` |
| Security scans | `make security` / `make scan` | `.\tasks.ps1 security` / `scan` |
| Proposal screenshots | `python scripts/screenshots.py` (needs Playwright) | same |
| Back up DB + files | `make backup` (add `STACK=prod`) | `.\tasks.ps1 backup [-Prod]` |
| Restore | `make restore BACKUP=backups/<timestamp>` | `.\tasks.ps1 restore -Backup backups\<timestamp>` |

Development and production-like stacks use separate data volumes.

## Project layout

See `CLAUDE.md` (project brief, rules and folder structure) and `docs/DATA_MODEL.md`.

## Configuration

Every setting is an environment variable — see `.env.example`. The same image runs locally
and, later, in AWS GovCloud with only environment changes (see CLAUDE.md section 6).

## how go log in
The first build takes about 5–10 minutes. After that, open https://localhost and log in with staff@demo.healthdepot.local, password HealthDepot-Demo-2026!. For the 2-factor code, add the key HEALTHDEPOTDEMOKEYCALVERTCOUNTYM to your authenticator app.