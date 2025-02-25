import re
from contextlib import contextmanager
from functools import wraps

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.transaction import get_connection

from django_redis import get_redis_connection
from loguru import logger

from baserow.core.psycopg import sql

if settings.CACHALOT_ENABLED:
    from cachalot.settings import cachalot_disabled, cachalot_settings  # noqa: F401

    @contextmanager
    def cachalot_enabled():
        """
        A context manager that enables cachalot for the duration of the context. This is
        useful when you want to enable cachalot for a specific query but you don't want
        to enable it globally. Please note that the query have to be executed within the
        context of the context manager in order for it to be cached.
        """

        from cachalot.api import LOCAL_STORAGE

        was_enabled = getattr(
            LOCAL_STORAGE, "cachalot_enabled", cachalot_settings.CACHALOT_ENABLED
        )
        LOCAL_STORAGE.cachalot_enabled = True
        try:
            yield
        finally:
            LOCAL_STORAGE.cachalot_enabled = was_enabled

else:

    @contextmanager
    def cachalot_enabled():
        yield

    @contextmanager
    def cachalot_disabled():
        yield


def patch_cachalot_for_baserow():
    """
    This function patches the cachalot library to make it work with baserow dynamic
    models. The problem we're trying to solve here is that the only way to limit what
    cachalot caches is to provide a fix list of tables, but baserow creates dynamic
    models on the fly so we can't know what tables will be created in advance, so we
    need to include all the tables that start with the USER_TABLE_DATABASE_NAME_PREFIX
    prefix in the list of cachable tables.

    `filter_cachable` and `is_cachable` are called to invalidate the cache when a table
    is changed. `are_all_cachable` is called to check if a query can be cached.
    """

    from cachalot import utils as cachalot_utils

    from baserow.contrib.database.table.constants import (
        LINK_ROW_THROUGH_TABLE_PREFIX,
        MULTIPLE_COLLABORATOR_THROUGH_TABLE_PREFIX,
        MULTIPLE_SELECT_THROUGH_TABLE_PREFIX,
        USER_TABLE_DATABASE_NAME_PREFIX,
    )

    original_filter_cachable = cachalot_utils.filter_cachable

    # create a single regex to match if a string provided starts with any of the
    # prefixes we want to match followed by a number
    baserow_table_names_regex = re.compile(
        r"^(?:{}|{}|{}|{})\d+".format(
            USER_TABLE_DATABASE_NAME_PREFIX,
            LINK_ROW_THROUGH_TABLE_PREFIX,
            MULTIPLE_COLLABORATOR_THROUGH_TABLE_PREFIX,
            MULTIPLE_SELECT_THROUGH_TABLE_PREFIX,
        )
    )

    def is_baserow_table(table_name):
        uncachable_tables = getattr(settings, "CACHALOT_UNCACHABLE_TABLES", [])
        return (
            table_name not in uncachable_tables
            and baserow_table_names_regex.match(table_name) is not None
        )

    @wraps(original_filter_cachable)
    def patched_filter_cachable(tables):
        return original_filter_cachable(tables).union(
            set(filter(is_baserow_table, tables))
        )

    cachalot_utils.filter_cachable = patched_filter_cachable

    original_is_cachable = cachalot_utils.is_cachable

    @wraps(original_is_cachable)
    def patched_is_cachable(table):
        return is_baserow_table(table) or original_is_cachable(table)

    cachalot_utils.is_cachable = patched_is_cachable

    original_are_all_cachable = cachalot_utils.are_all_cachable

    @wraps(original_are_all_cachable)
    def patched_are_all_cachable(tables):
        """
        This patch works because cachalot does not explicitly set this thread local
        variable, but it assumes to be True by default if CACHALOT_ENABLED is not set
        otherwise. Since we are explicitly setting it to True in our code for the query
        we want to cache, we can check if the value has been set or not to exclude our
        dynamic tables from the list of tables that cachalot will check, making all of
        them cachable for the queries wrapped in the `cachalot_enabled` context manager.
        """

        from cachalot.api import LOCAL_STORAGE

        cachalot_enabled = getattr(LOCAL_STORAGE, "cachalot_enabled", False)
        if cachalot_enabled:
            tables = set(filter(lambda t: not is_baserow_table(t), tables))
        return original_are_all_cachable(tables)

    cachalot_utils.are_all_cachable = patched_are_all_cachable

    baserow_tables_regex = re.compile(
        r"({}\d+|{}\d+|{}\d+|{}\d+)".format(
            USER_TABLE_DATABASE_NAME_PREFIX,
            LINK_ROW_THROUGH_TABLE_PREFIX,
            MULTIPLE_COLLABORATOR_THROUGH_TABLE_PREFIX,
            MULTIPLE_SELECT_THROUGH_TABLE_PREFIX,
        )
    )
    original_get_tables_from_sql = cachalot_utils._get_tables_from_sql

    @wraps(original_get_tables_from_sql)
    def patched_get_tables_from_sql(
        connection, lowercased_sql, enable_quote: bool = False
    ):
        baserow_tables = baserow_tables_regex.findall(lowercased_sql)
        return set(baserow_tables) | original_get_tables_from_sql(
            connection, lowercased_sql, enable_quote
        )

    cachalot_utils._get_tables_from_sql = patched_get_tables_from_sql

    def lower(self):
        """
        Cachalot wants this method to lowercase the queries to check if they are
        cachable, but the Composed class in psycopg.sql does not have a lower
        method, so we add it here to add the support for it.
        """

        cursor = get_connection().cursor()
        return self.as_string(cursor.cursor).lower()

    sql.Composed.lower = lower


def clear_cachalot_cache():
    """
    This function clears the cachalot cache. It can be used in the tests to make sure
    that the cache is cleared between tests or as post_migrate receiver to ensure to
    start with a clean cache after migrations.
    """

    from django.conf import settings
    from django.core.cache import caches

    logger.info("Clearing cachalot cache")
    try:
        cachalot_cache = caches[settings.CACHALOT_CACHE]
    except KeyError:
        raise ImproperlyConfigured(
            f"Could not find the {settings.CACHALOT_CACHE} cache."
        )

    if settings.TESTS:
        cachalot_cache.clear()
    else:
        key_prefix = settings.CACHES[settings.CACHALOT_CACHE]["KEY_PREFIX"]

        count = _delete_pattern(key_prefix)

        logger.info(f"Done clearing cachalot cache, cleared {count} entries.")


def _delete_pattern(key_prefix: str) -> int:
    """
    Allows deleting every redis key that matches a pattern. Copied from the django-redis
    implementation but modified to allow deleting all versions in the cache at once.
    """

    client = get_redis_connection("default")
    count = 0
    pipeline = client.pipeline()
    for key in client.scan_iter(match=f"{key_prefix}*", count=1000):
        pipeline.delete(key)
        count += 1
    pipeline.execute()
    return count
