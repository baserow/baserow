from uuid import uuid4

from baserow.contrib.integrations.ai.models import AIAgentService
from baserow.contrib.integrations.core.models import (
    CoreCSVFileReaderService,
    CoreGotoService,
    CoreHTTPRequestService,
    CoreHTTPTriggerService,
    CoreInboundEmailTriggerService,
    CoreIteratorService,
    CoreManualTriggerService,
    CorePeriodicService,
    CoreResponseService,
    CoreRouterService,
    CoreSMTPEmailService,
    CoreStartWorkflowService,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowAggregateRows,
    LocalBaserowCreateRows,
    LocalBaserowDeleteRow,
    LocalBaserowFieldsUpdated,
    LocalBaserowGetRow,
    LocalBaserowListRows,
    LocalBaserowRowsCreated,
    LocalBaserowRowsDeleted,
    LocalBaserowRowsUpdated,
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceFilterGroup,
    LocalBaserowTableServiceSort,
    LocalBaserowUpdateRows,
    LocalBaserowUpsertRow,
)
from baserow.contrib.integrations.slack.models import SlackWriteMessageService
from baserow.core.services.registries import service_type_registry


class ServiceFixtures:
    def create_local_baserow_get_row_service(self, **kwargs) -> LocalBaserowGetRow:
        service = self.create_service(LocalBaserowGetRow, **kwargs)
        return service

    def create_local_baserow_list_rows_service(self, **kwargs) -> LocalBaserowListRows:
        service = self.create_service(LocalBaserowListRows, **kwargs)
        return service

    def create_local_baserow_upsert_row_service(
        self, **kwargs
    ) -> LocalBaserowUpsertRow:
        service = self.create_service(LocalBaserowUpsertRow, **kwargs)
        return service

    def create_local_baserow_create_rows_service(
        self, **kwargs
    ) -> LocalBaserowCreateRows:
        service = self.create_service(LocalBaserowCreateRows, **kwargs)
        return service

    def create_local_baserow_update_rows_service(
        self, **kwargs
    ) -> LocalBaserowUpdateRows:
        service = self.create_service(LocalBaserowUpdateRows, **kwargs)
        return service

    def create_local_baserow_delete_row_service(
        self, **kwargs
    ) -> LocalBaserowDeleteRow:
        service = self.create_service(LocalBaserowDeleteRow, **kwargs)
        return service

    def create_local_baserow_aggregate_rows_service(
        self, **kwargs
    ) -> LocalBaserowAggregateRows:
        service = self.create_service(LocalBaserowAggregateRows, **kwargs)
        return service

    def create_local_baserow_rows_created_service(
        self, **kwargs
    ) -> LocalBaserowRowsCreated:
        service = self.create_service(LocalBaserowRowsCreated, **kwargs)
        return service

    def create_local_baserow_rows_updated_service(
        self, **kwargs
    ) -> LocalBaserowRowsUpdated:
        service = self.create_service(LocalBaserowRowsUpdated, **kwargs)
        return service

    def create_local_baserow_rows_deleted_service(
        self, **kwargs
    ) -> LocalBaserowRowsDeleted:
        service = self.create_service(LocalBaserowRowsDeleted, **kwargs)
        return service

    def create_local_baserow_fields_updated_service(
        self, fields=None, **kwargs
    ) -> LocalBaserowFieldsUpdated:
        service = self.create_service(LocalBaserowFieldsUpdated, **kwargs)
        if fields:
            service.fields.set(fields)
        return service

    def create_local_baserow_table_service_filter(
        self, **kwargs
    ) -> LocalBaserowTableServiceFilter:
        if "type" not in kwargs:
            kwargs["type"] = "equal"
        if "order" not in kwargs:
            kwargs["order"] = 0
        if kwargs.get("value_is_formula") is False and "value" in kwargs:
            value = kwargs["value"]
            if isinstance(value, dict):
                value["mode"] = "raw"
            else:
                kwargs["value"] = {
                    "formula": "" if value is None else str(value),
                    "mode": "raw",
                    "version": "0.1",
                }
        return LocalBaserowTableServiceFilter.objects.create(**kwargs)

    def create_local_baserow_table_service_filter_group(
        self, **kwargs
    ) -> LocalBaserowTableServiceFilterGroup:
        return LocalBaserowTableServiceFilterGroup.objects.create(**kwargs)

    def create_local_baserow_table_service_sort(
        self, **kwargs
    ) -> LocalBaserowTableServiceSort:
        return LocalBaserowTableServiceSort.objects.create(**kwargs)

    def create_core_http_request_service(self, **kwargs) -> CoreHTTPRequestService:
        service = self.create_service(CoreHTTPRequestService, **kwargs)
        return service

    def create_core_smtp_email_service(self, **kwargs) -> CoreSMTPEmailService:
        if "from_email" not in kwargs:
            kwargs["from_email"] = "'sender@example.com'"
        if "to_emails" not in kwargs:
            kwargs["to_emails"] = "'recipient@example.com'"
        if "subject" not in kwargs:
            kwargs["subject"] = "'Test Subject'"
        if "body" not in kwargs:
            kwargs["body"] = "'Test email body'"
        if "body_type" not in kwargs:
            kwargs["body_type"] = "plain"

        service = self.create_service(CoreSMTPEmailService, **kwargs)
        return service

    def create_ai_agent_service(self, **kwargs):
        return self.create_service(AIAgentService, **kwargs)

    def create_slack_write_message_service(self, **kwargs):
        # A bot with no token is refused before the dispatch sends anything.
        if "integration" not in kwargs:
            kwargs.setdefault("integration_args", {}).setdefault("token", "xoxb-test")
        return self.create_service(SlackWriteMessageService, **kwargs)

    def create_gmail_send_email_service(self, **kwargs):
        from baserow.contrib.integrations.google.models import GmailSendEmailService

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(GmailSendEmailService, **kwargs)

    def create_google_calendar_create_event_service(self, **kwargs):
        from baserow.contrib.integrations.google.models import (
            GoogleCalendarCreateEventService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(GoogleCalendarCreateEventService, **kwargs)

    def create_google_calendar_update_event_service(self, **kwargs):
        from baserow.contrib.integrations.google.models import (
            GoogleCalendarUpdateEventService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(GoogleCalendarUpdateEventService, **kwargs)

    def create_google_calendar_delete_event_service(self, **kwargs):
        from baserow.contrib.integrations.google.models import (
            GoogleCalendarDeleteEventService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(GoogleCalendarDeleteEventService, **kwargs)

    def create_google_calendar_list_events_service(self, **kwargs):
        from baserow.contrib.integrations.google.models import (
            GoogleCalendarListEventsService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(GoogleCalendarListEventsService, **kwargs)

    def create_microsoft_teams_send_message_service(self, **kwargs):
        from baserow.contrib.integrations.microsoft.models import (
            MicrosoftTeamsSendMessageService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(MicrosoftTeamsSendMessageService, **kwargs)

    def create_outlook_send_email_service(self, **kwargs):
        from baserow.contrib.integrations.microsoft.models import (
            OutlookSendEmailService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(OutlookSendEmailService, **kwargs)

    def create_outlook_calendar_create_event_service(self, **kwargs):
        from baserow.contrib.integrations.microsoft.models import (
            OutlookCalendarCreateEventService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(OutlookCalendarCreateEventService, **kwargs)

    def create_outlook_calendar_update_event_service(self, **kwargs):
        from baserow.contrib.integrations.microsoft.models import (
            OutlookCalendarUpdateEventService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(OutlookCalendarUpdateEventService, **kwargs)

    def create_outlook_calendar_delete_event_service(self, **kwargs):
        from baserow.contrib.integrations.microsoft.models import (
            OutlookCalendarDeleteEventService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(OutlookCalendarDeleteEventService, **kwargs)

    def create_outlook_calendar_list_events_service(self, **kwargs):
        from baserow.contrib.integrations.microsoft.models import (
            OutlookCalendarListEventsService,
        )

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(OutlookCalendarListEventsService, **kwargs)

    def create_jira_list_issues_service(self, **kwargs):
        from baserow.contrib.integrations.jira.models import JiraListIssuesService

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "url": "https://example.atlassian.net",
                "username": "u@example.com",
                "api_token": "t",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(JiraListIssuesService, **kwargs)

    def create_jira_create_issue_service(self, **kwargs):
        from baserow.contrib.integrations.jira.models import JiraCreateIssueService

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "url": "https://example.atlassian.net",
                "username": "u@example.com",
                "api_token": "t",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(JiraCreateIssueService, **kwargs)

    def create_jira_update_issue_service(self, **kwargs):
        from baserow.contrib.integrations.jira.models import JiraUpdateIssueService

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "url": "https://example.atlassian.net",
                "username": "u@example.com",
                "api_token": "t",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(JiraUpdateIssueService, **kwargs)

    def create_jira_delete_issue_service(self, **kwargs):
        from baserow.contrib.integrations.jira.models import JiraDeleteIssueService

        if "integration" not in kwargs:
            integration_args = kwargs.setdefault("integration_args", {})
            for key, value in {
                "url": "https://example.atlassian.net",
                "username": "u@example.com",
                "api_token": "t",
            }.items():
                integration_args.setdefault(key, value)
        return self.create_service(JiraDeleteIssueService, **kwargs)

    def create_core_iterator_service(self, **kwargs):
        return self.create_service(CoreIteratorService, **kwargs)

    def create_core_csv_file_reader_service(self, **kwargs):
        return self.create_service(CoreCSVFileReaderService, **kwargs)

    def create_core_start_workflow_service(self, **kwargs):
        return self.create_service(CoreStartWorkflowService, **kwargs)

    def create_core_response_service(self, **kwargs):
        return self.create_service(CoreResponseService, **kwargs)

    def create_core_router_service(self, **kwargs):
        return self.create_service(CoreRouterService, **kwargs)

    def create_core_router_service_edge(self, service: CoreRouterService, **kwargs):
        output_node = kwargs.pop("output_node", None)
        skip_output_node = kwargs.pop("skip_output_node", False)
        edge_label = kwargs.get("label", "Edge")
        output_label = kwargs.pop("output_label", f"{edge_label} output node")

        edge = service.edges.create(**kwargs)

        if output_node is None and not skip_output_node:
            router_node = service.automation_workflow_node
            self.create_local_baserow_create_row_action_node(
                reference_node=router_node,
                output=edge.uid,
                position="south",
                workflow=router_node.workflow,
                label=output_label,
            )

        return edge

    def create_core_goto_service(self, **kwargs) -> CoreGotoService:
        return self.create_service(CoreGotoService, **kwargs)

    def create_core_http_trigger_service(self, **kwargs) -> CoreSMTPEmailService:
        if "uid" not in kwargs:
            kwargs["uid"] = uuid4()

        return self.create_service(CoreHTTPTriggerService, **kwargs)

    def create_core_inbound_email_trigger_service(
        self, **kwargs
    ) -> CoreInboundEmailTriggerService:
        return self.create_service(CoreInboundEmailTriggerService, **kwargs)

    def create_core_manual_trigger_service(self, **kwargs):
        return self.create_service(CoreManualTriggerService, **kwargs)

    def create_core_periodic_service(self, **kwargs) -> CorePeriodicService:
        return self.create_service(CorePeriodicService, **kwargs)

    def create_service(self, model_class, **kwargs):
        if "integration" not in kwargs:
            integration = None
            integrations_args = kwargs.pop("integration_args", {})
            service_type = service_type_registry.get_by_model(model_class)
            if service_type.get_integration_type():
                integration = self.create_integration(
                    service_type.get_integration_type().model_class, **integrations_args
                )
        else:
            integration = kwargs.pop("integration", None)
            kwargs.pop("integration_args", None)

        service = model_class.objects.create(integration=integration, **kwargs)

        return service
