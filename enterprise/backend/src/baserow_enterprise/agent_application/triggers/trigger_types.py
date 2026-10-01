import datetime
from typing import Optional

from django.utils import timezone

from ..models import AgentTrigger
from .registries import AgentTriggerType


def _sample_row(trigger: AgentTrigger) -> dict:
    """A row with the trigger table's field names, so tokens can be tried."""

    row = {"id": 1}
    service = trigger.service.specific
    table = getattr(service, "table", None)
    if table is not None:
        for field in table.field_set.order_by("order", "id")[:8]:
            row[field.name] = f"Sample {field.name.lower()}"
    return row


def _trigger_table_id(trigger: AgentTrigger) -> Optional[int]:
    return getattr(trigger.service.specific, "table_id", None)


class LocalBaserowTableAgentTriggerType(AgentTriggerType):
    headline_template = "Trigger: an event occurred in table {table}."

    def get_opening_headline(self, trigger: AgentTrigger) -> str:
        table = getattr(trigger.service.specific, "table", None)
        table_name = f'"{table.name}" (id {table.id})' if table else "(unknown)"
        return self.headline_template.format(table=table_name)

    def get_tokens(self, trigger: AgentTrigger) -> list[dict]:
        return [
            {"token": "{{trigger.rows}}", "description": "All affected rows"},
            {"token": "{{trigger.row.id}}", "description": "The first affected row"},
            {
                "token": "{{trigger.row.Field name}}",
                "description": "Any field of that row",
            },
        ]

    def get_token_aliases(self, trigger_payload) -> dict[str, list]:
        return {"rows": ["results"], "row": ["results", 0]}

    def get_sample_payload(self, trigger: AgentTrigger) -> Optional[dict]:
        return {"results": [_sample_row(trigger)]}


class RowsCreatedAgentTriggerType(LocalBaserowTableAgentTriggerType):
    type = "rows_created"
    service_type = "local_baserow_rows_created"
    headline_template = "Trigger: rows were created in table {table}."

    def get_tokens(self, trigger: AgentTrigger) -> list[dict]:
        tokens = super().get_tokens(trigger)
        tokens[1]["description"] = "The new row"
        tokens[2]["description"] = "Any field of the new row"
        return tokens


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

    def get_tokens(self, trigger: AgentTrigger) -> list[dict]:
        return [
            {"token": "{{trigger.comment.message}}", "description": "The comment text"},
            {"token": "{{trigger.comment.author}}", "description": "Who wrote it"},
            {"token": "{{trigger.row.id}}", "description": "The row it was posted on"},
            {"token": "{{trigger.table.id}}", "description": "The table of that row"},
        ]

    def get_token_aliases(self, trigger_payload) -> dict[str, list]:
        return {
            "comment.message": ["message"],
            "comment.author": ["user", "name"],
            "comment": ["message"],
            "row.id": ["row_id"],
            "table.id": ["table_id"],
        }

    def get_sample_payload(self, trigger: AgentTrigger) -> Optional[dict]:
        return {
            "id": 1,
            "table_id": _trigger_table_id(trigger),
            "row_id": 1,
            "message": "Can you look into this one?",
            "user": {"id": 1, "name": "Sample user"},
            "mentions": [],
            "created_on": timezone.now().isoformat(),
        }


class PeriodicAgentTriggerType(AgentTriggerType):
    type = "periodic"
    service_type = "periodic"

    def get_opening_headline(self, trigger: AgentTrigger) -> str:
        return "Trigger: scheduled periodic run."

    def get_tokens(self, trigger: AgentTrigger) -> list[dict]:
        return [
            {"token": "{{trigger.time}}", "description": "When the run started"},
            {"token": "{{trigger.next_run}}", "description": "When the next run is"},
        ]

    def get_token_aliases(self, trigger_payload) -> dict[str, list]:
        return {"time": ["triggered_at"], "next_run": ["next_run_at"]}

    def get_sample_payload(self, trigger: AgentTrigger) -> Optional[dict]:
        service = trigger.service.specific
        try:
            return service.get_type()._get_simulation_payload(service)
        except Exception:
            now = timezone.now().replace(second=0, microsecond=0)
            return {
                "triggered_at": now.isoformat(),
                "next_run_at": (now + datetime.timedelta(days=1)).isoformat(),
            }


class HttpAgentTriggerType(AgentTriggerType):
    type = "http_trigger"
    service_type = "http_trigger"

    def get_opening_headline(self, trigger: AgentTrigger) -> str:
        return "Trigger: a webhook request was received."

    def get_tokens(self, trigger: AgentTrigger) -> list[dict]:
        return [
            {"token": "{{trigger.body}}", "description": "The request body"},
            {"token": "{{trigger.body.key}}", "description": "A value in the body"},
            {"token": "{{trigger.query.name}}", "description": "Any query parameter"},
            {"token": "{{trigger.headers}}", "description": "The request headers"},
        ]

    def get_token_aliases(self, trigger_payload) -> dict[str, list]:
        return {"query": ["query_params"]}

    def get_sample_payload(self, trigger: AgentTrigger) -> Optional[dict]:
        return {
            "method": "POST",
            "headers": {"content-type": "application/json"},
            "query_params": {"source": "example"},
            "body": {"message": "Hello from the webhook"},
        }


class InboundEmailAgentTriggerType(AgentTriggerType):
    type = "email_trigger"
    service_type = "email_trigger"

    def get_opening_headline(self, trigger: AgentTrigger) -> str:
        return "Trigger: an email was received at the agent's inbound address."

    def get_tokens(self, trigger: AgentTrigger) -> list[dict]:
        return [
            {"token": "{{trigger.email.subject}}", "description": "The subject"},
            {"token": "{{trigger.email.from}}", "description": "Who sent it"},
            {"token": "{{trigger.email.body}}", "description": "The message text"},
        ]

    def get_token_aliases(self, trigger_payload) -> dict[str, list]:
        return {
            "email.subject": ["subject"],
            "email.from": ["from", "address"],
            "email.body": ["body_text"],
        }

    def get_sample_payload(self, trigger: AgentTrigger) -> Optional[dict]:
        service = trigger.service.specific
        try:
            return service.get_type()._get_sample_payload(service)
        except Exception:
            return None
