# Health Depot — Security Controls

Status as of October 2026 (MVP / demo build). The first part describes controls that are
**implemented and tested in this codebase**, in language that can be reused in the proposal
(RFP 3.9). The last part lists what a production deployment still needs.

> The demo environment contains **synthetic data only**. No real client information has been
> entered into this system.

## 1. Controls in place

### Identity and access
- **Multi-factor authentication for every user.** Sign-in requires email + password, then a
  time-based one-time code from an authenticator app (TOTP, RFC 6238). Users cannot reach any
  page until they enroll; one-time recovery codes are issued at enrollment. The Django admin
  uses the same login, so MFA applies there too. Administrators can reset a lost
  authenticator; the reset is audit-logged.
- **No self-registration.** Accounts are created by system administrators.
- **Password policy:** minimum 12 characters, checked against common-password and
  user-attribute lists. Passwords are hashed with PBKDF2-SHA256 (FIPS-approved algorithm).
- **Account lockout:** after 5 failed sign-ins for an account (or 20 from one IP address) in 15
  minutes, sign-in is blocked for that window.
- **Session security:** sessions end after 15 minutes of inactivity and when the browser
  closes; "remember me" is disabled; session and CSRF cookies are `Secure`, `HttpOnly` and
  `SameSite=Lax`.
- **Single sign-on ready:** the login screen and identity library (django-allauth) support
  Google Workspace SSO (SAML/OIDC); it is configured at implementation.

### Authorization (least privilege)
- **Five roles:** System administrator, Program manager, Staff, Read-only (leadership),
  Community partner user.
- **Program-level segmentation (RFP 3.7):** health department users see clients, referrals and
  cases only in programs they are assigned to, with edit or view-only access per program.
  Read-only users can never change records, comment or send messages.
- **Partner isolation:** partner users see only referrals sent to or from their own
  organization — never other partners' clients, internal staff comments or case notes.
- **One enforcement point:** every query for client data goes through a central, tested rule set
  (`apps/accounts/access.py`). Records outside a user's scope return "not found" (HTTP 404), so
  record IDs cannot be probed. Record IDs are random UUIDs, not sequential numbers.
- 130+ automated tests (131 at last run) cover these rules, including cross-program and cross-partner access
  attempts.

### Audit logging
- **Append-only audit log** of sign-ins (successful and failed), sign-outs, MFA enrollment and
  resets, role and program-access changes, and every create, view, update, delete and export
  of client records. Entries record who, what, when, IP address and a request ID.
- Entries **cannot be edited or deleted** through the application or admin site.
- The log stores **which fields changed, never the values**, so it contains no health
  information. Each entry is also written as a structured JSON log line for central log
  collection (e.g., Amazon CloudWatch).
- Administrators can search and filter the audit log in the app.

### Data protection
- **Encryption in transit:** all browser traffic uses HTTPS (TLS 1.2+) with HSTS; HTTP is
  redirected to HTTPS.
- **No health information outside the application:** notification emails say only that
  something changed and link to the secure sign-in page — no names, reference numbers or
  details. Secure messages between organizations stay inside Health Depot.
- **No PHI in URLs or logs:** record URLs use random IDs; web-server access logs record paths
  without query strings (so searches are not logged); application logs never include
  request bodies.
- **Private file storage:** uploaded documents and logos are stored in private object storage
  (S3 API) under random names; downloads use presigned links that expire after 5 minutes and
  are audit-logged. Uploads are checked by file content (PDF, Word, PNG, JPEG only; SVG is
  rejected) and size-limited.
- **Data ownership and export:** reports export to Excel/CSV (every export is audit-logged;
  spreadsheet formula injection is neutralized). Database and file backups export all data.
- **Backups:** `make backup` / `.\tasks.ps1 backup` creates a full database dump and file
  storage copy; restore has been tested end to end.

### Application security
- **Content Security Policy:** scripts load only from the application itself; no inline
  scripts, no third-party hosts, framing blocked (`frame-ancestors 'none'`), `object-src 'none'`.
- Additional headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin`, `Permissions-Policy` (camera, microphone, location off),
  `Cross-Origin-Opener-Policy`, and `Cache-Control: no-store` on signed-in pages.
- **CSRF protection** on every form and background request.
- **Rate limiting** on the public referral form (10 submissions/minute/IP) plus a hidden
  honeypot field against bots.
- **Input validation:** all input goes through server-side form validation, including
  dynamically built intake forms.
- **No external dependencies at runtime:** all JavaScript, CSS and fonts are bundled with the
  app (verified: a full browser scan of every page made zero requests to outside hosts). The
  app works offline and in restricted government networks.
- **Django deployment check** (`manage.py check --deploy`) passes with production settings.

### Containers and supply chain
- One hardened image for web, worker and migrations: pinned `python:3.12-slim` base, OS
  packages upgraded at build, runs as a **non-root user**, **read-only root filesystem** (only
  `/tmp` is writable), all Linux capabilities dropped, `no-new-privileges`, health checks.
- No secrets in images; all configuration comes from environment variables.
- Dependencies are pinned in `uv.lock` / `package-lock.json`.
- **Scans (October 18, 2026):**
  - `pip-audit` — no known vulnerabilities in Python dependencies.
  - `bandit` — no unresolved findings (reviewed exceptions are marked in code).
  - **Trivy** image scan — **0 fixable HIGH/CRITICAL** vulnerabilities, no secrets found.
  - **SBOM** (SPDX, Syft): `security/sbom-health-depot.spdx.json` (128 packages).
- Run them yourself: `make security` and `make scan` (or the `tasks.ps1` equivalents).

### Portability to AWS GovCloud
- No hard-coded AWS regions, account IDs, ARNs or endpoints (enforced by a test).
- AWS credentials come from the standard credential chain (IAM roles in AWS — no keys).
- FIPS endpoints can be enabled with `AWS_USE_FIPS_ENDPOINT=true`.
- FIPS-approved algorithms only for security functions: PBKDF2-SHA256 passwords,
  HMAC-SHA1/SHA-256 (TOTP uses HMAC-SHA1, approved for HMAC under FIPS 198-1), TLS 1.2+.

## 2. Known limitations of the demo build

| Item | Detail | Plan |
|---|---|---|
| Alpine.js needs `'unsafe-eval'` in the CSP | Small interactive widgets (menus, tabs) evaluate expressions. Inline scripts are still blocked. | Move to Alpine's CSP build or plain JS before production. |
| Local storage is not encrypted at rest | Docker volumes on the demo laptop. | Production uses KMS-encrypted RDS and S3. |
| Rate-limit counters use the database cache | Counts can be slightly approximate under heavy load. | Use a dedicated cache (ElastiCache/Redis) in production. |
| Demo credentials are published | Shared demo password and authenticator key in DEMO_SCRIPT.md. | Demo only; `DEMO_MODE` is off in real deployments. |
| arm64 image build | Dockerfile has no architecture-specific steps and all base images are multi-arch, but the arm64 build was not executed in this build environment. | Run `make build-multiarch` on a machine with Docker Buildx. |

## 3. Production gaps (to complete before go-live)

1. **Hosting in AWS GovCloud (US)** (or commercial AWS) under a signed **AWS Business Associate
   Addendum**; HIPAA-eligible services only (see DEPLOYMENT_AWS_GOVCLOUD.md).
2. **Encryption at rest with AWS KMS** for the database (RDS), file storage (S3), backups and logs.
3. **SOC 2 Type II program** for Columbia Technology LLC (Type I at go-live, Type II within ~12
   months), inheriting AWS GovCloud's FedRAMP High and SOC 2 controls for infrastructure.
4. **Independent penetration test** before go-live and annually.
5. **FIPS 140-validated cryptographic modules** in the container base image (e.g., a
   FIPS-enabled OS image) and FIPS endpoints for all AWS calls.
6. **NIST SP 800-53 control mapping** and HIPAA Security Rule risk assessment; incident
   response and breach notification procedures.
7. Centralized logging and alerting (CloudWatch, GuardDuty, Security Hub); log retention per
   Maryland records requirements.
8. Google Workspace SSO configuration, BAA review for any email/SMS provider, and data
   retention and disposal schedules agreed with CCHD.
9. Business continuity: Multi-AZ database, cross-region backups, documented RPO/RTO, restore
   drills.
