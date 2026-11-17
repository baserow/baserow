from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_SNAPSHOT_DOES_NOT_EXIST = (
    "ERROR_SNAPSHOT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested snapshot does not exist.",
)

ERROR_MAXIMUM_SNAPSHOTS_REACHED = (
    "ERROR_MAXIMUM_SNAPSHOTS_REACHED",
    HTTP_400_BAD_REQUEST,
    "The group has already reached the snapshot limit.",
)

ERROR_SNAPSHOT_IS_BEING_CREATED = (
    "ERROR_SNAPSHOT_IS_BEING_CREATED",
    HTTP_400_BAD_REQUEST,
    "Snapshots creation is already in progress for the application.",
)

ERROR_SNAPSHOT_IS_BEING_RESTORED = (
    "ERROR_SNAPSHOT_IS_BEING_RESTORED",
    HTTP_400_BAD_REQUEST,
    "Snapshots can't be manipulated while being restored.",
)

ERROR_SNAPSHOT_IS_BEING_DELETED = (
    "ERROR_SNAPSHOT_IS_BEING_DELETED",
    HTTP_400_BAD_REQUEST,
    "Snapshots can't be manipulated while being deleted.",
)

ERROR_SNAPSHOT_NAME_NOT_UNIQUE = (
    "ERROR_SNAPSHOT_NAME_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "Snapshots names must be unique per application.",
)

ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED = (
    "ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED",
    HTTP_400_BAD_REQUEST,
    "The limit of number of the same operation exceeded by the user.",
)

ERROR_SNAPSHOT_KEEP_IS_ZERO = (
    "ERROR_SNAPSHOT_KEEP_IS_ZERO",
    HTTP_400_BAD_REQUEST,
    "The application keeps no snapshots. Raise its keep to take one.",
)

ERROR_SNAPSHOT_KEEP_FULL_OF_PROTECTED = (
    "ERROR_SNAPSHOT_KEEP_FULL_OF_PROTECTED",
    HTTP_400_BAD_REQUEST,
    "The application is at its keep and every snapshot it holds is protected. "
    "Raise its keep, or delete or unprotect a snapshot.",
)

ERROR_SNAPSHOT_KEEP_EXCEEDS_ALLOWANCE = (
    "ERROR_SNAPSHOT_KEEP_EXCEEDS_ALLOWANCE",
    HTTP_400_BAD_REQUEST,
    "Not enough of the workspace's snapshot allowance is left for this keep.",
)

ERROR_SNAPSHOT_KEEP_ABOVE_MAXIMUM = (
    "ERROR_SNAPSHOT_KEEP_ABOVE_MAXIMUM",
    HTTP_400_BAD_REQUEST,
    "The keep is above the most snapshots an application can keep.",
)

ERROR_SNAPSHOT_KEEP_BELOW_PROTECTED = (
    "ERROR_SNAPSHOT_KEEP_BELOW_PROTECTED",
    HTTP_400_BAD_REQUEST,
    "A keep can't be lower than the number of protected snapshots an application "
    "holds.",
)


def ERROR_SNAPSHOT_KEEP_CHANGE_DELETES_SNAPSHOTS(e):
    return (
        "ERROR_SNAPSHOT_KEEP_CHANGE_DELETES_SNAPSHOTS",
        HTTP_400_BAD_REQUEST,
        f"Lowering the keep deletes {e.count} snapshot(s). Send `delete_snapshots` "
        "to confirm.",
    )
