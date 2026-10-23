"""Health Depot settings.

Every environment-specific value comes from environment variables (12-factor), so the same
container image runs locally (Docker Compose) and later in AWS GovCloud with only env changes.
See .env.example for the full list.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent  # src/

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost"]),
    CSRF_TRUSTED_ORIGINS=(list, ["https://localhost"]),
    SECURE_SSL_REDIRECT=(bool, True),
    SESSION_IDLE_TIMEOUT_SECONDS=(int, 900),
    AWS_S3_ENDPOINT_URL=(str, ""),
    AWS_S3_REGION_NAME=(str, ""),
    AWS_S3_ADDRESSING_STYLE=(str, "path"),
    AWS_S3_PRESIGNED_EXPIRY_SECONDS=(int, 300),
    AWS_USE_FIPS_ENDPOINT=(bool, False),
    EMAIL_PORT=(int, 1025),
    EMAIL_USE_TLS=(bool, False),
    EMAIL_USE_SSL=(bool, False),
    LOG_LEVEL=(str, "INFO"),
    LOG_FORMAT=(str, "json"),
    DEMO_BANNER=(bool, True),
)

# --- Core -------------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
APP_NAME = "Health Depot"
# Public address used in referral links, QR codes and email links.
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="https://localhost").rstrip("/")
# Demo tools (reset demo data button). Never enable in production.
DEMO_MODE = env.bool("DEMO_MODE", default=False)
DEMO_BANNER = env("DEMO_BANNER")

INSTALLED_APPS = [
    "apps.core.admin_config.HealthDepotAdminConfig",  # Django admin restricted to SYSTEM_ADMIN
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "storages",
    "django_ratelimit",
    "csp",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    # Health Depot apps
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.clients",
    "apps.forms_builder",
    "apps.referrals",
    "apps.messaging",
    "apps.cases",
    "apps.notifications",
    "apps.reports",
    "apps.audit",
    "apps.phase2",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "apps.core.security.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
    "apps.accounts.middleware.RequireMFAMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.app_context",
            ],
            "builtins": ["apps.core.templatetags.ui"],
        },
    },
]

# --- Database (PostgreSQL 16; RDS-compatible) ---------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Database cache: shared across web and worker containers (used by rate limiting later).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

# --- Auth (django-allauth + MFA) ------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "account_login"
ACCOUNT_ADAPTER = "apps.accounts.adapters.HealthDepotAccountAdapter"
ACCOUNT_FORMS = {"login": "apps.accounts.forms.LoginForm"}
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # staff accounts are created by administrators
ACCOUNT_SESSION_REMEMBER = False  # never "remember me" on shared public-health computers
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
ACCOUNT_PREVENT_ENUMERATION = True
# Temporary lockout: after 5 failed logins for an account (or 20 from one IP) in 15 minutes.
ACCOUNT_RATE_LIMITS = {
    "login_failed": env("ACCOUNT_LOGIN_FAILED_LIMIT", default="20/15m/ip,5/15m/key"),
}
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Health Depot"
MFA_RECOVERY_CODE_COUNT = 10
# Every user must enroll an authenticator app before using the system (RFP 3.9).
MFA_REQUIRED = env.bool("MFA_REQUIRED", default=True)
# Audit: take the client IP from X-Forwarded-For set by our proxy (Caddy now, AWS ALB later).
AUDIT_TRUST_X_FORWARDED_FOR = env.bool("AUDIT_TRUST_X_FORWARDED_FOR", default=True)

# FIPS-friendly: PBKDF2-SHA256 only (no bcrypt/argon2).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Sessions & security -------------------------------------------------------------------
SESSION_COOKIE_AGE = env("SESSION_IDLE_TIMEOUT_SECONDS")
SESSION_SAVE_EVERY_REQUEST = True  # sliding idle timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True

# TLS terminates at the proxy (Caddy locally, AWS ALB later). Trust its X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = False
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
SECURE_REDIRECT_EXEMPT = [r"^health/"]  # load balancer / container health checks use HTTP
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"


# Content Security Policy (django-csp). No inline scripts and no third-party hosts.
# 'unsafe-eval' is required by Alpine.js expressions (documented in SECURITY.md).
def _origin(url: str) -> str:
    from urllib.parse import urlparse

    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


_storage_origin = _origin(env("AWS_S3_PUBLIC_ENDPOINT_URL", default="")) or env(
    "CSP_STORAGE_ORIGIN", default=""
)
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-eval'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", *([_storage_origin] if _storage_origin else [])],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'"],
        "base-uri": ["'self'"],
        "object-src": ["'none'"],
    }
}

# --- I18N ----------------------------------------------------------------------------------
FORMS_URLFIELD_ASSUME_HTTPS = True
LANGUAGE_CODE = "en-us"
LANGUAGES = [("en", "English"), ("es", "Español")]
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

# --- Static files (vendored; served by WhiteNoise — no CDNs) --------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# --- File storage: S3 API only (SeaweedFS locally, Amazon S3 later) --------------------------
# Credentials come from the default AWS credential chain (env vars locally; IAM task role in
# AWS). Never hard-code regions, endpoints or keys.
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL") or None
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME") or None
AWS_S3_ADDRESSING_STYLE = env("AWS_S3_ADDRESSING_STYLE")
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True  # private objects; presigned URLs only
AWS_QUERYSTRING_EXPIRE = env("AWS_S3_PRESIGNED_EXPIRY_SECONDS")
AWS_S3_USE_SSL = True
# Public endpoint for browser-facing presigned URLs (locally: storage through the proxy).
# Leave empty in AWS.
AWS_S3_PUBLIC_ENDPOINT_URL = env("AWS_S3_PUBLIC_ENDPOINT_URL", default="")
AWS_USE_FIPS_ENDPOINT = env("AWS_USE_FIPS_ENDPOINT")  # read by boto3 from the environment

STORAGES = {
    "default": {"BACKEND": "apps.core.storage.PrivateS3Storage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- Email: standard SMTP (Mailpit locally, Amazon SES SMTP later) -------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_USE_SSL = env("EMAIL_USE_SSL")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Health Depot <no-reply@localhost>")

# --- Logging: structured JSON to stdout ------------------------------------------------------
from config.logging import build_logging_config  # noqa: E402

LOGGING = build_logging_config(level=env("LOG_LEVEL"), fmt=env("LOG_FORMAT"))

# HSTS preload only makes sense for a real public domain (decide at production launch).
# Rate limiting uses the shared database cache (works across containers, no extra service).
# Counts may be slightly approximate under heavy concurrency; acceptable for this workload.
SILENCED_SYSTEM_CHECKS = ["security.W021", "django_ratelimit.W001", "django_ratelimit.E003"]
