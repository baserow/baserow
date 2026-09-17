from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.fields import signals as field_signals
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.table import signals as table_signals
from baserow.contrib.database.workflow_actions import signals as workflow_action_signals
from baserow.contrib.database.workflow_actions.reconfiguration import (
    button_fields_depending_on,
)
from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.core import signals as core_signals
from baserow.core.integrations import signals as integration_signals
from baserow.ws.registries import page_registry


def _broadcast_field(field: ButtonField, user: AbstractUser) -> None:
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


def _broadcast_dependent_buttons(**lookup) -> None:
    """
    Sends out again every button whose `requires_reconfiguration` may have
    changed because something its actions reference was trashed or restored.
    Those buttons usually live in another table than the one that changed, so
    nothing else tells the people looking at them.

    No session is left out: whoever trashed the field may be looking at the
    button's table, and nothing updates their copy either.

    :param lookup: The `button_fields_depending_on` arguments.
    """

    def broadcast():
        table_page_type = page_registry.get("table")
        for button_field in button_fields_depending_on(**lookup):
            table_page_type.broadcast(
                RealtimeFieldMessages.field_updated(button_field, []),
                None,
                table_id=button_field.table_id,
            )

    # Looked up on commit, so the trash state it reads is the committed one.
    transaction.on_commit(broadcast)


@receiver(field_signals.field_deleted)
def button_target_field_deleted(sender, field_id, **kwargs):
    _broadcast_dependent_buttons(field_ids=[field_id])


@receiver(field_signals.field_restored)
def button_target_field_restored(sender, field, **kwargs):
    _broadcast_dependent_buttons(field_ids=[field.id])


@receiver(table_signals.table_deleted)
def button_target_table_deleted(sender, table_id, **kwargs):
    _broadcast_dependent_buttons(table_ids=[table_id])


# Also sent when a table is restored from the trash.
@receiver(table_signals.table_created)
def button_target_table_created(sender, table, **kwargs):
    _broadcast_dependent_buttons(table_ids=[table.id])


@receiver(core_signals.application_deleted)
def button_target_application_deleted(sender, application_id, **kwargs):
    _broadcast_dependent_buttons(database_ids=[application_id])


# Also sent when an application is restored from the trash.
@receiver(core_signals.application_created)
def button_target_application_created(sender, application, **kwargs):
    _broadcast_dependent_buttons(database_ids=[application.id])


@receiver(integration_signals.integration_deleted)
def button_integration_deleted(sender, integration_id, **kwargs):
    _broadcast_dependent_buttons(integration_ids=[integration_id])


# Also sent when an integration is restored from the trash.
@receiver(integration_signals.integration_created)
def button_integration_created(sender, integration, **kwargs):
    _broadcast_dependent_buttons(integration_ids=[integration.id])
