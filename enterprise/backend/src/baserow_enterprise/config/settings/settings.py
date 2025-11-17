import os

from baserow.config.settings.utils import enum_member_by_value
from baserow_enterprise.secure_file_serve.constants import SecureFileServePermission


def setup(settings):
    """
    This function is called after Baserow as setup its own Django settings file but
    before Django starts. Read and modify provided settings object as appropriate
    just like you would in a normal Django settings file. E.g.:

    settings.INSTALLED_APPS += ["some_custom_plugin_dep"]
    for db, value in settings.DATABASES:
        value['engine'] = 'some custom engine'
    """

    settings.BASEROW_ENTERPRISE_USER_SOURCE_COUNTING_TASK_INTERVAL_MINUTES = int(
        os.getenv("BASEROW_ENTERPRISE_USER_SOURCE_COUNTING_TASK_INTERVAL_MINUTES", "")
        or 15
    )

    settings.BASEROW_ENTERPRISE_USER_SOURCE_COUNTING_CACHE_TTL_SECONDS = int(
        # Default TTL is 120 minutes: 60 seconds * 120
        os.getenv("BASEROW_ENTERPRISE_USER_SOURCE_COUNTING_CACHE_TTL_SECONDS")
        or 7200
    )

    settings.BASEROW_ENTERPRISE_AUDIT_LOG_CLEANUP_INTERVAL_MINUTES = int(
        os.getenv("BASEROW_ENTERPRISE_AUDIT_LOG_CLEANUP_INTERVAL_MINUTES", "")
        or 24 * 60
    )

    settings.BASEROW_ENTERPRISE_AUDIT_LOG_RETENTION_DAYS = int(
        os.getenv("BASEROW_ENTERPRISE_AUDIT_LOG_RETENTION_DAYS", "") or 365
    )

    # Set this to True to enable users to login with auth providers different than
    # the one they were originally created with.
    settings.BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT = bool(
        os.getenv("BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT", False)
    )

    serve_files_through_backend_permission = (
        os.getenv("BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION", "")
        or SecureFileServePermission.DISABLED.value
    )

    settings.BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION = enum_member_by_value(
        SecureFileServePermission, serve_files_through_backend_permission
    )

    # If the expire seconds is not set to a number greater than zero, the signature will
    # never expire.
    settings.BASEROW_SERVE_FILES_THROUGH_BACKEND_EXPIRE_SECONDS = (
        int(os.getenv("BASEROW_SERVE_FILES_THROUGH_BACKEND_EXPIRE_SECONDS", "") or 0)
        or None
    )

    serve_files_through_backend = bool(
        os.getenv("BASEROW_SERVE_FILES_THROUGH_BACKEND", False)
    )
    if serve_files_through_backend:
        settings.STORAGES["default"][
            "BACKEND"
        ] = "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"

    settings.BASEROW_SERVE_FILES_THROUGH_BACKEND = serve_files_through_backend

    settings.BASEROW_ENTERPRISE_PERIODIC_DATA_SYNC_CHECK_INTERVAL_MINUTES = int(
        os.getenv("BASEROW_ENTERPRISE_PERIODIC_DATA_SYNC_CHECK_INTERVAL_MINUTES", "")
        or 1
    )
    settings.BASEROW_ENTERPRISE_MAX_PERIODIC_DATA_SYNC_CONSECUTIVE_ERRORS = int(
        os.getenv("BASEROW_ENTERPRISE_MAX_PERIODIC_DATA_SYNC_CONSECUTIVE_ERRORS", "")
        or 4
    )

    # AI Assistant settings
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = os.getenv(
        "BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL", ""
    )
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE = float(
        os.getenv("BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE", "") or 0.3
    )
