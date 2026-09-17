from itertools import groupby
from operator import attrgetter

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import Q, QuerySet
from django.dispatch import receiver

from baserow.contrib.database.fields import signals as field_signals
from baserow.contrib.database.fields.field_types import ButtonFieldType
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.models import Database
from baserow.contrib.database.table import signals as table_signals
from baserow.contrib.database.workflow_actions import signals as workflow_action_signals
from baserow.contrib.database.workflow_actions.reconfiguration import (
    button_fields_depending_on,
)
from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.core import signals as core_signals
from baserow.core.integrations import signals as integration_signals
from baserow.core.models import Application
from baserow.core.trash import signals as trash_signals
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


def _broadcast_buttons(button_fields: QuerySet[ButtonField]) -> None:
    """
    Sends these buttons out again to their tables. They usually live in
    another table than the one that changed, so nothing else tells the people
    looking at them.

    No session is left out: whoever trashed the field may be looking at the
    button's table, and nothing updates their copy either.

    Each table gets one message with its first button as `field` and the rest
    as `related_fields`, as every `field_updated` refreshes the whole grid.

    :param button_fields: The buttons whose `requires_reconfiguration` may
        have changed.
    """

    table_page_type = page_registry.get("table")
    buttons = ButtonFieldType().enhance_field_queryset_for_serialization(
        button_fields.select_related("table__database")
        .prefetch_related("field_constraints")
        .order_by("table_id", "id"),
        None,
    )
    for table_id, in_table in groupby(buttons, key=attrgetter("table_id")):
        first, *rest = in_table
        table_page_type.broadcast(
            RealtimeFieldMessages.field_updated(first, rest),
            None,
            table_id=table_id,
        )


def _broadcast_dependent_buttons(exclude: Q | None = None, **lookup) -> None:
    """
    Sends out again every button whose `requires_reconfiguration` may have
    changed because something its actions reference was trashed or restored.

    :param exclude: The buttons to leave out, as a filter on them.
    :param lookup: The `button_fields_depending_on` arguments.
    """

    def broadcast():
        button_fields = button_fields_depending_on(**lookup)
        if exclude is not None:
            button_fields = button_fields.exclude(exclude)
        _broadcast_buttons(button_fields)

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
    # Trashing a table also trashes the link fields to it in other tables,
    # without a `field_deleted` for them.
    _broadcast_dependent_buttons(table_ids=[table_id], link_row_table_ids=[table_id])


# Also sent when a table is restored from the trash, duplicated or imported. The
# buttons inside it are loaded with it, and nobody has a copy open yet.
@receiver(table_signals.table_created)
def button_target_table_created(sender, table, **kwargs):
    _broadcast_dependent_buttons(table_ids=[table.id], exclude=Q(table_id=table.id))


@receiver(core_signals.application_deleted)
def button_target_application_deleted(sender, application_id, **kwargs):
    _broadcast_dependent_buttons(database_ids=[application_id])


# Also sent when an application is restored from the trash, duplicated or
# installed from a template, so its own buttons are left out as for a table.
@receiver(core_signals.application_created)
def button_target_application_created(sender, application, **kwargs):
    _broadcast_dependent_buttons(
        database_ids=[application.id], exclude=Q(table__database_id=application.id)
    )


@receiver(core_signals.workspace_deleted)
def button_target_workspace_deleted(sender, workspace_id, **kwargs):
    _broadcast_dependent_buttons(workspace_ids=[workspace_id])


# Set on the restored workspace, which every `workspace_restored` it sends
# shares, so the buttons go out once rather than once per member.
WORKSPACE_RESTORE_SENT_ATTRIBUTE = "_dependent_buttons_broadcast"


@receiver(core_signals.workspace_restored)
def button_target_workspace_restored(sender, workspace_user, **kwargs):
    workspace = workspace_user.workspace
    if getattr(workspace, WORKSPACE_RESTORE_SENT_ATTRIBUTE, False):
        return
    setattr(workspace, WORKSPACE_RESTORE_SENT_ATTRIBUTE, True)
    _broadcast_dependent_buttons(workspace_ids=[workspace.id])


def _in_a_database(application: Application) -> bool:
    """Only a database's integrations can be used by a button."""

    return issubclass(application.specific_class, Database)


@receiver(integration_signals.integration_deleted)
def button_integration_deleted(sender, integration_id, application, **kwargs):
    if _in_a_database(application):
        _broadcast_dependent_buttons(integration_ids=[integration_id])


# Also sent when an integration is restored from the trash.
@receiver(integration_signals.integration_created)
def button_integration_created(sender, integration, **kwargs):
    if _in_a_database(integration.application):
        _broadcast_dependent_buttons(integration_ids=[integration.id])


# The `button_fields_depending_on` argument for each trash item type whose
# permanent deletion can change a button's reconfigure state. Deleting a table
# or a database can't: it leaves the service without a table, which still
# counts.
PERMANENT_DELETION_LOOKUPS = {"field": "field_ids", "integration": "integration_ids"}

# Set on the item being deleted, which both signals are sent with, so nothing
# outlives a deletion that fails between them.
DEPENDENT_BUTTONS_ATTRIBUTE = "_dependent_button_field_ids"


@receiver(trash_signals.before_permanently_deleted)
def button_dependency_before_permanently_deleted(
    sender, trash_item_id, trash_item, **kwargs
):
    lookup = PERMANENT_DELETION_LOOKUPS.get(sender)
    if lookup is None:
        return
    if sender == "integration" and not _in_a_database(trash_item.application):
        return
    # Now, while the mapping or the integration reference still exists.
    setattr(
        trash_item,
        DEPENDENT_BUTTONS_ATTRIBUTE,
        list(
            button_fields_depending_on(**{lookup: [trash_item_id]}).values_list(
                "id", flat=True
            )
        ),
    )


@receiver(trash_signals.permanently_deleted)
def button_dependency_permanently_deleted(sender, trash_item, **kwargs):
    button_field_ids = getattr(trash_item, DEPENDENT_BUTTONS_ATTRIBUTE, None)
    if not button_field_ids:
        return

    def broadcast():
        # Fetched again, so the flag is read after the deletion.
        _broadcast_buttons(
            ButtonField.objects.filter(
                id__in=button_field_ids,
                table__trashed=False,
                table__database__trashed=False,
                table__database__workspace__trashed=False,
            )
        )

    # Registered after the deletion rather than before: outside an atomic block
    # this runs straight away. Inside one, a rollback drops it.
    transaction.on_commit(broadcast)
