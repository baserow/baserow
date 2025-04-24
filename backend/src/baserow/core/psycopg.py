from django.db import DatabaseError
from django.db.backends.postgresql.psycopg_any import is_psycopg3

if is_psycopg3:
    import psycopg  # noqa: F401
    from psycopg import errors, sql  # noqa: F401

else:
    import psycopg2 as psycopg  # noqa: F401
    from psycopg2 import errors, sql  # noqa: F401


def is_deadlock_error(exc: DatabaseError) -> bool:
    return isinstance(exc.__cause__, errors.DeadlockDetected)
