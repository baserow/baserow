from django.db import transaction
from django.db.models.signals import pre_delete

from baserow.api.sessions import get_untrusted_client_session_id
from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    DatabaseWorkflowServiceAction,
)
from baserow.contrib.database.workflow_actions.signals import (
    button_field_dispatched,
    workflow_action_dispatched,
)
from baserow.contrib.database.workflow_actions.telemetry import (
    record_button_field_dispatched,
    record_workflow_action_dispatched,
)
from baserow.core.models import TrashEntry
from baserow.core.posthog import capture_user_event
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


def before_permanently_deleted(sender, instance, **kwargs):
    """
    Delete the service related to the action, and its trash entry. A deleted
    action cannot be restored, and a field changing away from a button deletes
    its trashed actions too, which would otherwise stay listed in the trash.
    """

    from baserow.contrib.database.workflow_actions.trash_types import (
        DatabaseWorkflowActionTrashableItemType,
    )

    if instance.trashed:
        TrashEntry.objects.filter(
            trash_item_type=DatabaseWorkflowActionTrashableItemType.type,
            trash_item_id=instance.id,
        ).delete()

    if isinstance(instance.specific, DatabaseWorkflowServiceAction):
        service = instance.specific.service

        def delete_service_after_commit():
            try:
                ServiceHandler().delete_service(service.get_type(), service)
            except Service.DoesNotExist:
                # Cascade deletion may already have removed it.
                pass

        transaction.on_commit(delete_service_after_commit)


def connect_to_database_workflow_action_pre_delete_signal():
    pre_delete.connect(before_permanently_deleted, DatabaseWorkflowAction)


def capture_button_field_dispatched(
    sender,
    user,
    field,
    row_id,
    workflow_actions,
    outcome,
    failed_position,
    error_status_count,
    duration_ms,
    **kwargs,
):
    """
    One PostHog event per click. Nothing here may name a row, an address or
    what an action returned.
    """

    types = [workflow_action.get_type() for workflow_action in workflow_actions]
    table = field.table
    capture_user_event(
        user,
        "button_field_dispatched",
        {
            "database_id": table.database_id,
            "table_id": table.id,
            "field_id": field.id,
            "outcome": str(outcome),
            "failed_position": failed_position,
            # `completed` says Baserow ran the sequence, not that every
            # endpoint an action reached accepted what it sent.
            "error_status_count": error_status_count,
            "duration_ms": round(duration_ms),
            "action_types": [type_.type for type_ in types],
            "server_action_count": sum(not t.is_frontend_only for t in types),
            "client_action_count": sum(t.is_frontend_only for t in types),
            "external_action_count": sum(t.is_external for t in types),
        },
        session=get_untrusted_client_session_id(user),
        workspace=table.database.workspace,
    )


def connect_to_database_workflow_action_signals():
    button_field_dispatched.connect(capture_button_field_dispatched)
    button_field_dispatched.connect(record_button_field_dispatched)
    workflow_action_dispatched.connect(record_workflow_action_dispatched)
