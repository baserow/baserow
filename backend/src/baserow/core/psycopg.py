from django.db import IntegrityError, OperationalError
from django.db.backends.postgresql.psycopg_any import is_psycopg3

if is_psycopg3:
    import psycopg  # noqa: F401
    from psycopg import errors, sql  # noqa: F401

    # used for date type mapping
    from psycopg.types.datetime import (  # noqa: F401
        DataError,
        DateBinaryLoader,
        DateLoader,
        TimestampBinaryLoader,
        TimestampLoader,
        TimestamptzBinaryLoader,
        TimestamptzLoader,
    )

else:
    import psycopg2 as psycopg  # noqa: F401
    from psycopg2 import DataError  # noqa: F401
    from psycopg2 import errors, sql  # noqa: F401


def is_deadlock_error(exc: OperationalError) -> bool:
    return isinstance(exc.__cause__, errors.DeadlockDetected)


def is_unique_violation_error(exc: Exception) -> bool:
    return isinstance(exc, IntegrityError) and isinstance(
        exc.__cause__, errors.UniqueViolation
    )
