from datetime import timedelta

from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.field_rules import signals as field_rules_signals
from baserow.core.utils import generate_hash
from baserow.ws.tasks import broadcast_to_group


def send_payload(message_type, table, rule, user):
    database = table.database
    payload = rule.to_dict()
    # json serializer can't understand the buffer
    if isinstance(payload.get("dependency_buffer"), timedelta):
        payload["dependency_buffer"] = payload["dependency_buffer"].total_seconds()

    transaction.on_commit(
        lambda: broadcast_to_group.delay(
            database.workspace_id,
            {
                "type": message_type,
                # A user might also not have access to the database itself
                "database_id": generate_hash(database.id),
                "table_id": table.id,
                "rule": payload,
            },
            None,  # getattr(user, "web_socket_id", None),
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
