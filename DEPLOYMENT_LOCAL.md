# Health Depot — Local Deployment (Docker)

The whole system runs on one computer with Docker. Use the **production-like** stack for
demos and the **development** stack while building.

| | Production-like (demos) | Development |
|---|---|---|
| Start | `.\tasks.ps1 up-prod` · `make up-prod` | `.\tasks.ps1 up` · `make up` |
| Stop | `.\tasks.ps1 down-prod` · `make down-prod` | `.\tasks.ps1 down` · `make down` |
| Web server | Gunicorn, built image, read-only containers | Django dev server, live code reload |
| Data | Its own volumes (`health-depot-prod_*`) | Its own volumes (`health-depot_*`) |

Run one stack at a time (both use ports 80/443/9443).

## First start

1. Install Docker Desktop (Windows: WSL 2 backend), 4+ CPUs and 8 GB memory for Docker.
2. In the project folder: `.\tasks.ps1 up-prod` (first build takes a few minutes).
3. The `migrate` step creates the database, the storage bucket and — because `DEMO_MODE` is on
   in the local compose files — loads the synthetic demo data automatically.
4. Check everything: `.\tasks.ps1 check-stack -Prod` · `make check-stack STACK=prod`
   (database, storage, demo data, email delivery, demo logins).
5. Open **https://localhost** (accept the certificate warning, or run `.\tasks.ps1 certs`
   once — see README). Email inbox: **http://localhost:8025**.

Demo logins and the 7-minute walkthrough: **DEMO_SCRIPT.md**.

### Optional: https://demo.local
Add this line to your hosts file (Windows: `C:\Windows\System32\drivers\etc\hosts`, edit as
administrator; macOS/Linux: `/etc/hosts`), then open https://demo.local:
```
127.0.0.1   demo.local
```

## Everyday operations

| Task | Windows | macOS / Linux |
|---|---|---|
| Container status | `.\tasks.ps1 ps -Prod` | `make ps STACK=prod` |
| Logs | `.\tasks.ps1 logs -Prod` | `make logs STACK=prod` |
| Reset demo data | `.\tasks.ps1 reset-demo -Prod` or in-app **Users & access → Tools** | `make reset-demo STACK=prod` |
| Create your own admin | `.\tasks.ps1 superuser` | `make superuser` |
| Back up | `.\tasks.ps1 backup -Prod` | `make backup STACK=prod` |
| Restore | `.\tasks.ps1 restore -Prod -Backup backups\<timestamp>` | `make restore STACK=prod BACKUP=backups/<timestamp>` |
| Security scans | `.\tasks.ps1 security`, `.\tasks.ps1 scan` | `make security`, `make scan` |

Backups go to `backups/<timestamp>/` (database dump `db.sql.gz` + `storage/` files). A full
restore was tested: delete data → restore → data back.

## Offline demos
The app makes **no requests to outside websites** — all scripts, styles and fonts are inside
the image (verified by a browser scan of every page). Once images are built, you can unplug
the network and demo from the laptop.

## Troubleshooting

| Problem | Fix |
|---|---|
| `running scripts is disabled` (PowerShell) | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or run `powershell -ExecutionPolicy Bypass -File .\tasks.ps1 up-prod` |
| Port 80/443 already in use | Set `HTTP_PORT=8080`, `HTTPS_PORT=8443` in `.env`; add `https://localhost:8443` to `CSRF_TRUSTED_ORIGINS`; open https://localhost:8443 |
| Browser certificate warning | `.\tasks.ps1 certs`, then set `CADDY_TLS=/certs/localhost.pem /certs/localhost-key.pem` in `.env` and restart |
| A container keeps restarting | `docker compose -f compose.prod.yaml logs <service>` — paste the output to Claude with the "Docker problem" prompt |
| Two-factor code rejected | Each code works once; wait for the next one. Check your computer's clock is correct. |
| Locked out after wrong passwords | Wait 15 minutes, or `.\tasks.ps1 reset-demo` |
| Build fails on a company network with TLS inspection | Set `EXTRA_CA_FILE=C:/path/to/company-ca.pem` in `.env` and rebuild |
| Start completely fresh | `docker compose -f compose.prod.yaml down -v` (deletes that stack's data), then `up-prod` |
