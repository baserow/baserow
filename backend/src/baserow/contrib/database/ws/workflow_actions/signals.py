from itertools import groupby
from operator import attrgetter
from typing import Iterable

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import Q, QuerySet
from django.dispatch import receiver

from baserow.contrib.database.fields import signals as field_signals
from baserow.contrib.database.fields.field_types import ButtonFieldType
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.fields.registries import field_type_registry
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


def button_fields_updated_message(fields: Iterable[ButtonField]) -> dict:
    """
    The payload that carries these button fields out to a page. Only
    `has_workflow_actions` and `requires_reconfiguration` can have changed, and
    neither says anything about the rows, so this is a separate message from
    `field_updated`: that one makes the client refetch the whole grid.

    :param fields: The button fields to send, all in the same table.
    """

    return {
        "type": "button_fields_updated",
        "fields": RealtimeFieldMessages.serialize_fields_for_websockets(fields),
    }


@receiver(workflow_action_signals.button_fields_updated)
def broadcast_button_fields_updated(sender, table_id, fields, user, **kwargs):
    """Sends the button fields of a table to everyone looking at that table."""

    page_registry.get("table").broadcast(
        button_fields_updated_message(fields),
        getattr(user, "web_socket_id", None),
        table_id=table_id,
    )


def _broadcast_field(field: ButtonField, user: AbstractUser) -> None:
    """
    Sends the button field out again, so everyone else's copy of
    `has_workflow_actions` matches what the field now has. A cell renders an
    inert button or a working one from that alone, and nothing else about an
    action is of any use outside the editor.

    :param field: The button field whose actions changed.
    :param user: The user who changed them, whose own session already knows.
    """

    transaction.on_commit(
        # Sent here rather than above: `has_workflow_actions` counts the
        # actions, and the change is only committed by the time this runs.
        lambda: workflow_action_signals.button_fields_updated.send(
            ButtonField, table_id=field.table_id, fields=[field], user=user
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

    Each table gets one message with all of its buttons in it.

    :param button_fields: The buttons whose `requires_reconfiguration` may
        have changed.
    """

    buttons = ButtonFieldType().enhance_field_queryset_for_serialization(
        button_fields.select_related("table__database")
        .prefetch_related("field_constraints")
        .order_by("table_id", "id"),
        None,
    )
    for table_id, in_table in groupby(buttons, key=attrgetter("table_id")):
        workflow_action_signals.button_fields_updated.send(
            ButtonField, table_id=table_id, fields=list(in_table), user=None
        )


def _broadcast_dependent_buttons(
    exclude: Q | None = None, once_key: tuple | None = None, **lookup
) -> None:
    """
    Sends out again every button whose `requires_reconfiguration` may have
    changed because something its actions reference was trashed or restored.

    :param exclude: The buttons to leave out, as a filter on them.
    :param once_key: When set, a broadcast already waiting for the same commit
        with this key makes this one a no-op.
    :param lookup: The `button_fields_depending_on` arguments.
    """

    def broadcast():
        button_fields = button_fields_depending_on(**lookup)
        if exclude is not None:
            button_fields = button_fields.exclude(exclude)
        _broadcast_buttons(button_fields)

    if once_key is not None:
        broadcast.once_key = once_key
        # A rollback drops its callbacks from this list, so a key never
        # outlives its transaction.
        waiting = transaction.get_connection().run_on_commit
        if any(getattr(f, "once_key", None) == once_key for _, f, _ in waiting):
            return

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


# Sent once per member, in the restore's transaction, so the buttons are keyed
# to go out once. Its own buttons are left out as for a table.
@receiver(core_signals.workspace_restored)
def button_target_workspace_restored(sender, workspace_user, **kwargs):
    workspace_id = workspace_user.workspace_id
    _broadcast_dependent_buttons(
        workspace_ids=[workspace_id],
        exclude=Q(table__database__workspace_id=workspace_id),
        once_key=("workspace_restored", workspace_id),
    )


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
# permanent deletion can change a button's reconfigure state. A table takes the
# link fields to it in other tables with it, and their mappings. A service
# left without a table still counts, as it did while the table was trashed.
#
# An application and a workspace are here because they can be deleted without
# ever being trashed, and so without the `application_deleted` or
# `workspace_deleted` that would have flagged the buttons pointing into them:
# `delete_expired_users` purges a workspace whose last admin left, the admin
# panel deletes one outright, and a snapshot's application is dropped when it
# expires. Deleting a database deletes its tables without trashing them too,
# which the application entry covers. `permanently_empty_database` does the
# same to the tables alone, and the buttons targeting them are only flagged
# once they are fetched again.
PERMANENT_DELETION_LOOKUPS = {
    "field": "field_ids",
    "table": "link_row_table_ids",
    "application": "database_ids",
    "workspace": "workspace_ids",
    "integration": "integration_ids",
}

# The buttons deleted along with each container, which nobody needs to hear
# about.
PERMANENT_DELETION_EXCLUDES = {
    "table": lambda item_id: Q(table_id=item_id),
    "application": lambda item_id: Q(table__database_id=item_id),
    "workspace": lambda item_id: Q(table__database__workspace_id=item_id),
}

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
    if sender == "application" and not _in_a_database(trash_item):
        return
    ids = [trash_item_id]
    if sender == "field":
        # Deleted with it, like a link field's related field, and so are their
        # mappings.
        field = trash_item.specific
        field_type = field_type_registry.get_by_model(field)
        ids += [
            other.id
            for other in field_type.get_other_fields_to_trash_restore_always_together(
                field
            )
        ]
    button_fields = button_fields_depending_on(**{lookup: ids})
    exclude = PERMANENT_DELETION_EXCLUDES.get(sender)
    if exclude is not None:
        button_fields = button_fields.exclude(exclude(trash_item_id))
    # Now, while the mapping, the link field or the integration reference exists.
    setattr(
        trash_item,
        DEPENDENT_BUTTONS_ATTRIBUTE,
        list(button_fields.values_list("id", flat=True)),
    )


@receiver(trash_signals.permanently_deleted)
def button_dependency_permanently_deleted(sender, trash_item, **kwargs):
    button_field_ids = getattr(trash_item, DEPENDENT_BUTTONS_ATTRIBUTE, None)
    if not button_field_ids:
        return

    # Purging a workspace or a database also purges each of its tables, and
    # both can collect the same button. One broadcast waiting for the commit
    # takes them all. A rollback drops it from this list along with its ids.
    waiting = transaction.get_connection().run_on_commit
    for _, callback, _ in waiting:
        pending = getattr(callback, "purged_button_field_ids", None)
        if pending is not None:
            pending.update(button_field_ids)
            return

    def broadcast():
        # Fetched again, so the flag is read after the deletion.
        _broadcast_buttons(
            ButtonField.objects.filter(
                id__in=broadcast.purged_button_field_ids,
                table__trashed=False,
                table__database__trashed=False,
                table__database__workspace__trashed=False,
            )
        )

    broadcast.purged_button_field_ids = set(button_field_ids)
    # Registered after the deletion rather than before: outside an atomic block
    # this runs straight away. Inside one, a rollback drops it.
    transaction.on_commit(broadcast)
