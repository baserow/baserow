from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_TRASH_ITEM_DOES_NOT_EXIST = (
    "ERROR_TRASH_ITEM_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested trash item does not exist.",
)

ERROR_CANNOT_RESTORE_PARENT_BEFORE_CHILD = (
    "ERROR_CANNOT_RESTORE_PARENT_BEFORE_CHILD",
    HTTP_400_BAD_REQUEST,
    "Cannot restore a trashed item if it's parent is also trashed, please restore the "
    "parent first.",
)

ERROR_PARENT_ID_MUST_BE_PROVIDED = (
    "ERROR_PARENT_ID_MUST_BE_PROVIDED",
    HTTP_400_BAD_REQUEST,
    "A parent id must be provided when using this trashable item type.",
)

ERROR_PARENT_ID_MUST_NOT_BE_PROVIDED = (
    "ERROR_PARENT_ID_MUST_NOT_BE_PROVIDED",
    HTTP_400_BAD_REQUEST,
    "A parent id must NOT be provided when using this trashable item type.",
)

ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM = (
    "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM",
    HTTP_400_BAD_REQUEST,
    "This item has already been deleted.",
)

ERROR_CANT_RESTORE_AS_RELATED_TABLE_TRASHED = (
    "ERROR_CANT_RESTORE_AS_RELATED_TABLE_TRASHED",
    HTTP_400_BAD_REQUEST,
    "This field cannot be restored as it depends on another table which is still "
    "trashed.",
)

ERROR_CANNOT_RESTORE_ITEM_NOT_OWNED_BY_USER = (
    "ERROR_CANNOT_RESTORE_ITEM_NOT_OWNED_BY_USER",
    HTTP_400_BAD_REQUEST,
    "This item cannot be restored as it is not owned by the user.",
)

ERROR_TRASH_ITEM_RESTORATION_DISALLOWED = (
    "ERROR_TRASH_ITEM_DISALLOWED",
    HTTP_400_BAD_REQUEST,
    "{e}",
)
