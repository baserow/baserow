from uuid import uuid4

from baserow.contrib.integrations.ai.models import AIAgentService
from baserow.contrib.integrations.core.models import (
    CoreHTTPRequestService,
    CoreHTTPTriggerService,
    CoreIteratorService,
    CoreRouterService,
    CoreSMTPEmailService,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowAggregateRows,
    LocalBaserowDeleteRow,
    LocalBaserowGetRow,
    LocalBaserowListRows,
    LocalBaserowRowsCreated,
    LocalBaserowRowsDeleted,
    LocalBaserowRowsUpdated,
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceSort,
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

    def create_local_baserow_table_service_filter(
        self, **kwargs
    ) -> LocalBaserowTableServiceFilter:
        if "type" not in kwargs:
            kwargs["type"] = "equal"
        if "order" not in kwargs:
            kwargs["order"] = 0
        return LocalBaserowTableServiceFilter.objects.create(**kwargs)

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
        return self.create_service(SlackWriteMessageService, **kwargs)

    def create_core_iterator_service(self, **kwargs):
        return self.create_service(CoreIteratorService, **kwargs)

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

    def create_core_http_trigger_service(self, **kwargs) -> CoreSMTPEmailService:
        if "uid" not in kwargs:
            kwargs["uid"] = uuid4()

        return self.create_service(CoreHTTPTriggerService, **kwargs)

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
