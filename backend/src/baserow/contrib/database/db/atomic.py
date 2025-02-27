from django.db.transaction import Atomic

from baserow.cachalot_patch import cachalot_disabled
from baserow.core.db import IsolationLevel, sql, transaction_atomic


def read_repeatable_single_database_atomic_transaction(
    database_id: int,
) -> Atomic:
    """
    If you want to safely read the contents of a Baserow database inside of a single
    transaction and be guaranteed to see a single snapshot of the metadata and user
    data contained within the Baserow db tables then use this atomic transaction context
    manager.

    This manager does two things to ensure this:
    1. It runs in the REPEATABLE READ postgres isolation level, meaning all queries
       will see a snapshot of the database starting at the first SELECT etc statement
       run instead the transaction.
    2. This query runs that first transaction itself and intentionally locks all field
       and table metadata rows in this first SELECT statement FOR KEY SHARE. This means
       once the transaction has obtained this lock it can proceed safely without
       having to worry about fields being updated during the length of the transaction.
       We need to lock these rows as otherwise Baserow's various endpoints can
       execute ALTER TABLE and DROP TABLE statements which are not MVCC safe and will
       break the snapshot obtained by REPEATABLE READ, see
       https://www.postgresql.org/docs/current/mvcc-caveats.html for more info.

    :param database_id: The database to obtain table and field locks for to ensure
        safe reading.
    :return: An atomic context manager.
    """

    # It is critical we obtain the locks in the first SELECT statement run in the
    # REPEATABLE READ transaction so we are given a snapshot that is guaranteed to never
    # have harmful MVCC operations run on it.
    first_statement = sql.SQL(
        """
 SELECT * FROM database_field
 INNER JOIN database_table ON database_field.table_id = database_table.id
 WHERE database_table.database_id = {0} FOR KEY SHARE OF database_field, database_table
"""
    )
    first_statement_args = [sql.Literal(database_id)]
    with cachalot_disabled():
        return transaction_atomic(
            isolation_level=IsolationLevel.REPEATABLE_READ,
            first_sql_to_run_in_transaction_with_args=(
                first_statement,
                first_statement_args,
            ),
        )


def read_committed_single_table_transaction(
    table_id: int,
) -> Atomic:
    """
    If you want to safely read the contents of a Baserow table inside of a single
    transaction and be guaranteed that the fields wont change during the transaction no
    unsafe MVCC operations can occur during the transaction then use this context
    manager.

    This manager does one thing to ensure this:
    1. This query runs that first transaction itself and intentionally locks all field
       and the table's metadata row in this first SELECT statement FOR KEY SHARE. This
       means once the transaction has obtained this lock it can proceed safely without
       having to worry about fields being updated during the length of the transaction.
       We need to lock these rows as otherwise Baserow's various endpoints can
       execute ALTER TABLE and DROP TABLE statements which are not MVCC safe and can
       cause
       https://www.postgresql.org/docs/current/mvcc-caveats.html for more info.


    This manager uses READ COMMITTED and as such has a lower overhead, but does not get
    the snapshot like reading guarantees that REAPEATABLE READ does.

    :param table_id: The table to obtain a table and field locks for to ensure
        safe reading.
    :return: An atomic context manager.
    """

    first_statement = sql.SQL(
        """
 SELECT * FROM database_field
 INNER JOIN database_table ON database_field.table_id = database_table.id
 WHERE database_table.id = {0} FOR KEY SHARE OF database_field, database_table
"""
    )
    first_statement_args = [sql.Literal(table_id)]
    return transaction_atomic(
        first_sql_to_run_in_transaction_with_args=(
            first_statement,
            first_statement_args,
        ),
    )


def read_repeatable_read_single_table_transaction(
    table_id: int,
) -> Atomic:
    """
    If you want to safely read the contents of a Baserow table inside of a single
    transaction and be guaranteed that the fields wont change during the transaction no
    unsafe MVCC operations can occur during the transaction then use this context
    manager.

    This manager does two things to ensure this:
    1. It runs in the REPEATABLE READ postgres isolation level, meaning all queries
       will see a snapshot of the table starting at the first SELECT etc statement
       run instead the transaction.
    2. This query runs that first transaction itself and intentionally locks all field
       and the table's metadata row in this first SELECT statement FOR SHARE. This
       means once the transaction has obtained this lock it can proceed safely without
       having to worry about fields being updated during the length of the transaction.
       We need to lock these rows as otherwise Baserow's various endpoints can
       execute ALTER TABLE and DROP TABLE statements which are not MVCC safe and can
       cause
       https://www.postgresql.org/docs/current/mvcc-caveats.html for more info.


    This manager uses REPEATABLE READ to guarantee a valid snapshot of the data.

    :param table_id: The table to obtain a table and field locks for to ensure
        safe reading.
    :return: An atomic context manager.
    """

    first_statement = sql.SQL(
        """
 SELECT * FROM database_field
 INNER JOIN database_table ON database_field.table_id = database_table.id
 WHERE database_table.id = {0} FOR KEY SHARE OF database_field, database_table
"""
    )
    first_statement_args = [sql.Literal(table_id)]
    with cachalot_disabled():
        return transaction_atomic(
            isolation_level=IsolationLevel.REPEATABLE_READ,
            first_sql_to_run_in_transaction_with_args=(
                first_statement,
                first_statement_args,
            ),
        )
