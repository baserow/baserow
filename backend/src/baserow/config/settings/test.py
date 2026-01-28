# flake8: noqa: F405
import os
from copy import deepcopy
from unittest.mock import patch

from dotenv import dotenv_values
from fakeredis import FakeConnection, FakeServer

from baserow.config.settings.utils import str_to_bool

# Test environment configuration:
# - TEST_ENV_FILE: Optional env file for test settings (default: none)
# - DATABASE_*, REDIS_*, and MEDIA_ROOT vars can be passed via real env vars or TEST_ENV_FILE
# - All other settings are hardcoded in this file for consistency
#
# Example: DATABASE_URL=postgres://... just b test
# Example: TEST_ENV_FILE=.env.testing-local just b test

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load optional test env file
TEST_ENV_FILE = os.environ.get("TEST_ENV_FILE", "")
if TEST_ENV_FILE:
    TEST_ENV_VARS = dotenv_values(os.path.join(BASE_DIR, f"../../../{TEST_ENV_FILE}"))
else:
    TEST_ENV_VARS = {}

# Prefixes for vars that can be overridden via env vars (for DB/Redis configuration)
ALLOWED_ENV_PREFIXES = ("DATABASE_",)


def getenv_for_tests(key: str, default: str = "") -> str:
    """
    Get env var for tests:
    - DATABASE_* vars: check real env first, then TEST_ENV_FILE, then default
    - Other vars: only use TEST_ENV_FILE or default (never real env)
    """

    if key.startswith(ALLOWED_ENV_PREFIXES):
        # Allow real env vars for database and redis configuration
        return os.environ.get(key, TEST_ENV_VARS.get(key, default))
    else:
        # Block real env vars for other settings to ensure test consistency
        return TEST_ENV_VARS.get(key, default)


with patch("os.getenv", getenv_for_tests) as load_dotenv:
    # Import base settings with patched os.getenv to control which env vars are used
    from .base import *  # noqa: F403, F401

TESTS = True

# This is a hardcoded key for test runs only.
SECRET_KEY = "test_hardcoded_secret_key"  # nosec
SIMPLE_JWT["SIGNING_KEY"] = "test_hardcoded_jwt_signing_key"

CELERY_BROKER_BACKEND = "memory"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Set to 'off' to runs all migrations and disable the custom setup fixture that installs
# all pgPSQL functions. Default is 'on' for faster setup by skipping migrations.
BASEROW_TESTS_SETUP_DB_FIXTURE = str_to_bool(
    os.getenv("BASEROW_TESTS_SETUP_DB_FIXTURE", "on")
)
DATABASES["default"]["TEST"] = {
    "MIGRATE": not BASEROW_TESTS_SETUP_DB_FIXTURE,
}

# Open a second database connection that can be used to test transactions.
DATABASES["default-copy"] = deepcopy(DATABASES["default"])

USER_FILES_DIRECTORY = "user_files"
USER_THUMBNAILS_DIRECTORY = "thumbnails"
USER_THUMBNAILS = {"tiny": [21, 21]}

# Make sure that we are not using the `MEDIA_URL` environment variable because that
# could break the tests. They are expecting it to be 'http://localhost:8000/media/'
# because that is default value in `base.py`.
MEDIA_URL = "http://localhost:8000/media/"
MEDIA_ROOT = "/tmp/media-test/"  # noqa: S108


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
        "OPTIONS": {
            "CONNECTION_POOL_KWARGS": {
                "connection_class": FakeConnection,
                "server": FakeServer(),
            }
        },
        "KEY_PREFIX": "baserow-default-cache",
        "VERSION": VERSION,
    },
    GENERATED_MODEL_CACHE_NAME: {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "KEY_PREFIX": f"baserow-{GENERATED_MODEL_CACHE_NAME}-cache",
        "VERSION": None,
    },
}

# Disable the default throttle classes because ConcurrentUserRequestsThrottle is
# using redis and it will cause errors when running the tests.
# Look into tests.baserow.api.test_api_utils.py if you need to test the throttle
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []


BUILDER_PUBLICLY_USED_PROPERTIES_CACHE_TTL_SECONDS = 10
BUILDER_DISPATCH_ACTION_CACHE_TTL_SECONDS = 300

AUTO_INDEX_VIEW_ENABLED = False
# For ease of testing tests assume this setting is set to this. Set it explicitly to
# prevent any dev env config from breaking the tests.
BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED = "VIEWER"

# Ensure the tests never run with the concurrent middleware unless they add it in to
# prevent failures caused by the middleware itself
if "baserow.middleware.ConcurrentUserRequestsMiddleware" in MIDDLEWARE:
    MIDDLEWARE.remove("baserow.middleware.ConcurrentUserRequestsMiddleware")

PUBLIC_BACKEND_URL = "http://localhost:8000"
PUBLIC_WEB_FRONTEND_URL = "http://localhost:3000"
BASEROW_EMBEDDED_SHARE_URL = "http://localhost:3000"

FEATURE_FLAGS = "*"

# We must allow this because we're connecting to the same database in the tests.
BASEROW_PREVENT_POSTGRESQL_DATA_SYNC_CONNECTION_TO_DATABASE = False

# Make sure that default storage is used for the tests.
BASE_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
STORAGES["default"] = {"BACKEND": BASE_FILE_STORAGE}

BASEROW_LOGIN_ACTION_LOG_LIMIT = RateLimit.from_string("1000/s")

BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS = False
INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = False

CACHALOT_ENABLED = str_to_bool(os.getenv("CACHALOT_ENABLED", "false"))
if CACHALOT_ENABLED:
    CACHES[CACHALOT_CACHE] = {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "KEY_PREFIX": f"baserow-{CACHALOT_CACHE}-cache",
        "VERSION": None,
    }

    install_cachalot()


try:
    from .local_test import *  # noqa: F403, F401
except ImportError:
    pass
