import random

from django.conf import settings
from django.db import transaction

from asgiref.local import Local

DEFAULT_DB_ALIAS = "default"

_db_state = Local()


def set_db_alias(alias: str) -> str:
    """
    Pin the current db connection alias to use for the current request or celery task.

    :param alias: The database alias to pin to.
    :return: The database alias that was set.
    """

    _db_state.alias = alias
    return alias


def get_db_alias() -> str | None:
    """
    Get the pinned db connection alias for the current request or celery task.
    """

    return getattr(_db_state, "alias", None)


def set_db_alias_for_read():
    """
    Choose a read replica for read queries, unless we are in an atomic block,
    in which case we should use the primary database to avoid replication lag issues
    or trying to lock data in a read replica.
    Once a read replica is chosen, it is pinned for the duration of the request or
    celery task.

    :return: The database alias to use for read queries.
    """

    # Make sure LOCK always happen on the DEFAULT_DB_ALIAS
    if transaction.get_connection().in_atomic_block:
        return set_db_alias(DEFAULT_DB_ALIAS)

    # If we already have an alias set, return it
    if (alias := get_db_alias()) is not None:
        return alias

    # Choose a random read replica if available, otherwise use the default
    if settings.DATABASE_READ_REPLICAS:
        alias = random.choice(settings.DATABASE_READ_REPLICAS)  # nosec
    else:
        alias = DEFAULT_DB_ALIAS

    return set_db_alias(alias)


def clear_db_state():
    """Should be called when a request or celery finishes."""

    if hasattr(_db_state, "alias"):
        del _db_state.alias


class ReadReplicaRouter:
    """
    If `DATABASE_READ_REPLICAS` replicas are configured, then this routes ensures that
    if a read query is executed, it will use one of the read replicas. If a write query
    is must be executed, then it switches to the write node, and sticks with it until
    the db state is cleared. That is currently happening when a request or celery task
    is completed.
    """

    def db_for_read(self, model, **hints):
        return set_db_alias_for_read()

    def db_for_write(self, model, **hints):
        return set_db_alias(DEFAULT_DB_ALIAS)

    def allow_relation(self, obj1, obj2, **hints):
        db_set = {DEFAULT_DB_ALIAS}
        db_set.update(settings.DATABASE_READ_REPLICAS)
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == DEFAULT_DB_ALIAS
