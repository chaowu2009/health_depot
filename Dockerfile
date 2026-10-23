# syntax=docker/dockerfile:1.7
# Health Depot — one image, three commands: web, worker, migrate.
# Builds for linux/amd64 and linux/arm64 (docker buildx build --platform linux/amd64,linux/arm64 .)
#
# Networks that inspect TLS (common in government and corporate offices) can pass their CA
# bundle at build time without baking it into the image:
#   docker build --secret id=extra_ca,src=/path/to/ca-bundle.pem .

ARG PYTHON_IMAGE=python:3.12.15-slim
ARG NODE_IMAGE=node:22.23.3-alpine

# --- Stage 1: build Tailwind CSS (Node is used only here, never in the runtime image) -------
FROM ${NODE_IMAGE} AS css
WORKDIR /build
COPY package.json package-lock.json* ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca; fi; \
    npm ci --no-audit --no-fund
COPY src/assets/tailwind.css src/assets/tailwind.css
COPY src/templates src/templates
COPY src/apps src/apps
RUN npx @tailwindcss/cli -i src/assets/tailwind.css -o /build/app.css --minify

# --- Stage 2: Python dependencies (production) ---------------------------------------------
FROM ${PYTHON_IMAGE} AS deps
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    pip install "uv==0.11.32" && uv sync --frozen --no-dev --no-install-project

# --- Stage 3: Python dependencies including dev tools (tests, lint) ------------------------
FROM deps AS deps-dev
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-install-project

# --- Shared runtime base -------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings \
    PYTHONPATH=/app/src
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --chmod=0755 scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chmod=0755 scripts/healthcheck.py /usr/local/bin/healthcheck.py
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "/usr/local/bin/healthcheck.py"]
ENTRYPOINT ["entrypoint.sh"]

# --- Development image (code is mounted by compose.yaml) -----------------------------------
FROM base AS dev
COPY --from=deps-dev /opt/venv /opt/venv
USER app
CMD ["dev"]

# --- Production image ----------------------------------------------------------------------
FROM base AS runtime
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app src/ /app/src/
COPY --from=css --chown=app:app /build/app.css /app/src/static/css/app.css
# Collect static files at build time so the container can run with a read-only filesystem.
RUN DJANGO_SECRET_KEY=build-only DATABASE_URL=sqlite:////tmp/build.db \
    AWS_STORAGE_BUCKET_NAME=build EMAIL_HOST=localhost \
    python /app/src/manage.py collectstatic --noinput --verbosity 0
USER app
CMD ["web"]
