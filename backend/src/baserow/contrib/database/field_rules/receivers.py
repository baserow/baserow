from django.dispatch import receiver

from baserow.contrib.database.fields.signals import field_deleted, field_updated


@receiver([field_updated, field_deleted])
def on_field_change(sender, field, user, **kwargs):
    from .handlers import FieldRuleHandler

    field_rules_handler = FieldRuleHandler(field.table, user)
    if field_rules_handler.has_field_rules():
        field_rules_handler.on_table_change()
