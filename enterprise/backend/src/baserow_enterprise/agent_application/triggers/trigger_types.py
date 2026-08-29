from ..models import AgentTrigger
from .registries import AgentTriggerType


class LocalBaserowTableAgentTriggerType(AgentTriggerType):
    """
    Base for triggers backed by a table-scoped Local Baserow signal service.
    """

    headline_template = "Trigger: an event occurred in table {table}."

    def get_opening_headline(self, trigger: AgentTrigger) -> str:
        table = getattr(trigger.service.specific, "table", None)
        table_name = f'"{table.name}" (id {table.id})' if table else "(unknown)"
        return self.headline_template.format(table=table_name)


class RowsCreatedAgentTriggerType(LocalBaserowTableAgentTriggerType):
    type = "rows_created"
    service_type = "local_baserow_rows_created"
    headline_template = "Trigger: rows were created in table {table}."


class RowsUpdatedAgentTriggerType(LocalBaserowTableAgentTriggerType):
    type = "rows_updated"
    service_type = "local_baserow_rows_updated"
    headline_template = "Trigger: rows were updated in table {table}."


class RowsDeletedAgentTriggerType(LocalBaserowTableAgentTriggerType):
    type = "rows_deleted"
    service_type = "local_baserow_rows_deleted"
    headline_template = "Trigger: rows were deleted in table {table}."


class FieldsUpdatedAgentTriggerType(LocalBaserowTableAgentTriggerType):
    type = "fields_updated"
    service_type = "local_baserow_fields_updated"
    headline_template = "Trigger: watched field values were updated in table {table}."


class RowCommentCreatedAgentTriggerType(LocalBaserowTableAgentTriggerType):
    type = "row_comment_created"
    service_type = "local_baserow_row_comment_created"
    headline_template = "Trigger: a comment was placed on a row in table {table}."


class PeriodicAgentTriggerType(AgentTriggerType):
    type = "periodic"
    service_type = "periodic"

    def get_opening_headline(self, trigger: AgentTrigger) -> str:
        return "Trigger: scheduled periodic run."


class HttpAgentTriggerType(AgentTriggerType):
    type = "http_trigger"
    service_type = "http_trigger"

    def get_opening_headline(self, trigger: AgentTrigger) -> str:
        return "Trigger: a webhook request was received."
