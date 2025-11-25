import os

from django.core.exceptions import ImproperlyConfigured

from baserow.config.settings.utils import try_int


def setup(settings):
    """
    This function is called after Baserow as setup its own Django settings file but
    before Django starts. Read and modify provided settings object as appropriate
    just like you would in a normal Django settings file. E.g.:

    settings.INSTALLED_APPS += ["some_custom_plugin_dep"]
    for db, value in settings.DATABASES:
        value['engine'] = 'some custom engine'
    """

    # How many row comments can be requested at once.
    settings.ROW_COMMENT_PAGE_SIZE_LIMIT = 200

    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES = int(
        os.getenv("BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES", "") or 3
    )

    BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = int(
        os.getenv("BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS", "") or 10
    )
    if BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS < 1:
        raise ImproperlyConfigured(
            "BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS "
            "has to be bigger than 0."
        )

    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = (
        BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS
    )

    # Used to limit thread pool size for running AI field generation in parallel
    settings.BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS = try_int(
        os.getenv("BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS"), 5
    )
