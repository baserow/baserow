from baserow.core.user.registries import ChoiceUserPreferenceType


class AllWorkspacesSortByPreferenceType(ChoiceUserPreferenceType):
    """
    Sort order of the all workspaces page. Must stay in sync with the `SORT_BY_*`
    constants in `web-frontend/modules/core/utils/allWorkspaces.js`.
    """

    type = "all_workspaces_sort_by"
    choices = ["created", "last_viewed", "name_asc", "name_desc"]
    default = "last_viewed"


class AllWorkspacesViewModePreferenceType(ChoiceUserPreferenceType):
    type = "all_workspaces_view_mode"
    choices = ["expanded", "compact"]
    default = "expanded"


class RecentlyViewedViewModePreferenceType(ChoiceUserPreferenceType):
    type = "recently_viewed_view_mode"
    choices = ["table", "cards"]
    default = "table"


class WorkspaceRecentlyViewedViewModePreferenceType(ChoiceUserPreferenceType):
    """
    Same switch as `recently_viewed_view_mode`, remembered separately for the list
    on the workspace homepage.
    """

    type = "workspace_recently_viewed_view_mode"
    choices = ["table", "cards"]
    default = "table"
