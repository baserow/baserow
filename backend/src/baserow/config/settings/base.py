import importlib
import json
import os
import re
from datetime import timedelta
from decimal import Decimal
from ipaddress import ip_network
from pathlib import Path
from urllib.parse import urljoin, urlparse

from django.core.exceptions import ImproperlyConfigured

import dj_database_url
import posthog
import sentry_sdk
from corsheaders.defaults import default_headers
from sentry_sdk.integrations.django import DjangoIntegration

from baserow.cachalot_patch import patch_cachalot_for_baserow
from baserow.config.settings.utils import (
    Setting,
    get_crontab_from_env,
    read_file,
    set_settings_from_env_if_present,
    str_to_bool,
    try_int,
)
from baserow.core.telemetry.utils import otel_is_enabled
from baserow.throttling_types import RateLimit
from baserow.version import VERSION

# A comma separated list of feature flags used to enable in-progress or not ready
# features for developers. See docs/development/feature-flags.md for more info.
FEATURE_FLAGS = [
    flag.strip().lower() for flag in os.getenv("FEATURE_FLAGS", "").split(",")
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASEROW_PLUGIN_DIR_PATH = Path(os.environ.get("BASEROW_PLUGIN_DIR", "/baserow/plugins"))

if BASEROW_PLUGIN_DIR_PATH.exists():
    BASEROW_PLUGIN_FOLDERS = [
        file
        for file in BASEROW_PLUGIN_DIR_PATH.iterdir()
        if file.is_dir() and Path(file, "backend").exists()
    ]
else:
    BASEROW_PLUGIN_FOLDERS = []

BASEROW_BACKEND_PLUGIN_NAMES = [d.name for d in BASEROW_PLUGIN_FOLDERS]
BASEROW_OSS_ONLY = bool(os.getenv("BASEROW_OSS_ONLY", ""))
if BASEROW_OSS_ONLY:
    BASEROW_BUILT_IN_PLUGINS = []
else:
    BASEROW_BUILT_IN_PLUGINS = ["baserow_premium", "baserow_enterprise"]

# SECURITY WARNING: keep the secret key used in production secret!
if "SECRET_KEY" in os.environ:
    SECRET_KEY = os.environ.get("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("BASEROW_BACKEND_DEBUG", "off") == "on"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
ALLOWED_HOSTS += os.getenv("BASEROW_EXTRA_ALLOWED_HOSTS", "").split(",")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "djcelery_email",
    "health_check",
    "health_check.db",
    "health_check.cache",
    "health_check.contrib.migrations",
    "health_check.contrib.redis",
    "health_check.contrib.celery_ping",
    "health_check.contrib.psutil",
    "health_check.contrib.s3boto3_storage",
    "baserow.core",
    "baserow.api",
    "baserow.ws",
    "baserow.contrib.database",
    "baserow.contrib.integrations",
    "baserow.contrib.builder",
    "baserow.contrib.dashboard",
    *BASEROW_BUILT_IN_PLUGINS,
]


ADDITIONAL_APPS = os.getenv("ADDITIONAL_APPS", "").split(",")
if ADDITIONAL_APPS is not None:
    INSTALLED_APPS += [app.strip() for app in ADDITIONAL_APPS if app.strip() != ""]

if BASEROW_BACKEND_PLUGIN_NAMES:
    print(f"Loaded backend plugins: {','.join(BASEROW_BACKEND_PLUGIN_NAMES)}")
    INSTALLED_APPS.extend(BASEROW_BACKEND_PLUGIN_NAMES)

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "baserow.api.user_sources.middleware.AddUserSourceUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "baserow.middleware.BaserowCustomHttp404Middleware",
    "baserow.middleware.ClearContextMiddleware",
]

if otel_is_enabled():
    MIDDLEWARE += ["baserow.core.telemetry.middleware.BaserowOTELMiddleware"]

ROOT_URLCONF = "baserow.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "baserow.config.wsgi.application"
ASGI_APPLICATION = "baserow.config.asgi.application"


# `ASGI_HTTP_MAX_CONCURRENCY` sets max concurrent asgi requests to be processed by
# the asgi application. It's configurable with `BASEROW_ASGI_HTTP_MAX_CONCURRENCY`
# env variable.
# The default is None - no concurrency limit
ASGI_HTTP_MAX_CONCURRENCY = (
    int(os.getenv("BASEROW_ASGI_HTTP_MAX_CONCURRENCY") or 0) or None
)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_USERNAME = os.getenv("REDIS_USER", "")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_PROTOCOL = os.getenv("REDIS_PROTOCOL", "redis")
REDIS_URL = os.getenv(
    "REDIS_URL",
    f"{REDIS_PROTOCOL}://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0",
)

BASEROW_GROUP_STORAGE_USAGE_QUEUE = os.getenv(
    "BASEROW_GROUP_STORAGE_USAGE_QUEUE", "export"
)
BASEROW_ROLE_USAGE_QUEUE = os.getenv("BASEROW_GROUP_STORAGE_USAGE_QUEUE", "export")

CELERY_BROKER_URL = REDIS_URL
CELERY_TASK_ROUTES = {
    "baserow.contrib.database.export.tasks.run_export_job": {"queue": "export"},
    "baserow.contrib.database.export.tasks.clean_up_old_jobs": {"queue": "export"},
    "baserow.core.trash.tasks.mark_old_trash_for_permanent_deletion": {
        "queue": "export"
    },
    "baserow.core.trash.tasks.permanently_delete_marked_trash": {"queue": "export"},
    "baserow.core.usage.tasks": {"queue": BASEROW_GROUP_STORAGE_USAGE_QUEUE},
    "baserow.contrib.database.table.tasks.run_row_count_job": {"queue": "export"},
    "baserow.core.jobs.tasks.clean_up_jobs": {"queue": "export"},
}
CELERY_SOFT_TIME_LIMIT = 60 * 5  # 5 minutes
CELERY_TIME_LIMIT = CELERY_SOFT_TIME_LIMIT + 60  # 60 seconds

CELERY_REDBEAT_REDIS_URL = REDIS_URL
# Explicitly set the same value as the default loop interval here so we can use it
# later. CELERY_BEAT_MAX_LOOP_INTERVAL < CELERY_REDBEAT_LOCK_TIMEOUT must be kept true
# as otherwise a beat instance will acquire the lock, do scheduling, go to sleep for
# CELERY_BEAT_MAX_LOOP_INTERVAL before waking up where it assumes it still owns the lock
# however if the lock timeout is less than the interval the lock will have been released
# and the beat instance will crash as it attempts to extend the lock which it no longer
# owns.
CELERY_BEAT_MAX_LOOP_INTERVAL = os.getenv("CELERY_BEAT_MAX_LOOP_INTERVAL", 20)
# By default CELERY_REDBEAT_LOCK_TIMEOUT = 5 * CELERY_BEAT_MAX_LOOP_INTERVAL
# Only one beat instance can hold this lock and schedule tasks at any one time.
# This means if one celery-beat instance crashes any other replicas waiting to take over
# will by default wait 25 minutes until the lock times out and they can acquire
# the lock to start scheduling tasks again.
# Instead we just set it to be slightly longer than the loop interval that beat uses.
# This means beat wakes up, checks the schedule and extends the lock every
# CELERY_BEAT_MAX_LOOP_INTERVAL seconds. If it crashes or fails to wake up
# then 80 seconds after the lock was last extended it will be released and a new
# scheduler will acquire the lock and take over.
CELERY_REDBEAT_LOCK_TIMEOUT = os.getenv(
    "CELERY_REDBEAT_LOCK_TIMEOUT", CELERY_BEAT_MAX_LOOP_INTERVAL + 60
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases
if "DATABASE_URL" in os.environ:
    DATABASES = {
        "default": dj_database_url.parse(os.getenv("DATABASE_URL"), conn_max_age=600)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DATABASE_NAME", "baserow"),
            "USER": os.getenv("DATABASE_USER", "baserow"),
            "PASSWORD": os.getenv("DATABASE_PASSWORD", "baserow"),
            "HOST": os.getenv("DATABASE_HOST", "db"),
            "PORT": os.getenv("DATABASE_PORT", "5432"),
        }
    }
    if "DATABASE_OPTIONS" in os.environ:
        DATABASES["default"]["OPTIONS"] = json.loads(
            os.getenv("DATABASE_OPTIONS", "{}")
        )

GENERATED_MODEL_CACHE_NAME = "generated-models"
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "baserow-default-cache",
        "VERSION": VERSION,
    },
    GENERATED_MODEL_CACHE_NAME: {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": f"baserow-{GENERATED_MODEL_CACHE_NAME}-cache",
        "VERSION": None,
    },
}


CACHALOT_TIMEOUT = int(os.getenv("BASEROW_CACHALOT_TIMEOUT", 60 * 60 * 24 * 7))
BASEROW_CACHALOT_ONLY_CACHABLE_TABLES = os.getenv(
    "BASEROW_CACHALOT_ONLY_CACHABLE_TABLES", None
)
BASEROW_CACHALOT_MODE = os.getenv("BASEROW_CACHALOT_MODE", "default")
if BASEROW_CACHALOT_MODE == "full":
    CACHALOT_ONLY_CACHABLE_TABLES = []

elif BASEROW_CACHALOT_ONLY_CACHABLE_TABLES:
    # Please avoid to add tables with more than 50 modifications per minute
    # to this list, as described here:
    # https://django-cachalot.readthedocs.io/en/latest/limits.html
    CACHALOT_ONLY_CACHABLE_TABLES = BASEROW_CACHALOT_ONLY_CACHABLE_TABLES.split(",")
else:
    CACHALOT_ONLY_CACHABLE_TABLES = [
        "auth_user",
        "django_content_type",
        "core_settings",
        "core_userprofile",
        "core_application",
        "core_operation",
        "core_template",
        "core_trashentry",
        "core_workspace",
        "core_workspaceuser",
        "core_workspaceuserinvitation",
        "core_authprovidermodel",
        "core_passwordauthprovidermodel",
        "database_database",
        "database_table",
        "database_field",
        "database_fieldependency",
        "database_linkrowfield",
        "database_selectoption",
        "baserow_premium_license",
        "baserow_premium_licenseuser",
        "baserow_enterprise_role",
        "baserow_enterprise_roleassignment",
        "baserow_enterprise_team",
        "baserow_enterprise_teamsubject",
    ]

# This list will have priority over CACHALOT_ONLY_CACHABLE_TABLES.
BASEROW_CACHALOT_UNCACHABLE_TABLES = os.getenv(
    "BASEROW_CACHALOT_UNCACHABLE_TABLES", None
)

if BASEROW_CACHALOT_UNCACHABLE_TABLES:
    CACHALOT_UNCACHABLE_TABLES = list(
        filter(bool, BASEROW_CACHALOT_UNCACHABLE_TABLES.split(","))
    )

CACHALOT_ENABLED = os.getenv("BASEROW_CACHALOT_ENABLED", "false") == "true"
CACHALOT_CACHE = "cachalot"
CACHALOT_UNCACHABLE_TABLES = [
    "django_migrations",
    "core_action",
    "database_token",
    "baserow_enterprise_auditlogentry",
]

BUILDER_PUBLICLY_USED_PROPERTIES_CACHE_TTL_SECONDS = int(
    # Default TTL is 10 minutes: 60 seconds * 10
    os.getenv("BASEROW_BUILDER_PUBLICLY_USED_PROPERTIES_CACHE_TTL_SECONDS")
    or 600
)


def install_cachalot():
    global INSTALLED_APPS

    INSTALLED_APPS.append("cachalot")

    patch_cachalot_for_baserow()


if CACHALOT_ENABLED:
    install_cachalot()

    CACHES[CACHALOT_CACHE] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": f"baserow-{CACHALOT_CACHE}-cache",
        "VERSION": VERSION,
    }


CELERY_SINGLETON_BACKEND_CLASS = (
    "baserow.celery_singleton_backend.RedisBackendForSingleton"
)

# This flag enable automatic index creation for table views based on sortings.
AUTO_INDEX_VIEW_ENABLED = os.getenv("BASEROW_AUTO_INDEX_VIEW_ENABLED", "true") == "true"
AUTO_INDEX_LOCK_EXPIRY = os.getenv("BASEROW_AUTO_INDEX_LOCK_EXPIRY", 60 * 2)

# Should contain the database connection name of the database where the user tables
# are stored. This can be different than the default database because there are not
# going to be any relations between the application schema and the user schema.
USER_TABLE_DATABASE = "default"

# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "baserow.core.user.password_validation.MaximumLengthValidator",
    },
]

# We need the `AllowAllUsersModelBackend` in order to respond with a proper error
# message when the user is not active. The only thing it does, is allowing non active
# users to authenticate, but the user still can't obtain or use a JWT token or database
# token because the user needs to be active to use that.
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.AllowAllUsersModelBackend"]

# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("fr", "French"),
    ("nl", "Dutch"),
    ("de", "German"),
    ("es", "Spanish"),
    ("it", "Italian"),
    ("pl", "Polish"),
    ("ko", "Korean"),
]

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Collation that the backend database should
# support in order to make front end and back end
# collations as close as possible to match sorting and
# other operations.
EXPECTED_COLLATION = "en-x-icu"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = "/static/"

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "baserow.api.user_sources.authentication.UserSourceJSONWebTokenAuthentication",
        "baserow.api.authentication.JSONWebTokenAuthentication",
    ),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_SCHEMA_CLASS": "baserow.api.openapi.AutoSchema",
}

# Limits the number of concurrent requests per user.
# If BASEROW_MAX_CONCURRENT_USER_REQUESTS is not set, then the default value of -1
# will be used which means the throttling is disabled.
BASEROW_MAX_CONCURRENT_USER_REQUESTS = int(
    os.getenv("BASEROW_MAX_CONCURRENT_USER_REQUESTS", "") or -1
)

if BASEROW_MAX_CONCURRENT_USER_REQUESTS > 0:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
        "baserow.throttling.ConcurrentUserRequestsThrottle",
    ]

    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        "concurrent_user_requests": BASEROW_MAX_CONCURRENT_USER_REQUESTS
    }

    MIDDLEWARE += [
        "baserow.middleware.ConcurrentUserRequestsMiddleware",
    ]

# The maximum number of seconds that a request can be throttled for.
BASEROW_CONCURRENT_USER_REQUESTS_THROTTLE_TIMEOUT = int(
    os.getenv("BASEROW_CONCURRENT_USER_REQUESTS_THROTTLE_TIMEOUT", 30)
)

PUBLIC_VIEW_AUTHORIZATION_HEADER = "Baserow-View-Authorization"

CORS_ORIGIN_ALLOW_ALL = True
CLIENT_SESSION_ID_HEADER = "ClientSessionId"
MAX_CLIENT_SESSION_ID_LENGTH = 256

CLIENT_UNDO_REDO_ACTION_GROUP_ID_HEADER = "ClientUndoRedoActionGroupId"
MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP = 20
WEBSOCKET_ID_HEADER = "WebsocketId"

USER_SOURCE_AUTHENTICATION_HEADER = "UserSourceAuthorization"

CORS_ALLOW_HEADERS = list(default_headers) + [
    WEBSOCKET_ID_HEADER,
    PUBLIC_VIEW_AUTHORIZATION_HEADER,
    CLIENT_SESSION_ID_HEADER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_HEADER,
    USER_SOURCE_AUTHENTICATION_HEADER,
]

ACCESS_TOKEN_LIFETIME = timedelta(
    minutes=int(os.getenv("BASEROW_ACCESS_TOKEN_LIFETIME_MINUTES", 10))  # 10 minutes
)
REFRESH_TOKEN_LIFETIME = timedelta(
    hours=int(os.getenv("BASEROW_REFRESH_TOKEN_LIFETIME_HOURS", 24 * 7))  # 7 days
)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": ACCESS_TOKEN_LIFETIME,
    "REFRESH_TOKEN_LIFETIME": REFRESH_TOKEN_LIFETIME,
    "AUTH_HEADER_TYPES": ("JWT",),
    # It is recommended that you set BASEROW_JWT_SIGNING_KEY so it is independent
    # from the Django SECRET_KEY. This will make changing the signing key used for
    # tokens easier in the event that it is compromised.
    "SIGNING_KEY": os.getenv("BASEROW_JWT_SIGNING_KEY") or os.getenv("SECRET_KEY"),
    "USER_AUTHENTICATION_RULE": lambda user: user is not None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Baserow API spec",
    "DESCRIPTION": "For more information about our REST API, please visit "
    "[this page](https://baserow.io/docs/apis%2Frest-api).\n\n"
    "For more information about our deprecation policy, please visit "
    "[this page](https://baserow.io/docs/apis%2Fdeprecations).",
    "CONTACT": {"url": "https://baserow.io/contact"},
    "LICENSE": {
        "name": "MIT",
        "url": "https://gitlab.com/baserow/baserow/-/blob/master/LICENSE",
    },
    "VERSION": "1.30.1",
    "SERVE_INCLUDE_SCHEMA": False,
    "TAGS": [
        {"name": "Settings"},
        {"name": "User"},
        {"name": "User files"},
        {"name": "Workspaces"},
        {"name": "Workspace invitations"},
        {"name": "Templates"},
        {"name": "Trash"},
        {"name": "Applications"},
        {"name": "Snapshots"},
        {"name": "Jobs"},
        {"name": "Integrations"},
        {"name": "User sources"},
        {"name": "Database tables"},
        {"name": "Database table fields"},
        {"name": "Database table views"},
        {"name": "Database table view filters"},
        {"name": "Database table view sortings"},
        {"name": "Database table view decorations"},
        {"name": "Database table view groupings"},
        {"name": "Database table grid view"},
        {"name": "Database table gallery view"},
        {"name": "Database table form view"},
        {"name": "Database table kanban view"},
        {"name": "Database table calendar view"},
        {"name": "Database table rows"},
        {"name": "Database table export"},
        {"name": "Database table webhooks"},
        {"name": "Database tokens"},
        {"name": "Builder pages"},
        {"name": "Builder elements"},
        {"name": "Builder domains"},
        {"name": "Builder public"},
        {"name": "Builder data sources"},
        {"name": "Builder workflow actions"},
        {"name": "Builder theme"},
        {"name": "Admin"},
    ],
    "ENUM_NAME_OVERRIDES": {
        "NumberDecimalPlacesEnum": [
            (0, "1"),
            (1, "1.0"),
            (2, "1.00"),
            (3, "1.000"),
            (4, "1.0000"),
            (5, "1.00000"),
        ],
        "ViewTypesEnum": [
            "grid",
            "gallery",
            "form",
            "kanban",
            "calendar",
        ],
        "FieldTypesEnum": [
            "text",
            "long_text",
            "url",
            "email",
            "number",
            "rating",
            "boolean",
            "date",
            "last_modified",
            "created_on",
            "link_row",
            "file",
            "single_select",
            "multiple_select",
            "phone_number",
            "formula",
            "count",
            "lookup",
            "url",
        ],
        "ViewFilterTypesEnum": [
            "equal",
            "not_equal",
            "filename_contains",
            "has_file_type",
            "files_lower_than",
            "contains",
            "contains_not",
            "length_is_lower_than",
            "higher_than",
            "lower_than",
            "date_equal",
            "date_before",
            "date_after",
            "date_not_equal",
            "date_equals_today",
            "date_equals_days_ago",
            "date_equals_week",
            "date_equals_month",
            "date_equals_day_of_month",
            "date_equals_year",
            "single_select_equal",
            "single_select_not_equal",
            "link_row_has",
            "link_row_has_not",
            "boolean",
            "empty",
            "not_empty",
            "multiple_select_has",
            "multiple_select_has_not",
        ],
        "EventTypesEnum": ["rows.created", "rows.updated", "rows.deleted"],
    },
}

BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB = int(
    Decimal(os.getenv("BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB", 1024 * 1024)) * 1024 * 1024
)  # ~1TB by default

BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = int(
    os.getenv("BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB", 512)
)

# Allows accessing and setting values on a dictionary like an object. Using this
# we can pass plugin authors and other functions a `settings` object which can modify
# the settings like they expect (settings.SETTING = 'test') etc.


class AttrDict(dict):
    def __getattr__(self, item):
        return super().__getitem__(item)

    def __setattr__(self, item, value):
        globals()[item] = value

    def __setitem__(self, key, value):
        globals()[key] = value


BASE_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

AWS_STORAGE_ENABLED = os.getenv("AWS_STORAGE_BUCKET_NAME", "") != ""
GOOGLE_STORAGE_ENABLED = os.getenv("GS_BUCKET_NAME", "") != ""
AZURE_STORAGE_ENABLED = os.getenv("AZURE_ACCOUNT_NAME", "") != ""

ALL_STORAGE_ENABLED_VARS = [
    AZURE_STORAGE_ENABLED,
    GOOGLE_STORAGE_ENABLED,
    AWS_STORAGE_ENABLED,
]
if sum(ALL_STORAGE_ENABLED_VARS) > 1:
    raise ImproperlyConfigured(
        "You have enabled more than one user file storage backend, please make sure "
        "you set only one of AWS_ACCESS_KEY_ID, GS_BUCKET_NAME and AZURE_ACCOUNT_NAME."
    )

if AWS_STORAGE_ENABLED:
    BASE_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_S3_FILE_OVERWRITE = False
    # This is needed to write the media file in a single call to `files_zip.writestr`
    # as described here: https://github.com/kobotoolbox/kobocat/issues/475
    AWS_S3_FILE_BUFFER_SIZE = BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB
    set_settings_from_env_if_present(
        AttrDict(vars()),
        [
            "AWS_S3_SESSION_PROFILE",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_STORAGE_BUCKET_NAME",
            Setting(
                "AWS_S3_OBJECT_PARAMETERS",
                parser=json.loads,
                default={
                    "CacheControl": "max-age=86400",
                },
            ),
            Setting("AWS_DEFAULT_ACL", default="public-read"),
            Setting("AWS_QUERYSTRING_AUTH", parser=str_to_bool),
            Setting("AWS_S3_MAX_MEMORY_SIZE", parser=int),
            Setting("AWS_QUERYSTRING_EXPIRE", parser=int),
            "AWS_S3_URL_PROTOCOL",
            "AWS_S3_REGION_NAME",
            "AWS_S3_ENDPOINT_URL",
            "AWS_S3_CUSTOM_DOMAIN",
            "AWS_LOCATION",
            Setting("AWS_IS_GZIPPED", parser=str_to_bool),
            "GZIP_CONTENT_TYPES",
            Setting("AWS_S3_USE_SSL", parser=str_to_bool),
            Setting("AWS_S3_VERIFY", parser=str_to_bool),
            Setting(
                "AWS_SECRET_ACCESS_KEY_FILE_PATH",
                setting_name="AWS_SECRET_ACCESS_KEY",
                parser=read_file,
            ),
            "AWS_S3_ADDRESSING_STYLE",
            Setting("AWS_S3_PROXIES", parser=json.loads),
            "AWS_S3_SIGNATURE_VERSION",
            Setting("AWS_CLOUDFRONT_KEY", parser=lambda s: s.encode("ascii")),
            "AWS_CLOUDFRONT_KEY_ID",
        ],
    )


if GOOGLE_STORAGE_ENABLED:
    from google.oauth2 import service_account

    # See https://django-storages.readthedocs.io/en/latest/backends/gcloud.html for
    # details on what these env variables do

    BASE_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
    GS_FILE_OVERWRITE = False
    set_settings_from_env_if_present(
        AttrDict(vars()),
        [
            "GS_BUCKET_NAME",
            "GS_PROJECT_ID",
            Setting("GS_IS_GZIPPED", parser=str_to_bool),
            "GZIP_CONTENT_TYPES",
            Setting("GS_DEFAULT_ACL", default="publicRead"),
            Setting("GS_QUERYSTRING_AUTH", parser=str_to_bool),
            Setting("GS_MAX_MEMORY_SIZE", parser=int),
            Setting("GS_BLOB_CHUNK_SIZE", parser=int),
            Setting("GS_OBJECT_PARAMETERS", parser=json.loads),
            "GS_CUSTOM_ENDPOINT",
            "GS_LOCATION",
            Setting("GS_EXPIRATION", parser=int),
            Setting(
                "GS_CREDENTIALS_FILE_PATH",
                setting_name="GS_CREDENTIALS",
                parser=service_account.Credentials.from_service_account_file,
            ),
        ],
    )

if AZURE_STORAGE_ENABLED:
    BASE_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"
    AZURE_OVERWRITE_FILES = False
    set_settings_from_env_if_present(
        AttrDict(vars()),
        [
            "AZURE_ACCOUNT_NAME",
            "AZURE_ACCOUNT_KEY",
            Setting(
                "AZURE_ACCOUNT_KEY_FILE_PATH",
                setting_name="AZURE_ACCOUNT_KEY",
                parser=read_file,
            ),
            "AZURE_CONTAINER",
            Setting("AZURE_SSL", parser=str_to_bool),
            Setting("AZURE_UPLOAD_MAX_CONN", parser=int),
            Setting("AZURE_CONNECTION_TIMEOUT_SECS", parser=int),
            Setting("AZURE_URL_EXPIRATION_SECS", parser=int),
            "AZURE_LOCATION",
            "AZURE_ENDPOINT_SUFFIX",
            "AZURE_CUSTOM_DOMAIN",
            "AZURE_CONNECTION_STRING",
            "AZURE_TOKEN_CREDENTIAL",
            "AZURE_CACHE_CONTROL",
            Setting("AZURE_OBJECT_PARAMETERS", parser=json.loads),
            "AZURE_API_VERSION",
        ],
    )

STORAGES = {
    "default": {
        "BACKEND": BASE_FILE_STORAGE,
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

BASEROW_PUBLIC_URL = os.getenv("BASEROW_PUBLIC_URL")
if BASEROW_PUBLIC_URL:
    PUBLIC_BACKEND_URL = BASEROW_PUBLIC_URL
    PUBLIC_WEB_FRONTEND_URL = BASEROW_PUBLIC_URL
    if BASEROW_PUBLIC_URL == "http://localhost":
        print(
            "WARNING: Baserow is configured to use a BASEROW_PUBLIC_URL of "
            "http://localhost. If you attempt to access Baserow on any other hostname "
            "requests to the backend will fail as they will be from an unknown host. "
            "Please set BASEROW_PUBLIC_URL if you will be accessing Baserow "
            "from any other URL then http://localhost."
        )
else:
    PUBLIC_BACKEND_URL = os.getenv("PUBLIC_BACKEND_URL", "http://localhost:8000")
    PUBLIC_WEB_FRONTEND_URL = os.getenv(
        "PUBLIC_WEB_FRONTEND_URL", "http://localhost:3000"
    )
    if "PUBLIC_BACKEND_URL" not in os.environ:
        print(
            "WARNING: Baserow is configured to use a PUBLIC_BACKEND_URL of "
            "http://localhost:8000. If you attempt to access Baserow on any other "
            "hostname requests to the backend will fail as they will be from an "
            "unknown host."
            "Please ensure you set PUBLIC_BACKEND_URL if you will be accessing "
            "Baserow from any other URL then http://localhost."
        )
    if "PUBLIC_WEB_FRONTEND_URL" not in os.environ:
        print(
            "WARNING: Baserow is configured to use a default PUBLIC_WEB_FRONTEND_URL "
            "of http://localhost:3000. Emails sent by Baserow will use links pointing "
            "to http://localhost:3000 when telling users how to access your server. If "
            "this is incorrect please ensure you have set PUBLIC_WEB_FRONTEND_URL to "
            "the URL where users can access your Baserow server."
        )

BASEROW_EMBEDDED_SHARE_URL = os.getenv("BASEROW_EMBEDDED_SHARE_URL")
if not BASEROW_EMBEDDED_SHARE_URL:
    BASEROW_EMBEDDED_SHARE_URL = PUBLIC_WEB_FRONTEND_URL

PRIVATE_BACKEND_URL = os.getenv("PRIVATE_BACKEND_URL", "http://backend:8000")
PUBLIC_BACKEND_HOSTNAME = urlparse(PUBLIC_BACKEND_URL).hostname
PUBLIC_WEB_FRONTEND_HOSTNAME = urlparse(PUBLIC_WEB_FRONTEND_URL).hostname
BASEROW_EMBEDDED_SHARE_HOSTNAME = urlparse(BASEROW_EMBEDDED_SHARE_URL).hostname
PRIVATE_BACKEND_HOSTNAME = urlparse(PRIVATE_BACKEND_URL).hostname

if PUBLIC_BACKEND_HOSTNAME:
    ALLOWED_HOSTS.append(PUBLIC_BACKEND_HOSTNAME)

if PRIVATE_BACKEND_HOSTNAME:
    ALLOWED_HOSTS.append(PRIVATE_BACKEND_HOSTNAME)

FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@localhost")
RESET_PASSWORD_TOKEN_MAX_AGE = 60 * 60 * 48  # 48 hours

ROW_PAGE_SIZE_LIMIT = int(os.getenv("BASEROW_ROW_PAGE_SIZE_LIMIT", 200))
BATCH_ROWS_SIZE_LIMIT = int(
    os.getenv("BATCH_ROWS_SIZE_LIMIT", 200)
)  # How many rows can be modified at once.

TRASH_PAGE_SIZE_LIMIT = 200  # How many trash entries can be requested at once.

# How many unique row values can be requested at once.
BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT = int(
    os.getenv("BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT", 100)
)

# The amount of rows that can be imported when creating a table or data sync.
INITIAL_TABLE_DATA_LIMIT = None
if "INITIAL_TABLE_DATA_LIMIT" in os.environ:
    INITIAL_TABLE_DATA_LIMIT = int(os.getenv("INITIAL_TABLE_DATA_LIMIT"))

BASEROW_INITIAL_CREATE_SYNC_TABLE_DATA_LIMIT = int(
    os.getenv("BASEROW_INITIAL_CREATE_SYNC_TABLE_DATA_LIMIT", 5000)
)

MEDIA_URL_PATH = "/media/"
MEDIA_URL = os.getenv("MEDIA_URL", urljoin(PUBLIC_BACKEND_URL, MEDIA_URL_PATH))
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/baserow/media")

# Indicates the directory where the user files and user thumbnails are stored.
USER_FILES_DIRECTORY = "user_files"
USER_THUMBNAILS_DIRECTORY = "thumbnails"

EXPORT_FILES_DIRECTORY = "export_files"
EXPORT_CLEANUP_INTERVAL_MINUTES = 5
EXPORT_FILE_EXPIRE_MINUTES = 60

IMPORT_FILES_DIRECTORY = "import_files"

# The interval in minutes that the mentions cleanup job should run. This job will
# remove mentions that are no longer used.
STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES = int(
    os.getenv("BASEROW_STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES", "") or 360
)

MIDNIGHT_CRONTAB_STR = "0 0 * * *"
BASEROW_STORAGE_USAGE_JOB_CRONTAB = get_crontab_from_env(
    "BASEROW_STORAGE_USAGE_JOB_CRONTAB", default_crontab=MIDNIGHT_CRONTAB_STR
)

ONE_AM_CRONTRAB_STR = "0 1 * * *"
BASEROW_SEAT_USAGE_JOB_CRONTAB = get_crontab_from_env(
    "BASEROW_SEAT_USAGE_JOB_CRONTAB", default_crontab=ONE_AM_CRONTRAB_STR
)

EMAIL_BACKEND = "djcelery_email.backends.CeleryEmailBackend"

if os.getenv("EMAIL_SMTP", ""):
    CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    # EMAIL_SMTP_USE_TLS OR EMAIL_SMTP_USE_TLS for backwards compatibility after
    # fixing #448.
    EMAIL_USE_TLS = bool(os.getenv("EMAIL_SMTP_USE_TLS", "")) or bool(
        os.getenv("EMAIL_SMPT_USE_TLS", "")
    )
    EMAIL_HOST = os.getenv("EMAIL_SMTP_HOST", "localhost")
    EMAIL_PORT = os.getenv("EMAIL_SMTP_PORT", "25")
    EMAIL_HOST_USER = os.getenv("EMAIL_SMTP_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_SMTP_PASSWORD", "")

    EMAIL_USE_SSL = bool(os.getenv("EMAIL_SMTP_USE_SSL", ""))
    if EMAIL_USE_SSL and EMAIL_USE_TLS:
        raise ImproperlyConfigured(
            "EMAIL_SMTP_USE_SSL and EMAIL_SMTP_USE_TLS are "
            "mutually exclusive and both cannot be set at once."
        )

    EMAIL_SSL_CERTFILE = os.getenv("EMAIL_SMTP_SSL_CERTFILE_PATH", None)
    EMAIL_SSL_KEYFILE = os.getenv("EMAIL_SMTP_SSL_KEYFILE_PATH", None)
else:
    CELERY_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Enable email notifications globally. If disabled, tasks will reset the
# email_scheduled field without sending any emails.
EMAIL_NOTIFICATIONS_ENABLED = str_to_bool(
    os.getenv("BASEROW_EMAIL_NOTIFICATIONS_ENABLED", "true")
)
# The maximum amount of email notifications that can be sent per task. This
# equals the amount of users that will receive an email, since all the
# notifications for a user are sent in one email. If you want to limit the
# number of emails sent per minute, look at MAX_EMAILS_PER_MINUTE.
EMAIL_NOTIFICATIONS_LIMIT_PER_TASK = {
    "instant": int(os.getenv("BASEROW_EMAIL_NOTIFICATIONS_LIMIT_INSTANT", 50)),
    "daily": int(os.getenv("BASEROW_EMAIL_NOTIFICATIONS_LIMIT_DAILY", 1000)),
    "weekly": int(os.getenv("BASEROW_EMAIL_NOTIFICATIONS_LIMIT_WEEKLY", 5000)),
}
# The crontab used to schedule the instant email notifications task.
EMAIL_NOTIFICATIONS_INSTANT_CRONTAB = get_crontab_from_env(
    "BASEROW_EMAIL_NOTIFICATIONS_INSTANT_CRONTAB", default_crontab="* * * * *"
)
# The hour of the day (between 0 and 23) when the daily and weekly email
# notifications task is scheduled, according to the user timezone. Every hour a
# task is scheduled and only the users in the correct timezone will receive an
# email.
EMAIL_NOTIFICATIONS_DAILY_HOUR_OF_DAY = int(
    os.getenv("BASEROW_EMAIL_NOTIFICATIONS_DAILY_HOUR_OF_DAY", 0)
)
# The day of the week when the weekly email notifications task is scheduled,
# according to the user timezone (0: Monday, ..., 6: Sunday).
EMAIL_NOTIFICATIONS_WEEKLY_DAY_OF_WEEK = int(
    os.getenv("BASEROW_EMAIL_NOTIFICATIONS_WEEKLY_DAY_OF_WEEK", 0)
)
# 0 seconds means that the task will not be retried if the limit of users being
# notified is reached. Provide a positive number to enable retries after this many
# seconds.
EMAIL_NOTIFICATIONS_AUTO_RETRY_IF_LIMIT_REACHED_AFTER = (
    int(os.getenv("BASEROW_EMAIL_NOTIFICATIONS_AUTO_RETRY_IF_LIMIT_REACHED_AFTER", 0))
    or None
)

# The maximum number of notifications that are going to be listed in a single email.
# All the additional notifications are going to be included in a single "and x more"
MAX_NOTIFICATIONS_LISTED_PER_EMAIL = int(
    os.getenv("BASEROW_MAX_NOTIFICATIONS_LISTED_PER_EMAIL", 10)
)

# Look into `CeleryEmailBackend` for more information about these settings.
CELERY_EMAIL_CHUNK_SIZE = int(os.getenv("CELERY_EMAIL_CHUNK_SIZE", 10))
# Use a multiple of CELERY_EMAIL_CHUNK_SIZE to have a sensible rate limit.
MAX_EMAILS_PER_MINUTE = int(os.getenv("BASEROW_MAX_EMAILS_PER_MINUTE", 50))
CELERY_EMAIL_TASK_CONFIG = {
    "rate_limit": f"{int(MAX_EMAILS_PER_MINUTE / CELERY_EMAIL_CHUNK_SIZE)}/m",
}

BASEROW_SEND_VERIFY_EMAIL_RATE_LIMIT = RateLimit.from_string(
    os.getenv("BASEROW_SEND_VERIFY_EMAIL_RATE_LIMIT", "5/h")
)

login_action_limit_from_env = os.getenv("BASEROW_LOGIN_ACTION_LOG_LIMIT")
BASEROW_LOGIN_ACTION_LOG_LIMIT = (
    RateLimit.from_string(login_action_limit_from_env)
    if login_action_limit_from_env
    else RateLimit(period_in_seconds=60 * 5, number_of_calls=1)
)

# Configurable thumbnails that are going to be generated when a user uploads an image
# file.
USER_THUMBNAILS = {"tiny": [None, 21], "small": [48, 48], "card_cover": [300, 160]}

# The directory that contains the all the templates in JSON format. When for example
# the `sync_templates` management command is called, then the templates in the
# database will be synced with these files.
APPLICATION_TEMPLATES_DIR = os.path.join(BASE_DIR, "../../../templates")
# The template that must be selected when the user first opens the templates select
# modal.
# IF CHANGING KEEP IN SYNC WITH e2e-tests/wait-for-services.sh
DEFAULT_APPLICATION_TEMPLATE = "project-tracker"
BASEROW_SYNC_TEMPLATES_PATTERN = os.getenv("BASEROW_SYNC_TEMPLATES_PATTERN", None)

MAX_FIELD_LIMIT = int(os.getenv("BASEROW_MAX_FIELD_LIMIT", 600))

INITIAL_MIGRATION_FULL_TEXT_SEARCH_MAX_FIELD_LIMIT = int(
    os.getenv(
        "BASEROW_INITIAL_MIGRATION_FULL_TEXT_SEARCH_MAX_FIELD_LIMIT", MAX_FIELD_LIMIT
    )
)


# set max events to be returned by every ICal feed. Empty value means no limit.
BASEROW_ICAL_VIEW_MAX_EVENTS = try_int(
    os.getenv("BASEROW_ICAL_VIEW_MAX_EVENTS", None), None
)


# If you change this default please also update the default for the web-frontend found
# in web-frontend/modules/core/module.js:55
HOURS_UNTIL_TRASH_PERMANENTLY_DELETED = int(
    os.getenv("HOURS_UNTIL_TRASH_PERMANENTLY_DELETED", 24 * 3)
)
OLD_TRASH_CLEANUP_CHECK_INTERVAL_MINUTES = 5

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# For now force the old os dependant behaviour of file uploads as users might be relying
# on it. See
# https://docs.djangoproject.com/en/3.2/releases/3.0/#new-default-value-for-the-file-upload-permissions-setting
FILE_UPLOAD_PERMISSIONS = None

MAX_FORMULA_STRING_LENGTH = 10000
MAX_FIELD_REFERENCE_DEPTH = 1000
DONT_UPDATE_FORMULAS_AFTER_MIGRATION = bool(
    os.getenv("DONT_UPDATE_FORMULAS_AFTER_MIGRATION", "")
)
EVERY_TEN_MINUTES = "*/10 * * * *"
PERIODIC_FIELD_UPDATE_TIMEOUT_MINUTES = int(
    os.getenv("BASEROW_PERIODIC_FIELD_UPDATE_TIMEOUT_MINUTES", 9)
)
PERIODIC_FIELD_UPDATE_CRONTAB = get_crontab_from_env(
    "BASEROW_PERIODIC_FIELD_UPDATE_CRONTAB", default_crontab=EVERY_TEN_MINUTES
)
BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = int(
    os.getenv("BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN", 60)
)
PERIODIC_FIELD_UPDATE_QUEUE_NAME = os.getenv(
    "BASEROW_PERIODIC_FIELD_UPDATE_QUEUE_NAME", "export"
)

BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES = int(
    os.getenv("BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES", 8)
)
BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL = int(
    os.getenv("BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL", 8)
)
BASEROW_WEBHOOKS_MAX_PER_TABLE = int(os.getenv("BASEROW_WEBHOOKS_MAX_PER_TABLE", 20))
BASEROW_WEBHOOKS_MAX_CALL_LOG_ENTRIES = int(
    os.getenv("BASEROW_WEBHOOKS_MAX_CALL_LOG_ENTRIES", 10)
)
BASEROW_WEBHOOKS_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("BASEROW_WEBHOOKS_REQUEST_TIMEOUT_SECONDS", 5)
)
BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS = bool(
    os.getenv("BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS", False)
)
BASEROW_WEBHOOKS_IP_BLACKLIST = [
    ip_network(ip.strip())
    for ip in os.getenv("BASEROW_WEBHOOKS_IP_BLACKLIST", "").split(",")
    if ip.strip() != ""
]
BASEROW_WEBHOOKS_IP_WHITELIST = [
    ip_network(ip.strip())
    for ip in os.getenv("BASEROW_WEBHOOKS_IP_WHITELIST", "").split(",")
    if ip.strip() != ""
]
BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST = [
    re.compile(url_regex.strip())
    for url_regex in os.getenv("BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST", "").split(",")
    if url_regex.strip() != ""
]
BASEROW_WEBHOOKS_URL_CHECK_TIMEOUT_SECS = int(
    os.getenv("BASEROW_WEBHOOKS_URL_CHECK_TIMEOUT_SECS", "10")
)
BASEROW_MAX_WEBHOOK_CALLS_IN_QUEUE_PER_WEBHOOK = (
    int(os.getenv("BASEROW_MAX_WEBHOOK_CALLS_IN_QUEUE_PER_WEBHOOK", "0")) or None
)

# ======== WARNING ========
# Please read and understand everything at:
# https://docs.djangoproject.com/en/3.2/ref/settings/#secure-proxy-ssl-header
# before enabling this setting otherwise you can compromise your site’s security.
# This setting will ensure the "next" urls provided by the various paginated API
# endpoints will be returned with https when appropriate.
# If using gunicorn also behind the proxy you might also need to set
# --forwarded-allow-ips='*'. See the following link for more information:
# https://stackoverflow.com/questions/62337379/how-to-append-nginx-ip-to-x-forwarded
# -for-in-kubernetes-nginx-ingress-controller

if bool(os.getenv("BASEROW_ENABLE_SECURE_PROXY_SSL_HEADER", False)):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS = bool(
    os.getenv("DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS", "")
)

BASEROW_BACKEND_LOG_LEVEL = os.getenv("BASEROW_BACKEND_LOG_LEVEL", "INFO")
BASEROW_BACKEND_DATABASE_LOG_LEVEL = os.getenv(
    "BASEROW_BACKEND_DATABASE_LOG_LEVEL", "ERROR"
)

BASEROW_JOB_EXPIRATION_TIME_LIMIT = int(
    os.getenv("BASEROW_JOB_EXPIRATION_TIME_LIMIT", 30 * 24 * 60)  # 30 days
)
BASEROW_JOB_SOFT_TIME_LIMIT = int(
    os.getenv("BASEROW_JOB_SOFT_TIME_LIMIT", 60 * 30)  # 30 minutes
)
BASEROW_JOB_CLEANUP_INTERVAL_MINUTES = int(
    os.getenv("BASEROW_JOB_CLEANUP_INTERVAL_MINUTES", 5)  # 5 minutes
)
BASEROW_ROW_HISTORY_CLEANUP_INTERVAL_MINUTES = int(
    os.getenv("BASEROW_ROW_HISTORY_CLEANUP_INTERVAL_MINUTES", 30)  # 30 minutes
)
BASEROW_ROW_HISTORY_RETENTION_DAYS = int(
    os.getenv("BASEROW_ROW_HISTORY_RETENTION_DAYS", 180)
)
BASEROW_MAX_ROW_REPORT_ERROR_COUNT = int(
    os.getenv("BASEROW_MAX_ROW_REPORT_ERROR_COUNT", 30)
)
BASEROW_MAX_SNAPSHOTS_PER_GROUP = int(os.getenv("BASEROW_MAX_SNAPSHOTS_PER_GROUP", 50))
BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS = int(
    os.getenv("BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS", 360)  # 360 days
)
BASEROW_USER_LOG_ENTRY_CLEANUP_INTERVAL_MINUTES = int(
    os.getenv("BASEROW_USER_LOG_ENTRY_CLEANUP_INTERVAL_MINUTES", 60)  # 60 minutes
)
# 61 days to accommodate timezone changes in admin dashboard
BASEROW_USER_LOG_ENTRY_RETENTION_DAYS = int(
    os.getenv("BASEROW_USER_LOG_ENTRY_RETENTION_DAYS", 61)
)
# The maximum number of pending invites that a workspace can have. If `0` then
# unlimited invites are allowed, which is the default value.
BASEROW_MAX_PENDING_WORKSPACE_INVITES = int(
    os.getenv("BASEROW_MAX_PENDING_WORKSPACE_INVITES", 0)
)

BASEROW_IMPORT_EXPORT_RESOURCE_CLEANUP_INTERVAL_MINUTES = int(
    os.getenv("BASEROW_IMPORT_EXPORT_RESOURCE_CLEANUP_INTERVAL_MINUTES", 5)
)
BASEROW_IMPORT_EXPORT_RESOURCE_REMOVAL_AFTER_DAYS = int(
    os.getenv("BASEROW_IMPORT_EXPORT_RESOURCE_REMOVAL_AFTER_DAYS", 5)
)

# The maximum number of rows that will be exported when exporting a table.
# If `0` then all rows will be exported.
BASEROW_IMPORT_EXPORT_TABLE_ROWS_COUNT_LIMIT = int(
    os.getenv("BASEROW_IMPORT_EXPORT_TABLE_ROWS_COUNT_LIMIT", 0)
)

PERMISSION_MANAGERS = [
    "view_ownership",
    "core",
    "setting_operation",
    "staff",
    "allow_if_template",
    "allow_public_builder",
    "element_visibility",
    "member",
    "token",
    "role",
    "basic",
]
if "baserow_enterprise" not in INSTALLED_APPS:
    PERMISSION_MANAGERS.remove("role")
if "baserow_premium" not in INSTALLED_APPS:
    PERMISSION_MANAGERS.remove("view_ownership")


OLD_ACTION_CLEANUP_INTERVAL_MINUTES = os.getenv(
    "OLD_ACTION_CLEANUP_INTERVAL_MINUTES", 5
)
MINUTES_UNTIL_ACTION_CLEANED_UP = os.getenv("MINUTES_UNTIL_ACTION_CLEANED_UP", "120")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "%(levelname)s %(asctime)s %(name)s.%(funcName)s:%(lineno)s- %("
            "message)s "
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": BASEROW_BACKEND_DATABASE_LOG_LEVEL,
            "propagate": True,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": BASEROW_BACKEND_LOG_LEVEL,
    },
}


# Now incorrectly named old variable, previously we would run `sync_templates` prior
# to starting the gunicorn server in Docker. This variable would prevent that from
# happening. Now we sync_templates in an async job triggered after migration.
# This variable if not true will now stop the async job from being triggered.
SYNC_TEMPLATES_ON_STARTUP = os.getenv("SYNC_TEMPLATES_ON_STARTUP", "true") == "true"
BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION = os.getenv(
    "BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION", None
)

if BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION is None:
    # If the new correctly named environment variable is not set, default to using
    # the old now incorrectly named SYNC_TEMPLATES_ON_STARTUP.
    BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION = SYNC_TEMPLATES_ON_STARTUP
else:
    # The new correctly named environment variable is set, so use that instead of
    # the old.
    BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION = (
        BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION == "true"
    )

BASEROW_SYNC_TEMPLATES_TIME_LIMIT = int(
    os.getenv("BASEROW_SYNC_TEMPLATES_TIME_LIMIT", 60 * 30)
)

APPEND_SLASH = False

BASEROW_DISABLE_MODEL_CACHE = bool(os.getenv("BASEROW_DISABLE_MODEL_CACHE", ""))
BASEROW_NOWAIT_FOR_LOCKS = not bool(
    os.getenv("BASEROW_WAIT_INSTEAD_OF_409_CONFLICT_ERROR", False)
)

BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED = (
    os.getenv("BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED", "viewer").strip().upper()
)

LICENSE_AUTHORITY_CHECK_TIMEOUT_SECONDS = 10
ADDITIONAL_INFORMATION_TIMEOUT_SECONDS = 10

MAX_NUMBER_CALENDAR_DAYS = 45

MIGRATION_LOCK_ID = os.getenv("BASEROW_MIGRATION_LOCK_ID", 123456)
DEFAULT_SEARCH_MODE = os.getenv("BASEROW_DEFAULT_SEARCH_MODE", "compat")


# Search specific configuration settings.
CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT = int(
    os.getenv("BASEROW_CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT", 60 * 30)
)
# By default, Baserow will use Postgres full-text as its
# search backend. If the product is installed on a system
# with limited disk space, and less accurate results / degraded
# search performance is acceptable, then switch this setting off.
USE_PG_FULLTEXT_SEARCH = str_to_bool(
    (os.getenv("BASEROW_USE_PG_FULLTEXT_SEARCH", "true"))
)
PG_SEARCH_CONFIG = os.getenv("BASEROW_PG_SEARCH_CONFIG", "simple")
AUTO_VACUUM_AFTER_SEARCH_UPDATE = str_to_bool(os.getenv("BASEROW_AUTO_VACUUM", "true"))
TSV_UPDATE_CHUNK_SIZE = int(os.getenv("BASEROW_TSV_UPDATE_CHUNK_SIZE", "2000"))

POSTHOG_PROJECT_API_KEY = os.getenv("POSTHOG_PROJECT_API_KEY", "")
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "")
POSTHOG_ENABLED = POSTHOG_PROJECT_API_KEY and POSTHOG_HOST
if POSTHOG_ENABLED:
    posthog.project_api_key = POSTHOG_PROJECT_API_KEY
    posthog.host = POSTHOG_HOST
else:
    posthog.disabled = True

BASEROW_BUILDER_DOMAINS = os.getenv("BASEROW_BUILDER_DOMAINS", None)
BASEROW_BUILDER_DOMAINS = (
    BASEROW_BUILDER_DOMAINS.split(",") if BASEROW_BUILDER_DOMAINS is not None else []
)

# Indicates whether we are running the tests or not. Set to True in the test.py settings
# file used by pytest.ini
TESTS = False


for plugin in [*BASEROW_BUILT_IN_PLUGINS, *BASEROW_BACKEND_PLUGIN_NAMES]:
    try:
        mod = importlib.import_module(plugin + ".config.settings.settings")
        # The plugin should have a setup function which accepts a 'settings' object.
        # This settings object is an AttrDict shadowing our local variables so the
        # plugin can access the Django settings and modify them prior to startup.
        result = mod.setup(AttrDict(vars()))
    except ImportError as e:
        print("Could not import %s", plugin)
        print(e)


SENTRY_BACKEND_DSN = os.getenv("SENTRY_BACKEND_DSN")
SENTRY_DSN = SENTRY_BACKEND_DSN or os.getenv("SENTRY_DSN")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(signals_spans=False, middleware_spans=False)],
        send_default_pii=False,
        environment=os.getenv("SENTRY_ENVIRONMENT", ""),
    )

BASEROW_OPENAI_API_KEY = os.getenv("BASEROW_OPENAI_API_KEY", None)
BASEROW_OPENAI_ORGANIZATION = os.getenv("BASEROW_OPENAI_ORGANIZATION", "") or None
BASEROW_OPENAI_MODELS = os.getenv("BASEROW_OPENAI_MODELS", "")
BASEROW_OPENAI_MODELS = (
    BASEROW_OPENAI_MODELS.split(",") if BASEROW_OPENAI_MODELS else []
)

BASEROW_OPENROUTER_API_KEY = os.getenv("BASEROW_OPENROUTER_API_KEY", None)
BASEROW_OPENROUTER_ORGANIZATION = (
    os.getenv("BASEROW_OPENROUTER_ORGANIZATION", "") or None
)
BASEROW_OPENROUTER_MODELS = os.getenv("BASEROW_OPENROUTER_MODELS", "")
BASEROW_OPENROUTER_MODELS = (
    BASEROW_OPENROUTER_MODELS.split(",") if BASEROW_OPENROUTER_MODELS else []
)

BASEROW_ANTHROPIC_API_KEY = os.getenv("BASEROW_ANTHROPIC_API_KEY", None)
BASEROW_ANTHROPIC_MODELS = os.getenv("BASEROW_ANTHROPIC_MODELS", "")
BASEROW_ANTHROPIC_MODELS = (
    BASEROW_ANTHROPIC_MODELS.split(",") if BASEROW_ANTHROPIC_MODELS else []
)

BASEROW_MISTRAL_API_KEY = os.getenv("BASEROW_MISTRAL_API_KEY", None)
BASEROW_MISTRAL_MODELS = os.getenv("BASEROW_MISTRAL_MODELS", "")
BASEROW_MISTRAL_MODELS = (
    BASEROW_MISTRAL_MODELS.split(",") if BASEROW_MISTRAL_MODELS else []
)

BASEROW_OLLAMA_HOST = os.getenv("BASEROW_OLLAMA_HOST", None)
BASEROW_OLLAMA_MODELS = os.getenv("BASEROW_OLLAMA_MODELS", "")
BASEROW_OLLAMA_MODELS = (
    BASEROW_OLLAMA_MODELS.split(",") if BASEROW_OLLAMA_MODELS else []
)

BASEROW_PREVENT_POSTGRESQL_DATA_SYNC_CONNECTION_TO_DATABASE = str_to_bool(
    os.getenv("BASEROW_PREVENT_POSTGRESQL_DATA_SYNC_CONNECTION_TO_DATABASE", "true")
)
BASEROW_POSTGRESQL_DATA_SYNC_BLACKLIST = os.getenv(
    "BASEROW_POSTGRESQL_DATA_SYNC_BLACKLIST", ""
)
BASEROW_POSTGRESQL_DATA_SYNC_BLACKLIST = (
    BASEROW_POSTGRESQL_DATA_SYNC_BLACKLIST.split(",")
    if BASEROW_POSTGRESQL_DATA_SYNC_BLACKLIST
    else []
)

# Default compression level for creating zip files. This setting balances the need to
# save resources when compressing media files with the need to save space when
# compressing text files.
BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL = 5

BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE = int(
    os.getenv("BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE", "") or 10
)
