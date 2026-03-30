from django.dispatch import Signal, receiver

from baserow.contrib.database.fields import signals as field_signals

view_loaded = Signal()
view_created = Signal()
view_updated = Signal()
view_deleted = Signal()
views_reordered = Signal()
form_submitted = Signal()

view_filter_created = Signal()
view_filter_updated = Signal()
view_filter_deleted = Signal()

view_filter_group_created = Signal()
view_filter_group_updated = Signal()
view_filter_group_deleted = Signal()

view_sort_created = Signal()
view_sort_updated = Signal()
view_sort_deleted = Signal()

view_group_by_created = Signal()
view_group_by_updated = Signal()
view_group_by_deleted = Signal()

view_decoration_created = Signal()
view_decoration_updated = Signal()
view_decoration_deleted = Signal()

view_field_options_updated = Signal()

rows_entered_view = Signal()
rows_exited_view = Signal()


@receiver(field_signals.field_deleted)
def field_deleted(sender, field, **kwargs):
    from baserow.contrib.database.views.registries import (
        decorator_value_provider_type_registry,
        view_type_registry,
    )

    for view_type in view_type_registry.get_all():
        view_type.after_field_delete(field)

    # Call value provider type hooks
    for (
        decorator_value_provider_type
    ) in decorator_value_provider_type_registry.get_all():
        decorator_value_provider_type.after_field_delete(field)

    from baserow.contrib.database.views.handler import ViewIndexingHandler

    ViewIndexingHandler.after_fields_changed_or_deleted([field])


@receiver([view_sort_created, view_sort_updated, view_sort_deleted])
def update_view_index_if_view_sort_changes(sender, view_sort, **kwargs):
    from baserow.contrib.database.views.handler import ViewIndexingHandler

    ViewIndexingHandler.schedule_index_update(view_sort.view)


@receiver(
    [
        view_group_by_created,
        view_group_by_updated,
        view_group_by_deleted,
    ]
)
def update_view_index_if_view_group_by_changes(sender, view_group_by, **kwargs):
    from baserow.contrib.database.views.handler import ViewIndexingHandler

    ViewIndexingHandler.schedule_index_update(view_group_by.view)


@receiver(view_loaded)
def view_loaded_create_indexes_and_columns(sender, view, table_model, **kwargs):
    from baserow.contrib.database.table.tasks import (
        setup_created_by_and_last_modified_by_column,
        setup_m2m_field_indexes_if_not_exist,
    )
    from baserow.contrib.database.views.handler import ViewIndexingHandler

    ViewIndexingHandler.schedule_index_creation_if_needed(view, table_model)

    table = view.table
    if not table.last_modified_by_column_added or not table.created_by_column_added:
        setup_created_by_and_last_modified_by_column.delay(table_id=view.table.id)
    if not table.missing_m2m_indexes_added:
        setup_m2m_field_indexes_if_not_exist.delay(table_id=view.table_id)


@receiver(field_signals.fields_type_changed)
def view_fields_type_changed(sender, fields, **kwargs):
    from baserow.contrib.database.views.handler import ViewHandler

    ViewHandler().fields_type_changed(fields)
