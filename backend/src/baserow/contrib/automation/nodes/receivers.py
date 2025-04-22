from django.dispatch import receiver

from baserow.contrib.database.rows.signals import (
    rows_created,
    rows_updated,
)


@receiver(rows_created)
def trigger_on_rows_created(sender, rows, before, user, table, **kwargs):
    """
    TODO
    
    - Check if the table matches any linked TriggerNodeRowCreated instances.
    - If so, enqueue a task for celery call the related action node in a
        separate thread
    """


@receiver(rows_updated)
def trigger_on_rows_updated(
    sender, rows, user, table, model, before_return, updated_field_ids, **kwargs
):
    """
    TODO
    
    - Check if the row/table matches any linked TriggerNodeRowUpdated instances.
    - If so, enqueue a task for celery call the related action node in a
        separate thread
    """
