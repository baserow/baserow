from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.workflow_actions import signals as workflow_action_signals
from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.ws.registries import page_registry


def _broadcast_field(field, user):
    """
    Sends the button field out again, so everyone else's copy of
    `has_workflow_actions` matches what the field now has. A cell renders an
    inert button or a working one from that alone, and nothing else about an
    action is of any use outside the editor.

    :param field: The button field whose actions changed.
    :param user: The user who changed them, whose own session already knows.
    """

    table_page_type = page_registry.get("table")
    transaction.on_commit(
        # Built here rather than above: `has_workflow_actions` counts the
        # actions, and the change is only committed by the time this runs.
        lambda: table_page_type.broadcast(
            RealtimeFieldMessages.field_updated(field, []),
            getattr(user, "web_socket_id", None),
            table_id=field.table_id,
        )
    )


@receiver(workflow_action_signals.workflow_action_created)
def workflow_action_created(sender, workflow_action, user, **kwargs):
    _broadcast_field(workflow_action.field, user)


@receiver(workflow_action_signals.workflow_action_updated)
def workflow_action_updated(sender, workflow_action, user, **kwargs):
    _broadcast_field(workflow_action.field, user)


@receiver(workflow_action_signals.workflow_action_deleted)
def workflow_action_deleted(sender, workflow_action_id, field, user, **kwargs):
    _broadcast_field(field, user)


@receiver(workflow_action_signals.workflow_actions_reordered)
def workflow_actions_reordered(sender, field, order, user, **kwargs):
    _broadcast_field(field, user)
