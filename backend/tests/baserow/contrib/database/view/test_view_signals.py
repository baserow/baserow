from unittest.mock import patch

from django.db import transaction

import pytest
from freezegun import freeze_time

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.tasks import run_periodic_fields_updates
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler, ViewSubscriptionHandler
from baserow.contrib.database.views.signals import (
    view_loaded_create_indexes_and_columns,
)
from baserow.core.cache import local_cache
from baserow.core.trash.handler import TrashHandler


@patch("baserow.contrib.database.views.handler.ViewIndexingHandler")
@pytest.mark.django_db
def test_view_loaded_creates_last_modified_by_column(indexing_handler, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(
        user=user, last_modified_by_column_added=True
    )
    table_model = table.get_model()
    view = data_fixture.create_grid_view(user=user, table=table)

    # won't schedule column creation if already added
    with patch(
        "baserow.contrib.database.table.tasks.setup_created_by_and_last_modified_by_column"
    ) as setup:
        view_loaded_create_indexes_and_columns(
            None, view, table_model, table=table, user=user
        )
        setup.delay.assert_not_called()

    # schedule column creation if not added yet
    table.last_modified_by_column_added = False
    table.save()
    with patch(
        "baserow.contrib.database.table.tasks.setup_created_by_and_last_modified_by_column"
    ) as setup:
        view_loaded_create_indexes_and_columns(
            None, view, table_model, table=table, user=user
        )
        setup.delay.assert_called_once_with(table_id=view.table.id)


@pytest.mark.django_db
def test_rows_enter_and_exit_view_are_called_when_rows_updated(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables()

    # Create a view per table and assert that the the signal is called for both tables
    # when changing the link_a_to_b data
    row_handler = RowHandler()
    model_a = table_a.get_model()
    model_b = table_b.get_model()
    row_a = model_a.objects.create()
    row_b = model_b.objects.create()

    view_a = data_fixture.create_grid_view(table=table_a)
    view_a_has_row_b = data_fixture.create_view_filter(
        view=view_a, field=link_a_to_b, type="link_row_has", value=row_b.id
    )

    view_b = data_fixture.create_grid_view(table=table_b)
    view_b_has_row_a = data_fixture.create_view_filter(
        view=view_b,
        field=link_a_to_b.link_row_related_field,
        type="link_row_has",
        value=row_a.id,
    )

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        row_handler.force_update_rows(
            user,
            table_a,
            [{"id": row_a.id, link_a_to_b.db_column: [row_b.id]}],
            model_a,
        )
        p.assert_not_called()

    # let's subscribe to the view in table_a first
    ViewSubscriptionHandler.subscribe_to_views(user, [view_a])

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        row_handler.force_update_rows(
            user, table_a, [{"id": row_a.id, link_a_to_b.db_column: []}]
        )
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [row_a.id]

    # Now let's subscribe also to the view in table_b and assert that the signal is
    # called for both views
    ViewSubscriptionHandler.subscribe_to_views(user, [view_b])

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        row_handler.force_update_rows(
            user,
            table_a,
            [{"id": row_a.id, link_a_to_b.db_column: [row_b.id]}],
            model_a,
        )
        assert p.call_count == 2
        assert p.call_args_list[0][1]["view"].id == view_a.id
        assert p.call_args_list[1][1]["row_ids"] == [row_a.id]
        assert p.call_args_list[1][1]["view"].id == view_b.id
        assert p.call_args_list[1][1]["row_ids"] == [row_b.id]

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        row_handler.force_update_rows(
            user, table_a, [{"id": row_a.id, link_a_to_b.db_column: []}]
        )
        assert p.call_count == 2
        assert p.call_args_list[0][1]["view"].id == view_a.id
        assert p.call_args_list[1][1]["row_ids"] == [row_a.id]
        assert p.call_args_list[1][1]["view"].id == view_b.id
        assert p.call_args_list[1][1]["row_ids"] == [row_b.id]

    # Once unsubcribed, the signal should not be sent anymore
    ViewSubscriptionHandler.unsubscribe_from_views(user)
    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        row_handler.force_update_rows(
            user,
            table_a,
            [{"id": row_a.id, link_a_to_b.db_column: [row_b.id]}],
            model_a,
        )
        p.assert_not_called()


@pytest.mark.django_db
def test_rows_enter_and_exit_view_are_called_when_rows_created_or_deleted(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables()

    row_handler = RowHandler()
    model_a = table_a.get_model()
    model_b = table_b.get_model()
    row_b = model_b.objects.create()

    view_a = data_fixture.create_grid_view(table=table_a)
    view_a_has_row_b = data_fixture.create_view_filter(
        view=view_a, field=link_a_to_b, type="link_row_has", value=row_b.id
    )

    view_b = data_fixture.create_grid_view(table=table_b)
    view_b_has_row_a = data_fixture.create_view_filter(
        view=view_b, field=link_a_to_b.link_row_related_field, type="not_empty"
    )

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        (new_row,) = row_handler.force_create_rows(
            user, table_a, [{link_a_to_b.db_column: [row_b.id]}], model=model_a
        ).created_rows
        p.assert_not_called()

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        row_handler.force_delete_rows(user, table_a, [new_row.id])
        p.assert_not_called()

    # let's subscribe to the view in table_a first
    ViewSubscriptionHandler.subscribe_to_views(user, [view_a])

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        (new_row,) = row_handler.force_create_rows(
            user, table_a, [{link_a_to_b.db_column: [row_b.id]}], model=model_a
        ).created_rows
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [new_row.id]

    # Deleting the row should also trigger the signal
    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        row_handler.force_delete_rows(user, table_a, [new_row.id])
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [new_row.id]

    # Now let's subscribe also to the view in table_b and assert that the signal is
    # called for both views
    ViewSubscriptionHandler.subscribe_to_views(user, [view_b])

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        (new_row,) = row_handler.force_create_rows(
            user, table_a, [{link_a_to_b.db_column: [row_b.id]}], model=model_a
        ).created_rows
        assert p.call_count == 2
        assert p.call_args_list[0][1]["view"].id == view_a.id
        assert p.call_args_list[0][1]["row_ids"] == [new_row.id]
        assert p.call_args_list[1][1]["view"].id == view_b.id
        assert p.call_args_list[1][1]["row_ids"] == [row_b.id]

    # Deleting the row should also trigger the signal for both views
    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        row_handler.force_delete_rows(user, table_a, [new_row.id])
        assert p.call_count == 2
        assert p.call_args_list[0][1]["view"].id == view_a.id
        assert p.call_args_list[0][1]["row_ids"] == [new_row.id]
        assert p.call_args_list[1][1]["view"].id == view_b.id
        assert p.call_args_list[1][1]["row_ids"] == [row_b.id]

    # Once unsubcribed, the signal should not be sent anymore
    ViewSubscriptionHandler.unsubscribe_from_views(user)
    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        (new_row,) = row_handler.force_create_rows(
            user, table_a, [{link_a_to_b.db_column: [row_b.id]}], model=model_a
        ).created_rows
        p.assert_not_called()

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        row_handler.force_delete_rows(user, table_a, [new_row.id])
        p.assert_not_called()


@pytest.mark.django_db
def test_rows_enter_and_exit_view_are_called_when_view_filters_change(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table_a)

    model_a = table_a.get_model()

    view_a = data_fixture.create_grid_view(table=table_a)
    row_1 = model_a.objects.create()
    row_2 = model_a.objects.create(**{text_field.db_column: "bbb"})

    ViewSubscriptionHandler.subscribe_to_views(user, [view_a])

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        view_filter_1 = ViewHandler().create_filter(
            user, view_a, text_field, "equal", "aaa"
        )
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [row_1.id, row_2.id]

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        view_filter_1 = ViewHandler().delete_filter(user, view_filter_1)
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [row_1.id, row_2.id]

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        view_filter_2 = ViewHandler().create_filter(
            user, view_a, text_field, "equal", "bbb"
        )
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [row_1.id]

    with patch(
        "baserow.contrib.database.views.signals.rows_entered_view.send"
    ) as entered, patch(
        "baserow.contrib.database.views.signals.rows_exited_view.send"
    ) as exited:
        view_filter_2 = ViewHandler().update_filter(
            user, view_filter_2, type_name="empty"
        )
        entered.assert_called_once()
        assert entered.call_args[1]["view"].id == view_a.id
        assert entered.call_args[1]["row_ids"] == [row_1.id]

        exited.assert_called_once()
        assert exited.call_args[1]["view"].id == view_a.id
        assert exited.call_args[1]["row_ids"] == [row_2.id]

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        view_filter_3 = ViewHandler().create_filter(
            user, view_a, text_field, "equal", "bbb"
        )
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [row_1.id]

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        ViewHandler().update_view(user, view_a, filters_disabled=True)

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [row_1.id, row_2.id]


@pytest.mark.django_db
def test_rows_enter_and_exit_view_are_called_when_view_filter_groups_change(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table_a)

    model_a = table_a.get_model()

    view = data_fixture.create_grid_view(table=table_a)
    row_1 = model_a.objects.create()
    row_2 = model_a.objects.create(**{text_field.db_column: "bbb"})

    ViewSubscriptionHandler.subscribe_to_views(user, [view])

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        filter_group_1 = ViewHandler().create_filter_group(user, view)
        p.assert_not_called()

        view_filter_1 = ViewHandler().create_filter(
            user, view, text_field, "empty", "", filter_group_id=filter_group_1.id
        )

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_2.id]

        view_filter_2 = ViewHandler().create_filter(
            user, view, text_field, "equal", "bbb", filter_group_id=filter_group_1.id
        )

        p.call_count == 2
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id]

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        ViewHandler().update_filter_group(user, filter_group_1, filter_type="OR")

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id, row_2.id]

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        filter_group_2 = ViewHandler().create_filter_group(user, view)
        p.assert_not_called()

        view_filter_3 = ViewHandler().create_filter(
            user, view, text_field, "equal", "aaa", filter_group_id=filter_group_2.id
        )

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id, row_2.id]

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        ViewHandler().delete_filter_group(user, filter_group_2)

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id, row_2.id]


@pytest.mark.django_db
def test_rows_enter_and_exit_view_are_called_when_fields_change(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user=user)
    primary_field = data_fixture.create_text_field(table=table_a, primary=True)
    text_field = data_fixture.create_text_field(table=table_a)
    text_field_id = text_field.id

    model_a = table_a.get_model()

    view = data_fixture.create_grid_view(table=table_a)
    row_1 = model_a.objects.create()
    row_2 = model_a.objects.create(**{text_field.db_column: "bbb"})
    view_filter_1 = data_fixture.create_view_filter(
        view=view, field=text_field, type="equal", value="bbb"
    )

    ViewSubscriptionHandler.subscribe_to_views(user, [view])

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        FieldHandler().delete_field(user, text_field)

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id]

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        TrashHandler.restore_item(user, "field", text_field_id)

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id]

    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        FieldHandler().update_field(user, text_field, new_type_name="number")

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id]


@pytest.mark.django_db
def test_rows_enter_and_exit_view_with_periodic_fields_updates(data_fixture):
    user = data_fixture.create_user()

    with freeze_time("2021-01-01"):
        table = data_fixture.create_database_table(user=user)
        now_field = data_fixture.create_formula_field(
            table=table, formula="today()", name="today"
        )
        year_field = data_fixture.create_formula_field(
            table=table, formula="tonumber(datetime_format(field('today'), 'YYYY'))"
        )
        local_cache.delete(f"database_table_model_{table.id}*")

        model = table.get_model()

        view = data_fixture.create_grid_view(table=table)
        row_1 = model.objects.create()
        view_filter_1 = data_fixture.create_view_filter(
            view=view, field=year_field, type="equal", value="2022"
        )

    ViewSubscriptionHandler.subscribe_to_views(user, [view])

    with patch(
        "baserow.contrib.database.views.signals.rows_entered_view.send"
    ) as p, freeze_time("2022-01-01"), local_cache.context():
        run_periodic_fields_updates(table.database.workspace_id)

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id]

    with patch(
        "baserow.contrib.database.views.signals.rows_exited_view.send"
    ) as p, freeze_time("2023-01-01"), local_cache.context():
        run_periodic_fields_updates(table.database.workspace_id)

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id]


@pytest.mark.django_db(transaction=True)
def test_rows_enter_and_exit_view_when_time_sensitive_filters_are_used(
    data_fixture,
):
    user = data_fixture.create_user()

    with freeze_time("2021-01-01"):
        table = data_fixture.create_database_table(user=user)
        date_field = data_fixture.create_date_field(table=table)

        model = table.get_model()

        view = data_fixture.create_grid_view(table=table)
        row_1 = model.objects.create(**{date_field.db_column: "2022-01-01"})
        view_filter_1 = data_fixture.create_view_filter(
            view=view, field=date_field, type="date_is", value="Europe/Rome??today"
        )
        ViewSubscriptionHandler.subscribe_to_views(user, [view])

    with patch(
        "baserow.contrib.database.views.signals.rows_entered_view.send"
    ) as p, freeze_time("2022-01-01"):
        with transaction.atomic():
            ViewSubscriptionHandler.check_views_with_time_sensitive_filters()

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id]

    with patch(
        "baserow.contrib.database.views.signals.rows_exited_view.send"
    ) as p, freeze_time("2022-01-02"):
        with transaction.atomic():
            ViewSubscriptionHandler.check_views_with_time_sensitive_filters()

        p.assert_called_once()
        assert p.call_args[1]["view"].id == view.id
        assert p.call_args[1]["row_ids"] == [row_1.id]


@pytest.mark.django_db
def test_rows_enter_and_exit_view_when_data_changes_in_looked_up_tables(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables()
    text_field_b = data_fixture.create_text_field(table=table_b)
    lookup_field = data_fixture.create_lookup_field(
        name="lookup",
        table=table_a,
        through_field=link_a_to_b,
        target_field=text_field_b,
        through_field_name=link_a_to_b.name,
        target_field_name=text_field_b.name,
    )

    # Create a view per table and assert that the the signal is called for both tables
    # when changing the link_a_to_b data
    row_handler = RowHandler()
    model_a = table_a.get_model()
    model_b = table_b.get_model()
    (row_b1,) = row_handler.force_create_rows(
        user, table_b, [{text_field_b.db_column: ""}], model=model_b
    ).created_rows
    _, row_a2 = row_handler.force_create_rows(
        user, table_a, [{}, {link_a_to_b.db_column: [row_b1.id]}], model=model_a
    ).created_rows

    view_a = data_fixture.create_grid_view(table=table_a)
    view_filter = data_fixture.create_view_filter(
        view=view_a, field=lookup_field, type="has_not_empty_value", value=""
    )

    ViewSubscriptionHandler.subscribe_to_views(user, [view_a])
    with patch("baserow.contrib.database.views.signals.rows_entered_view.send") as p:
        row_handler.force_update_rows(
            user, table_b, [{"id": row_b1.id, text_field_b.db_column: "a"}], model_b
        )
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [row_a2.id]

        (row_a3,) = row_handler.force_create_rows(
            user, table_a, [{link_a_to_b.db_column: [row_b1.id]}], model=model_a
        ).created_rows

        assert p.call_count == 2
        assert p.call_args_list[1][1]["view"].id == view_a.id
        assert p.call_args_list[1][1]["row_ids"] == [row_a3.id]

    with patch("baserow.contrib.database.views.signals.rows_exited_view.send") as p:
        row_handler.force_update_rows(
            user, table_b, [{"id": row_b1.id, text_field_b.db_column: ""}], model_b
        )
        p.assert_called_once()
        assert p.call_args[1]["view"].id == view_a.id
        assert p.call_args[1]["row_ids"] == [row_a2.id, row_a3.id]
