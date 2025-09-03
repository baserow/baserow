from baserow.core.db import get_collation_name
from baserow.test_utils.fixtures.two_factor_auth import TwoFactorAuthFixtures

from .airtable import AirtableFixtures
from .app_auth_provider import AppAuthProviderFixtures
from .application import ApplicationFixtures
from .auth_provider import AuthProviderFixtures
from .automation_history import AutomationHistoryFixtures
from .automation_node import AutomationNodeFixtures
from .automation_workflow import AutomationWorkflowFixtures
from .automation_workflow_history import AutomationWorkflowHistoryFixtures
from .dashboard_data_source import DashboardDataSourceFixtures
from .data_source import DataSourceFixtures
from .data_sync import DataSyncFixtures
from .domain import DomainFixtures
from .element import ElementFixtures
from .field import FieldFixtures
from .file_import import FileImportFixtures
from .generative_ai import GenerativeAIFixtures
from .import_export import ImportExportWorkspaceFixtures
from .integration import IntegrationFixtures
from .job import JobFixtures
from .mcp import MCPFixtures
from .notifications import NotificationsFixture
from .page import PageFixtures
from .row import RowFixture
from .service import ServiceFixtures
from .settings import SettingsFixtures
from .snapshots import SnapshotFixtures
from .table import TableFixtures
from .template import TemplateFixtures
from .token import TokenFixtures
from .user import UserFixtures
from .user_file import UserFileFixtures
from .user_source import UserSourceFixtures
from .user_source_user import UserSourceUserFixtures
from .view import ViewFixtures
from .webhook import TableWebhookFixture
from .widget import WidgetFixtures
from .workflow_action import WorkflowActionFixture
from .workspace import WorkspaceFixtures


class Fixtures(
    SettingsFixtures,
    UserFixtures,
    UserFileFixtures,
    WorkspaceFixtures,
    ApplicationFixtures,
    AutomationWorkflowFixtures,
    AutomationWorkflowHistoryFixtures,
    AutomationNodeFixtures,
    AutomationHistoryFixtures,
    TableFixtures,
    ViewFixtures,
    FieldFixtures,
    TokenFixtures,
    TwoFactorAuthFixtures,
    TemplateFixtures,
    RowFixture,
    TableWebhookFixture,
    AirtableFixtures,
    JobFixtures,
    FileImportFixtures,
    SnapshotFixtures,
    AuthProviderFixtures,
    PageFixtures,
    ElementFixtures,
    DomainFixtures,
    IntegrationFixtures,
    ServiceFixtures,
    DataSourceFixtures,
    NotificationsFixture,
    WorkflowActionFixture,
    UserSourceFixtures,
    AppAuthProviderFixtures,
    UserSourceUserFixtures,
    GenerativeAIFixtures,
    DataSyncFixtures,
    ImportExportWorkspaceFixtures,
    DashboardDataSourceFixtures,
    WidgetFixtures,
    MCPFixtures,
):
    def __init__(self, fake=None):
        self.fake = fake

    def warm_cache_before_counting_queries(self):
        """
        This method is called before counting the queries so that the cache is already
        filled with queries that need to run the first time and then cached.
        In this way we avoid cases where the second time the queries are less than the
        first time because the cache is already filled.
        """

        self.update_settings()
        get_collation_name()
