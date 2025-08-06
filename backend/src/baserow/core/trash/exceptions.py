from baserow.core.exceptions import MaxLocksPerTransactionExceededException


class CannotRestoreChildBeforeParent(Exception):
    """
    Raised when attempting to restore a trashed item when it's parent is also trashed.
    """


class ParentIdMustBeProvidedException(Exception):
    """
    Raised when attempting to access or restore a trashed item without providing it's
    parent's id.
    """


class ParentIdMustNotBeProvidedException(Exception):
    """
    Raised when attempting to access or restore a trashed item which should not have
    it's parent id provided, but it was anyway.
    """


class CannotDeleteAlreadyDeletedItem(Exception):
    """
    Raised when attempting to delete an item which has already been deleted.
    """


class RelatedTableTrashedException(Exception):
    """
    Raised when attempting to restore a trashed field because one of its related fields
    is in a trashed table.
    """


class PermanentDeletionMaxLocksExceededException(
    MaxLocksPerTransactionExceededException
):
    """
    If too many items marked as trash are deleting in a single transaction,
    it'll quickly exceed the `max_locks_per_transaction` value set in Postgres.
    This exception is raised when we detect the scenario.
    """

    message = (
        "Baserow attempted to permanently delete trashed items, but exceeded the maximum "
        "number of PostgreSQL locks per transaction. Please read "
        "https://baserow.io/docs/technical/postgresql-locks"
    )


class CannotRestoreItemNotOwnedByUser(Exception):
    """
    Raised when attempting to restore an item that is not owned by the user.
    """


class TrashItemRestorationDisallowed(Exception):
    """
    Raised when an item cannot be restored from the trash due to specific conditions.
    This could be due to the item being in a state that does not allow restoration.
    """
