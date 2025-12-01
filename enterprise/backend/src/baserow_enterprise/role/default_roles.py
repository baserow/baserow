from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from baserow_premium.row_comments.operations import (
    CreateRowCommentsOperationType,
    DeleteRowCommentsOperationType,
    ReadRowCommentsOperationType,
    RestoreRowCommentOperationType,
    UpdateRowCommentsOperationType,
)

from baserow.contrib.automation.nodes.operations import (
    CreateAutomationNodeOperationType,
    DeleteAutomationNodeOperationType,
    DuplicateAutomationNodeOperationType,
    ListAutomationNodeOperationType,
    OrderAutomationNodeOperationType,
    ReadAutomationNodeOperationType,
    RestoreAutomationNodeOperationType,
    UpdateAutomationNodeOperationType,
)
from baserow.contrib.automation.operations import (
    ListAutomationWorkflowsOperationType,
    OrderAutomationWorkflowsOperationType,
)
from baserow.contrib.automation.workflows.operations import (
    CreateAutomationWorkflowOperationType,
    DeleteAutomationWorkflowOperationType,
    DuplicateAutomationWorkflowOperationType,
    PublishAutomationWorkflowOperationType,
    ReadAutomationWorkflowOperationType,
    RestoreAutomationWorkflowOperationType,
    UpdateAutomationWorkflowOperationType,
)
from baserow.contrib.builder.data_sources.operations import (
    CreateDataSourceOperationType,
    DeleteDataSourceOperationType,
    DispatchDataSourceOperationType,
    ListDataSourcesPageOperationType,
    OrderDataSourcesPageOperationType,
    ReadDataSourceOperationType,
    UpdateDataSourceOperationType,
)
from baserow.contrib.builder.domains.operations import (
    CreateDomainOperationType,
    DeleteDomainOperationType,
    PublishDomainOperationType,
    ReadDomainOperationType,
    RestoreDomainOperationType,
    UpdateDomainOperationType,
)
from baserow.contrib.builder.elements.operations import (
    CreateElementOperationType,
    DeleteElementOperationType,
    ListElementsPageOperationType,
    OrderElementsPageOperationType,
    ReadElementOperationType,
    UpdateElementOperationType,
)
from baserow.contrib.builder.operations import (
    ListDomainsBuilderOperationType,
    ListPagesBuilderOperationType,
    OrderDomainsBuilderOperationType,
    OrderPagesBuilderOperationType,
)
from baserow.contrib.builder.pages.operations import (
    CreatePageOperationType,
    DeletePageOperationType,
    DuplicatePageOperationType,
    ReadPageOperationType,
    UpdatePageOperationType,
)
from baserow.contrib.builder.theme.operations import UpdateThemeOperationType
from baserow.contrib.builder.workflow_actions.operations import (
    CreateBuilderWorkflowActionOperationType,
    DeleteBuilderWorkflowActionOperationType,
    DispatchBuilderWorkflowActionOperationType,
    ListBuilderWorkflowActionsPageOperationType,
    OrderBuilderWorkflowActionOperationType,
    ReadBuilderWorkflowActionOperationType,
    UpdateBuilderWorkflowActionOperationType,
)
from baserow.contrib.dashboard.data_sources.operations import (
    CreateDashboardDataSourceOperationType,
    DeleteDashboardDataSourceOperationType,
    DispatchDashboardDataSourceOperationType,
    ListDashboardDataSourcesOperationType,
    ReadDashboardDataSourceOperationType,
    UpdateDashboardDataSourceOperationType,
)
from baserow.contrib.dashboard.widgets.operations import (
    CreateWidgetOperationType,
    DeleteWidgetOperationType,
    ListWidgetsOperationType,
    ReadWidgetOperationType,
    RestoreWidgetOperationType,
    UpdateWidgetOperationType,
)
from baserow.contrib.database.airtable.operations import (
    RunAirtableImportJobOperationType,
)
from baserow.contrib.database.data_sync.operations import (
    GetIncludingPublicValuesOperationType,
    ListPropertiesOperationType,
    SyncTableOperationType,
)
from baserow.contrib.database.export.operations import ExportTableOperationType
from baserow.contrib.database.field_rules.operations import (
    ReadFieldRuleOperationType,
    SetFieldRuleOperationType,
)
from baserow.contrib.database.fields.operations import (
    CreateFieldOperationType,
    DeleteFieldOperationType,
    DeleteRelatedLinkRowFieldOperationType,
    DuplicateFieldOperationType,
    ListFieldsOperationType,
    ReadFieldOperationType,
    RestoreFieldOperationType,
    UpdateFieldOperationType,
)
from baserow.contrib.database.formula import TypeFormulaOperationType
from baserow.contrib.database.operations import (
    CreateTableDatabaseTableOperationType,
    ListTablesDatabaseTableOperationType,
    OrderTablesDatabaseTableOperationType,
)
from baserow.contrib.database.rows.operations import (
    DeleteDatabaseRowOperationType,
    MoveRowDatabaseRowOperationType,
    ReadAdjacentRowDatabaseRowOperationType,
    ReadDatabaseRowHistoryOperationType,
    ReadDatabaseRowOperationType,
    RestoreDatabaseRowOperationType,
    UpdateDatabaseRowOperationType,
)
from baserow.contrib.database.table.operations import (
    CreateRowDatabaseTableOperationType,
    DeleteDatabaseTableOperationType,
    DuplicateDatabaseTableOperationType,
    ImportRowsDatabaseTableOperationType,
    ListenToAllDatabaseTableEventsOperationType,
    ListRowNamesDatabaseTableOperationType,
    ListRowsDatabaseTableOperationType,
    ReadDatabaseTableOperationType,
    RestoreDatabaseTableOperationType,
    UpdateDatabaseTableOperationType,
)
from baserow.contrib.database.tokens.operations import (
    CreateTokenOperationType,
    ReadTokenOperationType,
    UpdateTokenOperationType,
    UseTokenOperationType,
)
from baserow.contrib.database.views.operations import (
    CanReceiveNotificationOnSubmitFormViewOperationType,
    CreateAndUsePersonalViewOperationType,
    CreatePublicViewOperationType,
    CreateViewDecorationOperationType,
    CreateViewFilterGroupOperationType,
    CreateViewFilterOperationType,
    CreateViewGroupByOperationType,
    CreateViewOperationType,
    CreateViewRowOperationType,
    CreateViewSortOperationType,
    DeleteViewDecorationOperationType,
    DeleteViewFilterGroupOperationType,
    DeleteViewFilterOperationType,
    DeleteViewGroupByOperationType,
    DeleteViewOperationType,
    DeleteViewRowOperationType,
    DeleteViewSortOperationType,
    DuplicateViewOperationType,
    ListAggregationsViewOperationType,
    ListViewDecorationOperationType,
    ListViewFilterOperationType,
    ListViewGroupByOperationType,
    ListViewsOperationType,
    ListViewSortOperationType,
    OrderViewsOperationType,
    ReadAggregationsViewOperationType,
    ReadViewDecorationOperationType,
    ReadViewFieldOptionsOperationType,
    ReadViewFilterGroupOperationType,
    ReadViewFilterOperationType,
    ReadViewGroupByOperationType,
    ReadViewOperationType,
    ReadViewRowOperationType,
    ReadViewsOrderOperationType,
    ReadViewSortOperationType,
    RestoreViewOperationType,
    UpdateViewDecorationOperationType,
    UpdateViewFieldOptionsOperationType,
    UpdateViewFilterGroupOperationType,
    UpdateViewFilterOperationType,
    UpdateViewGroupByOperationType,
    UpdateViewOperationType,
    UpdateViewPublicOperationType,
    UpdateViewRowOperationType,
    UpdateViewSlugOperationType,
    UpdateViewSortOperationType,
)
from baserow.contrib.database.webhooks.operations import (
    CreateWebhookOperationType,
    DeleteWebhookOperationType,
    ListTableWebhooksOperationType,
    ReadWebhookOperationType,
    TestTriggerWebhookOperationType,
    UpdateWebhookOperationType,
)
from baserow.core.integrations.operations import (
    CreateIntegrationOperationType,
    DeleteIntegrationOperationType,
    ListIntegrationsApplicationOperationType,
    OrderIntegrationsOperationType,
    ReadIntegrationOperationType,
    UpdateIntegrationOperationType,
)
from baserow.core.mcp.operations import (
    CreateMCPEndpointOperationType,
    DeleteMCPEndpointOperationType,
    ReadMCPEndpointOperationType,
    UpdateMCPEndpointOperationType,
)
from baserow.core.operations import (
    CreateApplicationsWorkspaceOperationType,
    CreateInvitationsWorkspaceOperationType,
    DeleteApplicationOperationType,
    DeleteWorkspaceInvitationOperationType,
    DeleteWorkspaceOperationType,
    DeleteWorkspaceUserOperationType,
    DuplicateApplicationOperationType,
    ListApplicationsWorkspaceOperationType,
    ListInvitationsWorkspaceOperationType,
    ListWorkspaceUsersWorkspaceOperationType,
    OrderApplicationsOperationType,
    ReadApplicationOperationType,
    ReadInvitationWorkspaceOperationType,
    ReadWorkspaceOperationType,
    RestoreApplicationOperationType,
    RestoreWorkspaceOperationType,
    UpdateApplicationOperationType,
    UpdateWorkspaceInvitationType,
    UpdateWorkspaceOperationType,
    UpdateWorkspaceUserOperationType,
)
from baserow.core.snapshots.operations import (
    CreateSnapshotApplicationOperationType,
    DeleteApplicationSnapshotOperationType,
    ListSnapshotsApplicationOperationType,
    RestoreApplicationSnapshotOperationType,
)
from baserow.core.trash.operations import (
    EmptyApplicationTrashOperationType,
    EmptyWorkspaceTrashOperationType,
    ReadApplicationTrashOperationType,
    ReadWorkspaceTrashOperationType,
)
from baserow.core.user_sources.operations import (
    AuthenticateUserSourceOperationType,
    CreateUserSourceOperationType,
    DeleteUserSourceOperationType,
    ListUserSourcesApplicationOperationType,
    LoginUserSourceOperationType,
    OrderUserSourcesOperationType,
    ReadUserSourceOperationType,
    UpdateUserSourceOperationType,
)
from baserow_enterprise.assistant.operations import ChatAssistantChatOperationType
from baserow_enterprise.audit_log.operations import (
    ListWorkspaceAuditLogEntriesOperationType,
)
from baserow_enterprise.field_permissions.operations import (
    ReadFieldPermissionsOperationType,
    UpdateFieldPermissionsOperationType,
)
from baserow_enterprise.role.constants import (
    ADMIN_ROLE_UID,
    BUILDER_ROLE_UID,
    COMMENTER_ROLE_UID,
    EDITOR_ROLE_UID,
    NO_ACCESS_ROLE_UID,
    NO_ROLE_LOW_PRIORITY_ROLE_UID,
    READ_ONLY_ROLE_UID,
    VIEWER_ROLE_UID,
)
from baserow_enterprise.role.operations import (
    AssignRoleWorkspaceOperationType,
    ReadRoleApplicationOperationType,
    ReadRoleTableOperationType,
    ReadRoleViewOperationType,
    ReadRoleWorkspaceOperationType,
    UpdateRoleApplicationOperationType,
    UpdateRoleTableOperationType,
    UpdateRoleViewOperationType,
)
from baserow_enterprise.teams.operations import (
    CreateTeamOperationType,
    CreateTeamSubjectOperationType,
    DeleteTeamOperationType,
    DeleteTeamSubjectOperationType,
    ListTeamsOperationType,
    ListTeamSubjectsOperationType,
    ReadTeamOperationType,
    ReadTeamSubjectOperationType,
    RestoreTeamOperationType,
    UpdateTeamOperationType,
)
from baserow_enterprise.views.operations import (
    ListenToAllRestrictedViewEventsOperationType,
)

default_roles = {
    ADMIN_ROLE_UID: [],
    BUILDER_ROLE_UID: [],
    EDITOR_ROLE_UID: [],
    COMMENTER_ROLE_UID: [],
    VIEWER_ROLE_UID: [],
    READ_ONLY_ROLE_UID: [],
    NO_ACCESS_ROLE_UID: [],
    NO_ROLE_LOW_PRIORITY_ROLE_UID: [],
}
# Virtual roles are only used in-code, and it's not possible for the user to use these.
# The READ_ONLY role is used give to the user when they don't have access to a lower
# level object scope, but have access a higher one.
hidden_roles = [READ_ONLY_ROLE_UID]

if settings.BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED not in default_roles:
    raise ImproperlyConfigured(
        f"The env var BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED must be set to one of "
        f"the following values: {default_roles.keys()} but instead it is "
        f"{settings.BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED}. "
    )

default_roles[settings.BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED].append(
    CreateAndUsePersonalViewOperationType
)

# Note that the read only role can automatically be assigned to the user if they have a
# role assigned on a higher scope. If the user for example has `NO_ACCESS` to a
# database, but has been given `EDITOR` role to the table, then they will automatically
# get the viewer role of the database. The individual endpoints or filter queryset
# rules must prevent accidental data exposure.
default_roles[READ_ONLY_ROLE_UID].extend(
    default_roles[NO_ACCESS_ROLE_UID]
    + [
        ReadWorkspaceOperationType,
        ReadTeamOperationType,
        ListTeamsOperationType,
        ListApplicationsWorkspaceOperationType,
        ListTablesDatabaseTableOperationType,
        ReadApplicationOperationType,
        ReadDatabaseTableOperationType,
        ListRowsDatabaseTableOperationType,
        ReadViewOperationType,
        ReadFieldOperationType,
        ListViewSortOperationType,
        ReadViewFieldOptionsOperationType,
        ReadViewDecorationOperationType,
        ListViewDecorationOperationType,
        ListViewFilterOperationType,
        ListViewsOperationType,
        ListFieldsOperationType,
        ListAggregationsViewOperationType,
        ReadAggregationsViewOperationType,
        ReadAdjacentRowDatabaseRowOperationType,
        ListRowNamesDatabaseTableOperationType,
        ReadViewFilterOperationType,
        ReadViewsOrderOperationType,
        ReadViewSortOperationType,
        ListViewGroupByOperationType,
        ReadViewGroupByOperationType,
        ListBuilderWorkflowActionsPageOperationType,
        ReadBuilderWorkflowActionOperationType,
        ReadViewFilterGroupOperationType,
        ReadWidgetOperationType,
        ListWidgetsOperationType,
        ListDashboardDataSourcesOperationType,
        ReadDashboardDataSourceOperationType,
    ]
)
default_roles[VIEWER_ROLE_UID].extend(
    default_roles[READ_ONLY_ROLE_UID]
    + [
        ListenToAllRestrictedViewEventsOperationType,
        ListenToAllDatabaseTableEventsOperationType,
        ReadMCPEndpointOperationType,
        CreateMCPEndpointOperationType,
        UpdateMCPEndpointOperationType,
        DeleteMCPEndpointOperationType,
        ChatAssistantChatOperationType,
        ReadFieldRuleOperationType,
        ExportTableOperationType,
        DispatchDashboardDataSourceOperationType,
        ReadDatabaseRowOperationType,
        ReadViewRowOperationType,
    ]
)
default_roles[COMMENTER_ROLE_UID].extend(
    default_roles[VIEWER_ROLE_UID]
    + [
        CreateRowCommentsOperationType,
        DeleteRowCommentsOperationType,
        ReadRowCommentsOperationType,
        RestoreRowCommentOperationType,
        UpdateRowCommentsOperationType,
        ReadDatabaseRowHistoryOperationType,
    ]
)
default_roles[EDITOR_ROLE_UID].extend(
    default_roles[COMMENTER_ROLE_UID]
    + [
        CreateRowDatabaseTableOperationType,
        UpdateDatabaseRowOperationType,
        DeleteDatabaseRowOperationType,
        MoveRowDatabaseRowOperationType,
        ImportRowsDatabaseTableOperationType,
        ListWorkspaceUsersWorkspaceOperationType,
        RestoreDatabaseRowOperationType,
        ListTeamSubjectsOperationType,
        ReadTeamSubjectOperationType,
        CanReceiveNotificationOnSubmitFormViewOperationType,
        CreateViewRowOperationType,
        UpdateViewRowOperationType,
        DeleteViewRowOperationType,
    ]
)
default_roles[BUILDER_ROLE_UID].extend(
    default_roles[EDITOR_ROLE_UID]
    + [
        CreatePageOperationType,
        DeletePageOperationType,
        UpdatePageOperationType,
        UpdateThemeOperationType,
        DuplicatePageOperationType,
        CreateTableDatabaseTableOperationType,
        UpdateDatabaseTableOperationType,
        DeleteDatabaseTableOperationType,
        RestoreDatabaseTableOperationType,
        DeleteDatabaseRowOperationType,
        CreateViewOperationType,
        CreateFieldOperationType,
        UpdateViewDecorationOperationType,
        TestTriggerWebhookOperationType,
        ListTableWebhooksOperationType,
        DuplicateFieldOperationType,
        CreateViewDecorationOperationType,
        DeleteFieldOperationType,
        DeleteRelatedLinkRowFieldOperationType,
        RestoreFieldOperationType,
        UpdateFieldOperationType,
        TypeFormulaOperationType,
        RunAirtableImportJobOperationType,
        UpdateViewOperationType,
        DeleteViewOperationType,
        RestoreViewOperationType,
        DuplicateViewOperationType,
        UpdateWebhookOperationType,
        CreateViewFilterOperationType,
        CreateViewFilterGroupOperationType,
        UpdateViewFilterGroupOperationType,
        DeleteViewFilterGroupOperationType,
        UpdateViewFilterOperationType,
        DeleteViewFilterOperationType,
        DeleteViewDecorationOperationType,
        CreateWebhookOperationType,
        DeleteWebhookOperationType,
        ReadWebhookOperationType,
        OrderViewsOperationType,
        UpdateViewFieldOptionsOperationType,
        CreateApplicationsWorkspaceOperationType,
        DeleteViewSortOperationType,
        UpdateViewSlugOperationType,
        CreatePublicViewOperationType,
        UpdateViewPublicOperationType,
        DeleteApplicationOperationType,
        RestoreApplicationOperationType,
        ReadApplicationTrashOperationType,
        DuplicateApplicationOperationType,
        UpdateApplicationOperationType,
        UpdateViewSortOperationType,
        DuplicateDatabaseTableOperationType,
        CreateViewSortOperationType,
        CreateViewGroupByOperationType,
        UpdateViewGroupByOperationType,
        DeleteViewGroupByOperationType,
        ReadWorkspaceTrashOperationType,
        CreateTokenOperationType,
        ReadTokenOperationType,
        UpdateTokenOperationType,
        UseTokenOperationType,
        OrderTablesDatabaseTableOperationType,
        OrderApplicationsOperationType,
        CreateElementOperationType,
        UpdateElementOperationType,
        DeleteElementOperationType,
        ReadElementOperationType,
        ListElementsPageOperationType,
        OrderElementsPageOperationType,
        CreateDomainOperationType,
        DeleteDomainOperationType,
        ReadDomainOperationType,
        UpdateDomainOperationType,
        PublishDomainOperationType,
        CreateIntegrationOperationType,
        DeleteIntegrationOperationType,
        ListIntegrationsApplicationOperationType,
        OrderIntegrationsOperationType,
        ReadIntegrationOperationType,
        UpdateIntegrationOperationType,
        CreateDataSourceOperationType,
        DeleteDataSourceOperationType,
        ListDataSourcesPageOperationType,
        OrderDataSourcesPageOperationType,
        ReadDataSourceOperationType,
        UpdateDataSourceOperationType,
        DispatchDataSourceOperationType,
        DispatchBuilderWorkflowActionOperationType,
        DeleteBuilderWorkflowActionOperationType,
        CreateBuilderWorkflowActionOperationType,
        CreateUserSourceOperationType,
        DeleteUserSourceOperationType,
        ListUserSourcesApplicationOperationType,
        ReadUserSourceOperationType,
        UpdateUserSourceOperationType,
        OrderUserSourcesOperationType,
        AuthenticateUserSourceOperationType,
        LoginUserSourceOperationType,
        ReadPageOperationType,
        ListPagesBuilderOperationType,
        OrderPagesBuilderOperationType,
        ListDomainsBuilderOperationType,
        OrderDomainsBuilderOperationType,
        UpdateBuilderWorkflowActionOperationType,
        OrderBuilderWorkflowActionOperationType,
        SyncTableOperationType,
        ListPropertiesOperationType,
        GetIncludingPublicValuesOperationType,
        CreateWidgetOperationType,
        UpdateWidgetOperationType,
        DeleteWidgetOperationType,
        RestoreWidgetOperationType,
        CreateDashboardDataSourceOperationType,
        DeleteDashboardDataSourceOperationType,
        UpdateDashboardDataSourceOperationType,
        ListAutomationWorkflowsOperationType,
        OrderAutomationWorkflowsOperationType,
        CreateAutomationWorkflowOperationType,
        RestoreAutomationWorkflowOperationType,
        DeleteAutomationWorkflowOperationType,
        UpdateAutomationWorkflowOperationType,
        ReadAutomationWorkflowOperationType,
        PublishAutomationWorkflowOperationType,
        DuplicateAutomationWorkflowOperationType,
        UpdateFieldPermissionsOperationType,
        ReadFieldPermissionsOperationType,
        ListAutomationNodeOperationType,
        CreateAutomationNodeOperationType,
        UpdateAutomationNodeOperationType,
        ReadAutomationNodeOperationType,
        DeleteAutomationNodeOperationType,
        OrderAutomationNodeOperationType,
        RestoreAutomationNodeOperationType,
        DuplicateAutomationNodeOperationType,
        SetFieldRuleOperationType,
    ]
)
default_roles[ADMIN_ROLE_UID].extend(
    default_roles[BUILDER_ROLE_UID]
    + [
        UpdateWorkspaceOperationType,
        DeleteWorkspaceOperationType,
        DeleteDatabaseRowOperationType,
        ReadInvitationWorkspaceOperationType,
        AssignRoleWorkspaceOperationType,
        ReadRoleWorkspaceOperationType,
        DeleteWorkspaceUserOperationType,
        DeleteWorkspaceInvitationOperationType,
        UpdateWorkspaceUserOperationType,
        CreateInvitationsWorkspaceOperationType,
        ListInvitationsWorkspaceOperationType,
        UpdateWorkspaceInvitationType,
        CreateTeamOperationType,
        UpdateTeamOperationType,
        DeleteTeamOperationType,
        CreateTeamSubjectOperationType,
        DeleteTeamSubjectOperationType,
        RestoreTeamOperationType,
        RestoreWorkspaceOperationType,
        EmptyApplicationTrashOperationType,
        EmptyWorkspaceTrashOperationType,
        ReadRoleTableOperationType,
        UpdateRoleTableOperationType,
        ReadRoleApplicationOperationType,
        UpdateRoleApplicationOperationType,
        CreateSnapshotApplicationOperationType,
        RestoreApplicationSnapshotOperationType,
        ListSnapshotsApplicationOperationType,
        DeleteApplicationSnapshotOperationType,
        RestoreDomainOperationType,
        ListWorkspaceAuditLogEntriesOperationType,
        ReadRoleViewOperationType,
        UpdateRoleViewOperationType,
    ]
)
