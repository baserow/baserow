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
    from psycopg2 import (  # noqa: F401
        DataError,  # noqa: F401
        errors,
        sql,
    )


def is_deadlock_error(exc: OperationalError) -> bool:
    return isinstance(exc.__cause__, errors.DeadlockDetected)


_TIGHTEN_STATEMENT_TIMEOUT_SQL = """
SELECT set_config('statement_timeout', %s, true)
WHERE current_setting('statement_timeout')::interval = interval '0'
   OR current_setting('statement_timeout')::interval > %s::interval
""".strip()


def tighten_statement_timeout(cursor, timeout_ms: int) -> None:
    """
    Lowers statement_timeout for the rest of the current transaction, but keeps a
    stricter one that is already set. The setting ends with the transaction.
    """

    timeout = f"{timeout_ms}ms"
    cursor.execute(_TIGHTEN_STATEMENT_TIMEOUT_SQL, [timeout, timeout])


def is_query_canceled_error(exc: Exception) -> bool:
    return isinstance(exc, OperationalError) and isinstance(
        exc.__cause__, errors.QueryCanceled
    )


def is_unique_violation_error(exc: Exception) -> bool:
    return isinstance(exc, IntegrityError) and isinstance(
        exc.__cause__, errors.UniqueViolation
    )


def is_index_row_size_error(exc: Exception) -> bool:
    """
    Return True when an error is raised because a btree index
    row exceeds the maximum size.

    This happens for example when existing (legacy) indexes were
    created before the ``Left()`` truncation was applied to text columns.
    """

    if not (
        isinstance(exc, OperationalError)
        and isinstance(exc.__cause__, errors.ProgramLimitExceeded)
    ):
        return False
    msg = str(exc)
    return "index" in msg and "size" in msg
