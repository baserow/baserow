import random

from django.conf import settings
from django.db import transaction

from asgiref.local import Local

DEFAULT_DB_ALIAS = "default"

_db_state = Local()


def set_db_alias(alias: str):
    _db_state.alias = alias


def get_db_alias():
    alias = getattr(_db_state, "alias", None)
    if alias:
        return alias
    if settings.DATABASE_READ_REPLICAS:
        read_replica = random.choice(settings.DATABASE_READ_REPLICAS)  # nosec
        _db_state.alias = read_replica
        return read_replica
    _db_state.alias = DEFAULT_DB_ALIAS
    return DEFAULT_DB_ALIAS


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
        conn = transaction.get_connection()
        if getattr(conn, "in_atomic_block", False):
            set_db_alias(DEFAULT_DB_ALIAS)
            return DEFAULT_DB_ALIAS
        return get_db_alias()

    def db_for_write(self, model, **hints):
        set_db_alias(DEFAULT_DB_ALIAS)
        return DEFAULT_DB_ALIAS

    def allow_relation(self, obj1, obj2, **hints):
        db_set = {DEFAULT_DB_ALIAS}
        db_set.update(settings.DATABASE_READ_REPLICAS)
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == DEFAULT_DB_ALIAS
