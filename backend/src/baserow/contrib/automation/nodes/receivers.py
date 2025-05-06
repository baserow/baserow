from django.dispatch import receiver

from baserow.contrib.database.rows.signals import rows_created, rows_updated


@receiver(rows_created)
def trigger_on_rows_created(sender, rows, before, user, table, **kwargs):
    """
    To be implemented. We'll probably want to:
        - Check if the table matches any linked LocalBaserowRowCreatedNodeType
            instances.
        - Enqueue a task to dispatch the appropriate action.
    """


@receiver(rows_updated)
def trigger_on_rows_updated(
    sender, rows, user, table, model, before_return, updated_field_ids, **kwargs
):
    """
    To be implemented. We'll probably want to:
        - Check if the row/table matches any linked RowUpdatedNodeType instances.
        - Enqueue a task to dispatch the appropriate action.
    """
