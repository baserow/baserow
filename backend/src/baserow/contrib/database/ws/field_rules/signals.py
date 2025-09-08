from datetime import timedelta

from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.field_rules import signals as field_rules_signals
from baserow.contrib.database.field_rules.operations import ReadFieldRuleOperationType
from baserow.contrib.database.table.object_scopes import DatabaseTableObjectScopeType
from baserow.ws.tasks import broadcast_to_permitted_users


def send_payload(message_type, table, rule, user):
    database = table.database
    payload = rule.to_dict()
    # Celery's default json serializer can't understand timedelta type, so we
    # change it to number of seconds (int).
    if isinstance(payload.get("dependency_buffer"), timedelta):
        payload["dependency_buffer"] = payload["dependency_buffer"].total_seconds()

    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            database.workspace_id,
            ReadFieldRuleOperationType.type,
            DatabaseTableObjectScopeType.type,
            rule.table_id,
            {
                "type": message_type,
                "database_id": database.id,
                "table_id": table.id,
                "rule": payload,
            },
            # we want to send this to all users, even current one. This is because
            # field rule changes are triggering background tasks, and the updated
            # state is not transmitted otherwise to the originating user.
            None,
        )
    )


@receiver(field_rules_signals.field_rule_created)
def on_field_rule_created(sender, table, rule, user, **kwargs):
    send_payload("field_rule_created", table, rule, user)


@receiver(field_rules_signals.field_rule_updated)
def on_field_rule_updated(sender, table, rule, user, **kwargs):
    send_payload("field_rule_updated", table, rule, user)


@receiver(field_rules_signals.field_rule_deleted)
def on_field_rule_deleted(sender, table, rule, user, **kwargs):
    send_payload("field_rule_deleted", table, rule, user)
