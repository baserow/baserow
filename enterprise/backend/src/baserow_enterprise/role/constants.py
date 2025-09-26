from django.conf import settings

DEFAULT_ROLE_ASSIGNABLE_OBJECT_MAP = {
    "workspace": {
        "READ": "workspace.read_role",
        "UPDATE": "workspace.assign_role",
    },
    "application": {
        "READ": "application.read_role",
        "UPDATE": "application.update_role",
    },
    "database_table": {
        "READ": "database.table.read_role",
        "UPDATE": "database.table.update_role",
    },
    "database_view": {
        "READ": "database.table.view.read_role",
        "UPDATE": "database.table.view.update_role",
    },
}

ADMIN_ROLE_UID = "ADMIN"
BUILDER_ROLE_UID = "BUILDER"
EDITOR_ROLE_UID = "EDITOR"
COMMENTER_ROLE_UID = "COMMENTER"
VIEWER_ROLE_UID = "VIEWER"
NO_ACCESS_ROLE_UID = getattr(settings, "NO_ACCESS_ROLE_UID", "NO_ACCESS")
READ_ONLY_ROLE_UID = getattr(settings, "READ_ONLY_ROLE_UID", "READ_ONLY")
NO_ROLE_LOW_PRIORITY_ROLE_UID = getattr(
    settings, "NO_ROLE_LOW_PRIORITY_UID", "NO_ROLE_LOW_PRIORITY"
)
FREE_ROLE_UIDS = [
    COMMENTER_ROLE_UID,
    VIEWER_ROLE_UID,
    NO_ACCESS_ROLE_UID,
    NO_ROLE_LOW_PRIORITY_ROLE_UID,
]

ROLE_ASSIGNABLE_OBJECT_MAP = getattr(
    settings,
    "GET_ROLE_ASSIGNABLE_OBJECT_MAP",
    DEFAULT_ROLE_ASSIGNABLE_OBJECT_MAP,
)
ALLOWED_SUBJECT_TYPE_BY_PRIORITY = getattr(
    settings,
    "ALLOWED_SUBJECT_TYPE_BY_PRIORITY",
    ["auth.User", "baserow_enterprise.Team"],
)
