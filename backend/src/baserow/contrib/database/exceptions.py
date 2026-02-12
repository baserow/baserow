from baserow.core.exceptions import MaxLocksPerTransactionExceededException


class DatabaseDoesNotBelongToGroup(Exception):
    """Raised when the database does not belong to the related group."""


class DatabaseSnapshotMaxLocksExceededException(
    MaxLocksPerTransactionExceededException
):
    """
    If a Database has a snapshot issued against it, and it contains a very large
    number of tables, it'll quickly exceed the `max_locks_per_transaction` value
    set in Postgres. This exception is raised when we detect the scenario.
    """

    message = (
        "TCR Projects attempted to snapshot a database, but exceeded the maximum "
        "number of PostgreSQL locks per transaction. Please read "
        "https://tcrprojects.com/docs/technical/postgresql-locks"
    )
