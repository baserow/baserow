from django.dispatch import receiver

from baserow.contrib.database.fields.signals import field_deleted, field_updated


@receiver([field_updated, field_deleted])
def on_field_change(sender, field, user, **kwargs):
    from .handlers import FieldRuleHandler

    fh = FieldRuleHandler(field.table, user)
    if fh.has_field_rules():
        fh.on_table_change()
