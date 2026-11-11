from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_TEAM_NAME_NOT_UNIQUE = (
    "ERROR_TEAM_NAME_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The specified team name is already in use in this workspace.",
)

ERROR_TEAM_DOES_NOT_EXIST = (
    "ERROR_TEAM_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested team does not exist.",
)

ERROR_SUBJECT_DOES_NOT_EXIST = (
    "ERROR_SUBJECT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested subject does not exist.",
)

ERROR_SUBJECT_TYPE_UNSUPPORTED = (
    "ERROR_SUBJECT_TYPE_UNSUPPORTED",
    HTTP_400_BAD_REQUEST,
    "The specified subject type is not supported.",
)

ERROR_SUBJECT_BAD_REQUEST = (
    "ERROR_SUBJECT_BAD_REQUEST",
    HTTP_400_BAD_REQUEST,
    "An ID or email address is required.",
)

ERROR_SUBJECT_NOT_IN_GROUP = (
    "ERROR_SUBJECT_NOT_IN_GROUP",
    HTTP_400_BAD_REQUEST,
    "The specified subject does not belong to this team's workspace.",
)

ERROR_ROLE_DOES_NOT_EXIST = (
    "ERROR_ROLE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The specified role does not exist.",
)

ERROR_SCOPE_DOES_NOT_EXIST = (
    "ERROR_SCOPE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested scope does not exist.",
)

ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST = (
    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested scope type does not exist.",
)

ERROR_SUBJECT_TYPE_DOES_NOT_EXIST = (
    "ERROR_SUBJECT_TYPE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested subject type does not exist.",
)

ERROR_ROLE_DOES_NOT_EXIST = (
    "ERROR_ROLE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested role does not exist.",
)

ERROR_DUPLICATE_ROLE_ASSIGNMENTS = (
    "ERROR_DUPLICATE_ROLE_ASSIGNMENTS",
    HTTP_400_BAD_REQUEST,
    "The list of role assignments includes duplicates at indexes: {e.indexes}",
)

ERROR_CANT_ASSIGN_ROLE_EXCEPTION_TO_ADMIN = (
    "ERROR_CANT_ASSIGN_ROLE_EXCEPTION_TO_ADMIN",
    HTTP_400_BAD_REQUEST,
    "You can't assign a role exception to a scope with ADMIN role.",
)

ERROR_CANT_ASSIGN_ROLE_TO_SELF = (
    "ERROR_CANT_ASSIGN_ROLE_TO_SELF",
    HTTP_400_BAD_REQUEST,
    "You can't assign a role to yourself. Ask another admin.",
)

ERROR_LAST_ADMIN_OF_GROUP = (
    "ERROR_LAST_ADMIN_OF_GROUP",
    HTTP_400_BAD_REQUEST,
    "You can't remove the last admin of a workspace.",
)

ERROR_SCOPED_INVITATION_DOES_NOT_EXIST = (
    "ERROR_SCOPED_INVITATION_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested scoped invitation does not exist.",
)
