import os


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

    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = int(
        os.getenv("BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS", "") or 10
    )
