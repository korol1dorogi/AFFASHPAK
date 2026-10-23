"""Django settings. Every value comes from the environment (.env locally, real env in prod).

DJANGO_DEBUG=0 turns on the production security profile; `manage.py check --deploy`
must pass with it (CI runs that check).
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"Environment variable {name} is required")
    return value


def env_bool(name: str, default: bool) -> bool:
    return env(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    return int(env(name, str(default)))


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
ADMIN_URL = env("DJANGO_ADMIN_URL", "admin/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.accounts",
    "apps.business",
    "apps.products",
    "apps.applications",
    "apps.documents",
    "apps.notifications",
    "apps.assistant",
    "apps.integrations",
    "apps.pipeline",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",  # first: every log line carries the request_id
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "alfa"),
        "USER": env("POSTGRES_USER", "alfa"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Dev compose bind-mounts the source over /app, so the image's /app/media is hidden
# and the container user cannot create it. Point MEDIA_ROOT at a writable path there.
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

# --- Uploads: hard limits (per-file checks live in the documents app) ---
# The Django request cap sits just above the per-file limit so an oversized file
# reaches the documents app and can answer 413 instead of being cut off earlier.
UPLOAD_MAX_FILE_BYTES = env_int("UPLOAD_MAX_FILE_BYTES", 10 * 1024 * 1024)
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int(
    "DJANGO_DATA_UPLOAD_MAX_BYTES",
    UPLOAD_MAX_FILE_BYTES + 64 * 1024,
)
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE
# Stored uploads are data, never programs: no execute bit, not readable by other users.
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

# --- Sessions + CSRF on a single origin (no CORS, no JWT) ---
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 8
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it to send X-CSRFToken
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if not DEBUG:
    # Behind Caddy, which terminates TLS and sets X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SECURE_REDIRECT_EXEMPT = [r"^api/health$"]  # container healthcheck over plain HTTP
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    # Preload needs a manual submission to browser lists; not for a hackathon stand.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# --- Cache ---
# Throttle counters must be shared by all gunicorn workers: LocMemCache keeps one per process,
# so 3 workers let 3× the limit through. The table is created by a migration
# (apps/core/migrations), so `migrate` alone is enough; Redis is only the Celery broker.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

# --- DRF ---
# Per-IP for anonymous, per-user otherwise. The client IP is the last X-Forwarded-For hop,
# the one Caddy appends (NUM_PROXIES); without the header DRF falls back to REMOTE_ADDR.
# Caddy drops a client-sent X-Forwarded-For, and the stand publishes no backend port.
# demo_login is separate from login: on the stand the jury switches personas from one IP,
# while password login stays strict (docs/deploy.md).
THROTTLE_DEFAULTS = {
    "anon": "60/min",
    "user": "600/min",
    "login": "10/min",
    "demo_login": "120/min",
    "assistant": "20/min",
}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "apps.core.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        scope: env(f"THROTTLE_{scope.upper()}", rate) for scope, rate in THROTTLE_DEFAULTS.items()
    },
    "NUM_PROXIES": env_int("DRF_NUM_PROXIES", 1),
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "COERCE_DECIMAL_TO_STRING": True,
}

# --- Bank queue SLA (XP4, apps/applications/sla.py) ---
# Hours an application may stay in a status where the bank acts. Overrides of the defaults in
# sla.py, e.g. SLA_HOURS="manual_review=24,submitted=1"; statuses not listed keep the default.
# Kept as text and parsed in sla.py: a broken item is ignored with a warning, never a crash.
APPLICATION_SLA_HOURS = env("SLA_HOURS", "")

# --- AI assistant (see apps/assistant/llm) ---
LLM_PROVIDER = env("LLM_PROVIDER", "mock")
LLM_BASE_URL = env("LLM_BASE_URL", "")
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_MODEL = env("LLM_MODEL", "")
LLM_TIMEOUT_SECONDS = env_int("LLM_TIMEOUT_SECONDS", 30)
# Model ↔ tools round trips per answer (AI2); each tool call of a model without parallel calls
# is a step of its own, so 4 is enough for the bank summary (two tools) with room to spare.
LLM_MAX_STEPS = env_int("LLM_MAX_STEPS", 4)
# Guardrails (AI22): block — a broken answer is regenerated once, then replaced by a safe one;
# log — the answer goes out as is and only the trigger is logged (to measure a model first).
GUARDRAILS_MODE = env("GUARDRAILS_MODE", "block")

# --- Demo stand: /api/demo/* and the seed of personas exist only with DEMO_MODE=1 ---
DEMO_MODE = env_bool("DEMO_MODE", default=False)

# --- Pipeline: Celery worker behind Redis when CELERY_BROKER_URL is set (compose), else
# in-process. pytest always runs in-process, even inside a container that has a broker set,
# so `docker compose run --rm backend pytest` needs no Redis. ---
TESTING = "pytest" in sys.modules
PIPELINE_ENABLED = env_bool("PIPELINE_ENABLED", default=True)
CELERY_BROKER_URL = "" if TESTING else env("CELERY_BROKER_URL", "")
CELERY_TASK_ALWAYS_EAGER = not CELERY_BROKER_URL
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = True  # nobody reads task results: the application row is the state
# A task is acknowledged after it ran; a worker process killed mid-task puts it back.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 600}
# Redis down at submit: fail within ~3 s and fall back to in-process (apps/pipeline/tasks.py).
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_PUBLISH_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.5}

# --- Case data: read-only mount, never inside the repo ---
CASE_DATA_DIR = Path(env("CASE_DATA_DIR", "/case-data"))

# --- Contract (docs/openapi.yaml) used by tests to validate responses ---
OPENAPI_SPEC_PATH = Path(env("OPENAPI_SPEC_PATH", str(BASE_DIR.parent / "docs" / "openapi.yaml")))

# --- Logs (OPS5): JSON lines by default, `LOG_FORMAT=text` for a human at a terminal. Every line,
# the worker's too (config/celery.py), carries request_id / application_id / user_id; the access
# log is one line per request from apps/core/middleware.py. ---
LOG_FORMAT = "text" if env("LOG_FORMAT", "json").lower() == "text" else "json"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"context": {"()": "apps.core.logs.ContextFilter"}},
    "formatters": {
        "json": {"()": "apps.core.logs.JsonFormatter"},
        "text": {"()": "apps.core.logs.TextFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["context"],
            "formatter": LOG_FORMAT,
        }
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        # runserver's own access line repeats ours, with the query string
        "django.server": {"level": "WARNING"},
    },
}
