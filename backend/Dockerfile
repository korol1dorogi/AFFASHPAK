# Build context: repo root (see docker-compose.yml and .dockerignore allowlist).
FROM python:3.12.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RUFF_CACHE_DIR=/tmp/ruff-cache \
    OPENAPI_SPEC_PATH=/docs/openapi.yaml

# Dev image installs requirements-dev.txt (compose passes it); prod uses requirements.txt.
ARG REQUIREMENTS=requirements.txt
ARG APP_UID=1000

WORKDIR /app

COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install -r "${REQUIREMENTS}"

RUN useradd --uid "${APP_UID}" --no-create-home --shell /usr/sbin/nologin app
# Mount points for named volumes (prod): created here so they inherit the app owner.
RUN mkdir -p /app/staticfiles /app/media && chown app:app /app/staticfiles /app/media

COPY docs/openapi.yaml /docs/openapi.yaml
COPY --chown=app:app backend/ /app/

USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--worker-class", "gthread", "--threads", "8", "--no-control-socket", "--access-logfile", "-"]
