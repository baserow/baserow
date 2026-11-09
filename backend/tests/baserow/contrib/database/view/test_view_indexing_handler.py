from datetime import date, datetime, timezone
from unittest.mock import patch

from django.db import OperationalError, models, transaction

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.views.handler import ViewHandler, ViewIndexingHandler
from baserow.contrib.database.views.models import (
    OWNERSHIP_TYPE_COLLABORATIVE,
)
from baserow.contrib.database.views.signals import view_loaded
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "kind,include_time,ordering",
    [
        ("created_on", False, "sort"),
        ("last_modified", False, "sort"),
        ("created_on", False, "group"),
        ("last_modified", False, "group"),
        ("created_on", True, "group"),
        ("last_modified", True, "group"),
        ("date", True, "group"),
        ("date", False, "group"),
        ("date", True, "group_and_sort"),
    ],
)
def test_date_view_index_matches_row_ordering(
    data_fixture, kind, include_time, ordering
):
    table = data_fixture.create_database_table()
    field = getattr(data_fixture, f"create_{kind}_field")(
        table=table, date_include_time=include_time
    )
    view = data_fixture.create_grid_view(table=table)
    if ordering != "sort":
        data_fixture.create_view_group_by(view=view, field=field, order="DESC")
    if ordering != "group":
        data_fixture.create_view_sort(view=view, field=field, order="DESC")
    model = table.get_model()

    index = ViewIndexingHandler.get_index(view, model)
    assert index is not None
    queryset = ViewHandler().get_queryset(None, view, model=model)
    # A raw timestamp index can be created successfully but cannot serve the
    # truncated ordering used by rows in a date group.
    assert index.expressions[:-2] == queryset.query.order_by[:-2]

    ViewIndexingHandler.update_index(view, model)

    view.refresh_from_db()
    assert view.db_index_name == index.name
    # Metadata alone would miss PostgreSQL rejecting a non-immutable expression.
    assert ViewIndexingHandler.does_index_exist(index.name)


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["multiple_select", "multiple_collaborators"])
def test_date_group_with_many_to_many_group_remains_unindexed(data_fixture, kind):
    table = data_fixture.create_database_table()
    date_field = data_fixture.create_date_field(table=table, date_include_time=True)
    related_field = getattr(data_fixture, f"create_{kind}_field")(table=table)
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=view, field=date_field, order="ASC")
    data_fixture.create_view_group_by(view=view, field=related_field, order="ASC")

    assert ViewIndexingHandler.get_index(view) is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.views.tasks.update_view_index.delay"
)
def test_loading_date_view_replaces_legacy_timestamp_index(data_fixture, settings):
    settings.AUTO_INDEX_VIEW_ENABLED = True
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_last_modified_field(
        table=table, date_include_time=False
    )
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_sort(view=view, field=field, order="DESC")
    model = table.get_model()
    legacy_index = models.Index(
        models.F(field.db_column).desc(nulls_last=True),
        "order",
        "id",
        condition=models.Q(trashed=False),
        name=f"i{table.id}:legacy_date",
    )
    view.db_index_name = ViewIndexingHandler.create_index_if_not_exists(
        view, model, legacy_index
    )
    view.save(update_fields=["db_index_name"])
    assert ViewIndexingHandler.does_index_exist(legacy_index.name)

    with patch("baserow.contrib.database.views.tasks.update_view_index.delay") as task:
        view_loaded.send(
            sender=None, table=table, view=view, table_model=model, user=user
        )
        task.assert_called_once_with(view.id)

        # Execute the scheduled work without a broker, then reload the saved view.
        ViewIndexingHandler.update_index_by_view_id(view.id)
        view.refresh_from_db()
        index = ViewIndexingHandler.get_index(view, model)
        assert view.db_index_name == index.name
        assert ViewIndexingHandler.does_index_exist(index.name)
        assert not ViewIndexingHandler.does_index_exist(legacy_index.name)

        view_loaded.send(
            sender=None, table=table, view=view, table_model=model, user=user
        )
        task.assert_called_once_with(view.id)


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.views.tasks.update_view_index.delay"
)
def test_grouped_date_index_survives_include_time_changes(data_fixture, settings):
    settings.AUTO_INDEX_VIEW_ENABLED = True
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_date_field(table=table, date_include_time=True)
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=view, field=field)
    model = table.get_model()
    model.objects.create(
        **{field.db_column: datetime(2024, 1, 8, 9, 30, 55, tzinfo=timezone.utc)}
    )
    model.objects.create(**{field.db_column: None})
    ViewIndexingHandler.update_index(view, model)

    for include_time, expected_value in [
        (False, date(2024, 1, 8)),
        (True, datetime(2024, 1, 8, tzinfo=timezone.utc)),
    ]:
        old_index = view.db_index_name
        field = FieldHandler().update_field(user, field, date_include_time=include_time)
        view.refresh_from_db()
        assert view.db_index_name is None
        assert not ViewIndexingHandler.does_index_exist(old_index)
        model = table.get_model()
        assert list(
            model.objects.order_by("id").values_list(field.db_column, flat=True)
        ) == [expected_value, None]

        with patch(
            "baserow.contrib.database.views.tasks.update_view_index.delay"
        ) as task:
            view_loaded.send(
                sender=None, table=table, view=view, table_model=model, user=user
            )
            task.assert_called_once_with(view.id)
        ViewIndexingHandler.update_index_by_view_id(view.id)
        view.refresh_from_db()
        index = ViewIndexingHandler.get_index(view, model)
        queryset = ViewHandler().get_queryset(user, view, model=model)
        assert index.expressions[:-2] == queryset.query.order_by[:-2]
        assert view.db_index_name == index.name
        assert ViewIndexingHandler.does_index_exist(index.name)


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.views.tasks.update_view_index.delay"
)
@pytest.mark.parametrize(
    "kind,include_time,expected_value",
    [
        ("date", True, "2024-01-08 09:30"),
        ("created_on", False, "2024-01-08"),
        ("last_modified", False, "2024-01-08"),
    ],
)
def test_shared_date_group_index_is_removed_before_field_conversion(
    data_fixture, settings, kind, include_time, expected_value
):
    settings.AUTO_INDEX_VIEW_ENABLED = True
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = getattr(data_fixture, f"create_{kind}_field")(
        table=table,
        date_include_time=include_time,
        date_format="ISO",
        date_time_format="24",
    )
    views = [data_fixture.create_grid_view(table=table) for _ in range(2)]
    for view in views:
        data_fixture.create_view_group_by(view=view, field=field)
    model = table.get_model()
    row = model.objects.create()
    value = datetime(2024, 1, 8, 9, 30, 55, tzinfo=timezone.utc)
    model.objects.filter(id=row.id).update(
        created_on=value, updated_on=value, **{field.db_column: value}
    )
    for view in views:
        ViewIndexingHandler.update_index(view, model)
    old_index = views[0].db_index_name
    assert views[1].db_index_name == old_index

    field = FieldHandler().update_field(user, field, new_type_name="text")

    assert not ViewIndexingHandler.does_index_exist(old_index)
    model = table.get_model()
    assert getattr(model.objects.get(id=row.id), field.db_column) == expected_value
    for view in views:
        view.refresh_from_db()
        assert view.db_index_name is None
        with patch(
            "baserow.contrib.database.views.tasks.update_view_index.delay"
        ) as task:
            view_loaded.send(
                sender=None, table=table, view=view, table_model=model, user=user
            )
            task.assert_called_once_with(view.id)
        ViewIndexingHandler.update_index_by_view_id(view.id)
        view.refresh_from_db()
        index = ViewIndexingHandler.get_index(view, model)
        queryset = ViewHandler().get_queryset(user, view, model=model)
        assert index.expressions[:-2] == queryset.query.order_by[:-2]
        assert view.db_index_name == index.name
        assert ViewIndexingHandler.does_index_exist(index.name)
        assert list(queryset.values_list(field.db_column, flat=True)) == [
            expected_value
        ]
    assert views[0].db_index_name == views[1].db_index_name


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.views.tasks.update_view_index.delay"
)
@pytest.mark.parametrize("state", ["sort_removed", "group_removed", "trashed"])
def test_field_conversion_removes_indexes_from_old_view_configurations(
    data_fixture, settings, state
):
    settings.AUTO_INDEX_VIEW_ENABLED = True
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_created_on_field(
        table=table, date_include_time=False, date_format="ISO"
    )
    rank = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(table=table)
    other_view = data_fixture.create_grid_view(table=table)
    if state == "sort_removed":
        ordering = data_fixture.create_view_sort(view=view, field=field)
    else:
        ordering = data_fixture.create_view_group_by(view=view, field=field)
    for current_view in [view, other_view]:
        data_fixture.create_view_sort(view=current_view, field=rank)
    model = table.get_model()
    rows = []
    for day, rank_value in [(8, 2), (9, 1)]:
        row = model.objects.create(**{rank.db_column: rank_value})
        timestamp = datetime(2024, 1, day, 15, tzinfo=timezone.utc)
        model.objects.filter(pk=row.pk).update(
            created_on=timestamp, **{field.db_column: timestamp}
        )
        rows.append(row)
    for current_view in [view, other_view]:
        ViewIndexingHandler.update_index(current_view, model)
    old_index_names = [view.db_index_name, other_view.db_index_name]

    separate_table = data_fixture.create_database_table(user=user)
    separate_field = data_fixture.create_number_field(table=separate_table)
    separate_view = data_fixture.create_grid_view(table=separate_table)
    data_fixture.create_view_sort(view=separate_view, field=separate_field)
    ViewIndexingHandler.update_index(separate_view, separate_table.get_model())
    separate_index_name = separate_view.db_index_name

    # The index task has not caught up with the changed ordering or deleted view.
    with patch("baserow.contrib.database.views.tasks.update_view_index.delay"):
        if state == "sort_removed":
            ViewHandler().delete_sort(user, ordering)
        elif state == "group_removed":
            ViewHandler().delete_group_by(user, ordering)
        else:
            with transaction.atomic():
                ViewHandler().delete_view(user, view)
        assert ViewIndexingHandler.does_index_exist(old_index_names[0])

        field = FieldHandler().update_field(user, field, new_type_name="text")

    for index_name in old_index_names:
        assert not ViewIndexingHandler.does_index_exist(index_name)
    for current_view in [view, other_view]:
        current_view.refresh_from_db()
        assert current_view.db_index_name is None
    separate_view.refresh_from_db()
    assert separate_view.db_index_name == separate_index_name
    assert ViewIndexingHandler.does_index_exist(separate_index_name)
    model = table.get_model()
    assert list(
        model.objects.order_by("id").values_list(field.db_column, flat=True)
    ) == ["2024-01-08", "2024-01-09"]

    if state == "trashed":
        with transaction.atomic():
            TrashHandler.restore_item(user, "view", view.id)
        view.refresh_from_db()
    for current_view in [view, other_view]:
        with patch(
            "baserow.contrib.database.views.tasks.update_view_index.delay"
        ) as task:
            view_loaded.send(
                sender=None,
                table=table,
                view=current_view,
                table_model=model,
                user=user,
            )
            task.assert_called_once_with(current_view.id)
        ViewIndexingHandler.update_index_by_view_id(current_view.id)
        current_view.refresh_from_db()
        assert ViewIndexingHandler.does_index_exist(current_view.db_index_name)
        expected_rows = (
            rows
            if state == "trashed" and current_view == view
            else list(reversed(rows))
        )
        queryset = ViewHandler().get_queryset(user, current_view, model=model)
        assert list(queryset.values_list("id", flat=True)) == [
            row.id for row in expected_rows
        ]
    if state != "trashed":
        assert view.db_index_name == other_view.db_index_name


@pytest.mark.django_db(transaction=True)
def test_update_index_long_text_over_max_size_doesnt_fail(data_fixture):
    """
    Sort expressions use Left() to truncate text columns, so the index should
    be successfully created even when row values exceed PostgreSQL's btree
    index maximum entry size (~2712 bytes).
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    long_text_field = data_fixture.create_long_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()

    import base64
    import os

    large_text_value = base64.b64encode(os.urandom(8000)).decode("ascii")

    # Insert a row with a text value large enough that it would exceed
    # PostgreSQL's btree index maximum entry size without Left() truncation.
    table_model.objects.create(**{f"field_{long_text_field.id}": large_text_value})

    handler.create_sort(user=user, view=grid_view, field=long_text_field, order="ASC")

    ViewIndexingHandler.update_index(grid_view, table_model)

    index = ViewIndexingHandler.get_index(grid_view, table_model)
    # The index should be created successfully because Left() truncation keeps
    # the indexed values within btree's size limit.
    assert ViewIndexingHandler.does_index_exist(index.name) is True


@pytest.mark.django_db(transaction=True)
def test_update_index_multiple_fields_over_max_size_doesnt_fail(
    data_fixture,
):
    """
    Same as above but with two long text fields combined. Left() truncation
    should keep the total index entry size within limits.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    long_text_field = data_fixture.create_long_text_field(user=user, table=table)
    long_text_field_2 = data_fixture.create_long_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()

    import base64
    import os

    large_text_value = base64.b64encode(os.urandom(4000)).decode("ascii")

    # Insert a row with text values that combined would exceed PostgreSQL's btree
    # index maximum entry size without Left() truncation.
    table_model.objects.create(
        **{
            f"field_{long_text_field.id}": large_text_value,
            f"field_{long_text_field_2.id}": large_text_value,
        }
    )

    handler.create_sort(user=user, view=grid_view, field=long_text_field, order="ASC")
    handler.create_sort(user=user, view=grid_view, field=long_text_field_2, order="ASC")

    ViewIndexingHandler.update_index(grid_view, table_model)

    index = ViewIndexingHandler.get_index(grid_view, table_model)
    # The index should be created successfully because Left() truncation keeps
    # the indexed values within btree's size limit.
    assert ViewIndexingHandler.does_index_exist(index.name) is True


@pytest.mark.django_db(transaction=True)
def test_update_index_catches_operational_error_gracefully(data_fixture):
    """
    If PostgreSQL raises an OperationalError during index creation (e.g., due
    to an unforeseen size issue), the error is caught and the view's
    db_index_name is set to None instead of crashing.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()
    handler.create_sort(user=user, view=grid_view, field=text_field, order="ASC")

    # Mock the schema editor's add_index to simulate a btree size error.
    with patch(
        "baserow.contrib.database.views.handler.safe_django_schema_editor"
    ) as mock_editor_ctx:
        mock_schema_editor = mock_editor_ctx.return_value.__enter__.return_value
        mock_schema_editor.add_index.side_effect = OperationalError(
            "index row size 6568 exceeds btree version 4 maximum 2704 for index"
        )

        ViewIndexingHandler.update_index(grid_view, table_model)

    grid_view.refresh_from_db()
    # The index creation failed, so db_index_name should be None.
    assert grid_view.db_index_name is None


@pytest.mark.django_db(transaction=True)
def test_drop_all_indexes_for_table(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    grid_view_2 = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()
    handler.create_sort(user=user, view=grid_view, field=text_field, order="ASC")
    handler.create_sort(user=user, view=grid_view_2, field=text_field, order="ASC")

    ViewIndexingHandler.update_index(grid_view, table_model)
    ViewIndexingHandler.update_index(grid_view_2, table_model)
    grid_view.refresh_from_db()
    grid_view_2.refresh_from_db()
    assert grid_view.db_index_name is not None
    assert grid_view_2.db_index_name is not None

    index = ViewIndexingHandler.get_index(grid_view, table_model)
    assert ViewIndexingHandler.does_index_exist(index.name) is True

    index2 = ViewIndexingHandler.get_index(grid_view_2, table_model)
    assert ViewIndexingHandler.does_index_exist(index2.name) is True

    ViewIndexingHandler.drop_all_indexes_for_table(table.id)

    grid_view.refresh_from_db()
    assert grid_view.db_index_name is None
    assert ViewIndexingHandler.does_index_exist(index.name) is False
    grid_view_2.refresh_from_db()
    assert grid_view_2.db_index_name is None
    assert ViewIndexingHandler.does_index_exist(index2.name) is False


@pytest.mark.django_db(transaction=True)
def test_handle_index_row_size_error_drops_indexes(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()
    handler.create_sort(user=user, view=grid_view, field=text_field, order="ASC")

    ViewIndexingHandler.update_index(grid_view, table_model)
    grid_view.refresh_from_db()
    assert grid_view.db_index_name is not None

    ViewIndexingHandler.handle_index_row_size_error(table.id)

    grid_view.refresh_from_db()
    assert grid_view.db_index_name is None
