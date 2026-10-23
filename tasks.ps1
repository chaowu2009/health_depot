<#
  Health Depot — Windows helper (same commands as the Makefile).
  Usage:  .\tasks.ps1 up        (if blocked: powershell -ExecutionPolicy Bypass -File .\tasks.ps1 up)
  Commands: env, certs, up, up-prod, down, down-prod, logs, ps, migrate, shell, superuser,
            seed-demo, reset-demo, check-stack, code, security, scan,
            test, lint, fmt, check, backup [-Prod], restore -Backup backups\<timestamp> [-Prod]
#>
param(
  [Parameter(Position = 0)][string]$Command = "help",
  [string]$Backup = "",
  [switch]$Prod
)
$ErrorActionPreference = "Stop"
$composeFile = if ($Prod) { "compose.prod.yaml" } else { "compose.yaml" }
function Compose { docker compose -f $composeFile @args; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
function DevRun { docker compose -f compose.yaml run --rm --no-deps web @args; if ($LASTEXITCODE) { exit $LASTEXITCODE } }

function Assert-Docker {
  # Windows PowerShell turns native stderr into errors when ErrorActionPreference=Stop,
  # so relax it just for this probe.
  $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  $null = & docker info --format "{{.ServerVersion}}" 2>&1
  $code = $LASTEXITCODE; $ErrorActionPreference = $prev
  if ($code) {
    Write-Host "Docker Desktop is not running or still starting." -ForegroundColor Yellow
    Write-Host "Start Docker Desktop, wait until it says 'Engine running', then try again."
    Write-Host "If it stays stuck: right-click the Docker icon > Restart, or run 'wsl --shutdown' and reopen Docker Desktop."
    exit 1
  }
}

function Show-DemoCode {
  # Prints the current 2-factor code for the demo accounts (RFC 6238 TOTP, demo key only).
  $secret = "HEALTHDEPOTDEMOKEYCALVERTCOUNTYM"
  $alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
  $bits = ($secret.ToCharArray() | ForEach-Object { [Convert]::ToString($alphabet.IndexOf($_), 2).PadLeft(5, "0") }) -join ""
  $key = for ($i = 0; $i + 8 -le $bits.Length; $i += 8) { [Convert]::ToByte($bits.Substring($i, 8), 2) }
  $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  $counter = [BitConverter]::GetBytes([Int64][Math]::Floor($now / 30))
  if ([BitConverter]::IsLittleEndian) { [Array]::Reverse($counter) }
  $hmac = New-Object System.Security.Cryptography.HMACSHA1 (,[byte[]]$key)
  $hash = $hmac.ComputeHash($counter)
  $o = $hash[19] -band 15
  $num = (($hash[$o] -band 127) * 16777216) + ($hash[$o + 1] * 65536) + ($hash[$o + 2] * 256) + $hash[$o + 3]
  $code = ($num % 1000000).ToString("000000")
  Write-Host "Demo 2-factor code: $code  (valid for $(30 - ($now % 30)) more seconds; each code works once)"
}

function Ensure-Env {
  if (-not (Test-Path .env)) {
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $key = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd("=")
    (Get-Content .env.example -Raw).Replace("DJANGO_SECRET_KEY=change-me", "DJANGO_SECRET_KEY=$key") |
      Set-Content .env -NoNewline -Encoding utf8
    Write-Host "Created .env"
  }
}

switch ($Command) {
  "env"       { Ensure-Env }
  "code"      { Show-DemoCode }
  "certs"     {
    mkcert -install
    mkcert -cert-file deploy/caddy/certs/localhost.pem -key-file deploy/caddy/certs/localhost-key.pem localhost demo.local 127.0.0.1
    Write-Host 'Now set in .env:  CADDY_TLS=/certs/localhost.pem /certs/localhost-key.pem'
  }
  "up"        { Assert-Docker; Ensure-Env; docker compose -f compose.yaml up -d --build; if ($LASTEXITCODE) { exit $LASTEXITCODE }; Write-Host "App: https://localhost   Email: http://localhost:8025" }
  "up-prod"   { Assert-Docker; Ensure-Env; docker compose -f compose.prod.yaml up -d --build; if ($LASTEXITCODE) { exit $LASTEXITCODE }; Write-Host "App: https://localhost" }
  "down"      { docker compose -f compose.yaml down }
  "down-prod" { docker compose -f compose.prod.yaml down }
  "logs"      { Compose logs -f --tail=100 }
  "ps"        { Compose ps }
  "migrate"   { Compose run --rm migrate }
  "shell"     { Compose exec web python /app/src/manage.py shell }
  "superuser" { Compose exec web python /app/src/manage.py createsuperuser }
  "seed-demo" { Compose exec web python /app/src/manage.py seed_demo }
  "reset-demo" { Compose exec web python /app/src/manage.py seed_demo --reset }
  "test"      { docker compose -f compose.yaml up -d db s3; DevRun pytest }
  "lint"      { DevRun sh -c "ruff check . && ruff format --check . && mypy src" }
  "fmt"       { DevRun sh -c "ruff check --fix . && ruff format ." }
  "security"  { DevRun sh -c "bandit -q -r src scripts -x '*/migrations/*,*/tests/*' -c pyproject.toml && pip-audit --local --strict" }
  "scan"      {
    docker compose -f compose.prod.yaml build web
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.67.2 image --scanners vuln,secret --severity HIGH,CRITICAL --ignore-unfixed health-depot:latest
    New-Item -ItemType Directory -Force -Path security | Out-Null
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock anchore/syft:v1.33.0 health-depot:latest -o spdx-json | Out-File -Encoding utf8 security/sbom-health-depot.spdx.json
  }
  "check-stack" { Compose ps; Compose exec web python /app/src/manage.py stack_check }
  "check"     { DevRun sh -c "cd src && DEBUG=false python manage.py check --deploy" }
  "backup"    {
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    New-Item -ItemType Directory -Force -Path "backups/$ts" | Out-Null
    Compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists | gzip > /tmp/db.sql.gz'
    Compose cp db:/tmp/db.sql.gz "backups/$ts/db.sql.gz"
    Compose run --rm --no-deps -v "${PWD}/backups:/backups" --entrypoint python web /app/src/manage.py backup_storage "/backups/$ts/storage"
    Write-Host "Backup written to backups/$ts"
  }
  "restore"   {
    if (-not $Backup) { Write-Host "Usage: .\tasks.ps1 restore -Backup backups\<timestamp>"; exit 1 }
    $name = Split-Path $Backup -Leaf
    Compose cp "$Backup/db.sql.gz" db:/tmp/restore.sql.gz
    Compose exec -T db sh -c 'gunzip -c /tmp/restore.sql.gz | psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
    Compose run --rm --no-deps -v "${PWD}/backups:/backups" --entrypoint python web /app/src/manage.py restore_storage "/backups/$name/storage"
    Write-Host "Restored from $Backup"
  }
  default     { Get-Content $PSCommandPath -TotalCount 8 | Select-Object -Skip 1 }
}
