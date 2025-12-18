import os

from django.db.models.signals import post_migrate

import snoop

from .base import *  # noqa: F403, F401
from .utils import setup_dev_e2e, str_to_bool

SECRET_KEY = os.getenv("SECRET_KEY", "dev_hardcoded_secret_key")  # noqa: F405
SIMPLE_JWT["SIGNING_KEY"] = (  # noqa: F405
    os.getenv("BASEROW_JWT_SIGNING_KEY") or "dev_hardcoded_jwt_signing_key"
)


DEBUG = True
BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES = 4
BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL = 4

INSTALLED_APPS.insert(0, "daphne")  # noqa: F405
INSTALLED_APPS += ["django_extensions"]  # noqa: F405

# daphne imports numpy via autobahn -> flatbuffers, so we exclude it from the
# lazy-load check in dev mode. In production, numpy should still be lazy-loaded.
if "numpy" in BASEROW_LAZY_LOADED_LIBRARIES:  # noqa: F405
    BASEROW_LAZY_LOADED_LIBRARIES.remove("numpy")  # noqa: F405

BASEROW_ENABLE_SILK = str_to_bool(os.getenv("BASEROW_ENABLE_SILK", "on"))
if BASEROW_ENABLE_SILK:
    INSTALLED_APPS += ["silk"]  # noqa: F405
    MIDDLEWARE += [  # noqa: F405
        "silk.middleware.SilkyMiddleware",
    ]
    CACHALOT_UNCACHABLE_TABLES += [  # noqa: F405
        "silk_request",
        "silk_response",
        "silk_sqlquery",
        "silk_profile",
    ]

# Set this env var to any non-blank value in your dev env so django-silk will EXPLAIN
# all queries run.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! MASSIVE WARNING !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# This setting is DANGEROUS and will cause ALL UPDATE statements run by Baserow to be
# run twice.
# Any update statements that are not idempotent will become buggy!
# Only turn it on to analyse performance, it will break Baserow's business
# logic and cause bugs and so don't ever have it on whilst testing Baserow's
# functionality.
# See https://github.com/jazzband/django-silk/issues/629.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
SILKY_ANALYZE_QUERIES = bool(
    os.getenv("BASEROW_DANGEROUS_SILKY_ANALYZE_QUERIES", False)  # noqa: F405
)

snoop.install()

CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_USE_TLS = False
EMAIL_HOST = "mailhog"
EMAIL_PORT = 1025

BASEROW_MAX_ROW_REPORT_ERROR_COUNT = 10  # To trigger this exception easily

post_migrate.connect(setup_dev_e2e, dispatch_uid="setup_dev_e2e")


try:
    from .local import *  # noqa: F403, F401
except ImportError:
    pass
