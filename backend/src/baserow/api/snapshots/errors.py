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

ERROR_MAX_SNAPSHOTS_IS_ZERO = (
    "ERROR_MAX_SNAPSHOTS_IS_ZERO",
    HTTP_400_BAD_REQUEST,
    "The application keeps no snapshots. Raise its max snapshots to take one.",
)

ERROR_MAX_SNAPSHOTS_FULL_OF_PROTECTED = (
    "ERROR_MAX_SNAPSHOTS_FULL_OF_PROTECTED",
    HTTP_400_BAD_REQUEST,
    "The application is at its max snapshots and every snapshot it holds is protected. "
    "Raise its max snapshots, or delete or unprotect a snapshot.",
)

ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE = (
    "ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE",
    HTTP_400_BAD_REQUEST,
    "Not enough of the workspace's snapshot allowance is left for this max snapshots.",
)

ERROR_MAX_SNAPSHOTS_ABOVE_LIMIT = (
    "ERROR_MAX_SNAPSHOTS_ABOVE_LIMIT",
    HTTP_400_BAD_REQUEST,
    "The max snapshots is above the most snapshots an application can keep.",
)

ERROR_MAX_SNAPSHOTS_BELOW_PROTECTED = (
    "ERROR_MAX_SNAPSHOTS_BELOW_PROTECTED",
    HTTP_400_BAD_REQUEST,
    "A max can't be lower than the number of protected snapshots an application holds.",
)


def ERROR_MAX_SNAPSHOTS_CHANGE_DELETES_SNAPSHOTS(e):
    return (
        "ERROR_MAX_SNAPSHOTS_CHANGE_DELETES_SNAPSHOTS",
        HTTP_400_BAD_REQUEST,
        f"Lowering the max snapshots deletes {e.count} snapshot(s). Send "
        f"`delete_snapshots` to confirm.",
    )
