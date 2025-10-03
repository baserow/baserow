import random

from django.conf import settings

from asgiref.local import Local

DATABASE_READ_REPLICAS = settings.DATABASE_READ_REPLICAS
DEFAULT_DB_ALIAS = "default"

_db_state = Local()


def set_write_mode():
    _db_state.pinned = True


def is_write_mode():
    return getattr(_db_state, "pinned", False)


def clear_db_state():
    """Should be called when a request or celery finishes."""

    if hasattr(_db_state, "pinned"):
        del _db_state.pinned
    if hasattr(_db_state, "read_alias"):
        del _db_state.read_alias


def get_read_alias():
    return getattr(_db_state, "read_alias", None)


def set_read_alias(alias: str):
    _db_state.read_alias = alias


class ReadReplicaRouter:
    """
    If `DATABASE_READ_REPLICAS` replicas are configured, then this routes ensures that
    if a read query is executed, it will use one of the read replicas. If a write query
    is must be executed, then it switches to the write node, and sticks with it until
    the db state is cleared. That is currently happening when a request or celery task
    is completed.
    """

    def db_for_read(self, model, **hints):
        if is_write_mode():
            return DEFAULT_DB_ALIAS
        alias = get_read_alias()
        if alias:
            return alias
        if DATABASE_READ_REPLICAS:
            read_replica = random.choice(DATABASE_READ_REPLICAS)  # nosec
            set_read_alias(read_replica)
            return read_replica
        return DEFAULT_DB_ALIAS

    def db_for_write(self, model, **hints):
        set_write_mode()
        return DEFAULT_DB_ALIAS

    def allow_relation(self, obj1, obj2, **hints):
        db_set = {DEFAULT_DB_ALIAS}
        db_set.update(DATABASE_READ_REPLICAS)
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == DEFAULT_DB_ALIAS
