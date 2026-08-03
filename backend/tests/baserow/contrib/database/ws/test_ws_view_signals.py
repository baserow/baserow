from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.contrib.database.views.handler import ViewHandler


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_created(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    view = ViewHandler().create_view(
        user=user, table=table, type_name="grid", name="Grid"
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "view_created"
    assert args[0][1]["view"]["id"] == view.id
    assert "filters" in args[0][1]["view"]
    assert "sortings" in args[0][1]["view"]
    assert "group_bys" in args[0][1]["view"]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_updated(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user)
    ViewHandler().update_view(user=user, view=view, name="View")

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view.table.id}"
    assert args[0][1]["type"] == "view_updated"
    assert args[0][1]["view_id"] == view.id
    assert args[0][1]["view"]["id"] == view.id
    assert "filters" not in args[0][1]["view"]
    assert "sortings" not in args[0][1]["view"]
    assert "group_bys" not in args[0][1]["view"]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_deleted(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user)
    view_id = view.id
    table_id = view.table_id
    with transaction.atomic():
        ViewHandler().delete_view(user=user, view=view)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view.table.id}"
    assert args[0][1]["type"] == "view_deleted"
    assert args[0][1]["view_id"] == view_id
    assert args[0][1]["table_id"] == table_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_views_reordered(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user)
    ViewHandler().order_views(user=user, table=view.table, order=[view.id])

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view.table.id}"
    assert args[0][1]["type"] == "views_reordered"
    assert args[0][1]["table_id"] == view.table.id
    assert args[0][1]["order"] == [view.id]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_filter_created(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    view_filter = ViewHandler().create_filter(
        user=user, view=view, type_name="equal", value="test", field=field
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "view_filter_created"
    assert args[0][1]["view_filter"]["id"] == view_filter.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_filter_updated(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view_filter = data_fixture.create_view_filter(user=user)
    view_filter = ViewHandler().update_filter(
        user=user, view_filter=view_filter, value="test2"
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_filter.view.table.id}"
    assert args[0][1]["type"] == "view_filter_updated"
    assert args[0][1]["view_filter_id"] == view_filter.id
    assert args[0][1]["view_filter"]["id"] == view_filter.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_filter_deleted(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view_filter = data_fixture.create_view_filter(user=user)
    view_id = view_filter.view.id
    view_filter_id = view_filter.id
    ViewHandler().delete_filter(user=user, view_filter=view_filter)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_filter.view.table.id}"
    assert args[0][1]["type"] == "view_filter_deleted"
    assert args[0][1]["view_id"] == view_id
    assert args[0][1]["view_filter_id"] == view_filter_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_sort_created(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    view_sort = ViewHandler().create_sort(
        user=user, view=view, field=field, order="ASC"
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "view_sort_created"
    assert args[0][1]["view_sort"]["id"] == view_sort.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_sort_updated(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view_sort = data_fixture.create_view_sort(user=user)
    view_sort = ViewHandler().update_sort(user=user, view_sort=view_sort, order="DESC")

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_sort.view.table.id}"
    assert args[0][1]["type"] == "view_sort_updated"
    assert args[0][1]["view_sort_id"] == view_sort.id
    assert args[0][1]["view_sort"]["id"] == view_sort.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_sort_deleted(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view_sort = data_fixture.create_view_sort(user=user)
    view_id = view_sort.view.id
    view_sort_id = view_sort.id
    ViewHandler().delete_sort(user=user, view_sort=view_sort)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_sort.view.table.id}"
    assert args[0][1]["type"] == "view_sort_deleted"
    assert args[0][1]["view_id"] == view_id
    assert args[0][1]["view_sort_id"] == view_sort_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_decoration_created(mock_broadcast_to_channel_group, data_fixture):
    data_fixture.register_temp_decorators_and_value_providers()
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    view_decoration = ViewHandler().create_decoration(
        user=user,
        view=view,
        decorator_type_name="tmp_decorator_type_1",
        value_provider_type_name="",
        value_provider_conf={},
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "view_decoration_created"
    assert args[0][1]["view_decoration"]["id"] == view_decoration.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_decoration_updated(mock_broadcast_to_channel_group, data_fixture):
    data_fixture.register_temp_decorators_and_value_providers()
    user = data_fixture.create_user()
    view_decoration = data_fixture.create_view_decoration(user=user)
    view_decoration = ViewHandler().update_decoration(
        user=user,
        view_decoration=view_decoration,
        decorator_type_name="tmp_decorator_type_2",
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_decoration.view.table.id}"
    assert args[0][1]["type"] == "view_decoration_updated"
    assert args[0][1]["view_decoration_id"] == view_decoration.id
    assert args[0][1]["view_decoration"]["id"] == view_decoration.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_decoration_deleted(mock_broadcast_to_channel_group, data_fixture):
    data_fixture.register_temp_decorators_and_value_providers()
    user = data_fixture.create_user()
    view_decoration = data_fixture.create_view_decoration(user=user)
    view_id = view_decoration.view.id
    view_decoration_id = view_decoration.id
    ViewHandler().delete_decoration(user=user, view_decoration=view_decoration)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_decoration.view.table.id}"
    assert args[0][1]["type"] == "view_decoration_deleted"
    assert args[0][1]["view_id"] == view_id
    assert args[0][1]["view_decoration_id"] == view_decoration_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_field_options_updated(mock_broadcast_to_channel_group, data_fixture):
    data_fixture.register_temp_decorators_and_value_providers()
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    with transaction.atomic():
        ViewHandler().update_field_options(
            user=user,
            view=grid_view,
            field_options={str(text_field.id): {"width": 150}},
        )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "view_field_options_updated"
    assert args[0][1]["view_id"] == grid_view.id
    assert args[0][1]["field_options"][str(text_field.id)]["width"] == 150


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_group_by_created(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    view_group_by = ViewHandler().create_group_by(
        user=user,
        view=view,
        field=field,
        order="ASC",
        width=150,
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "view_group_by_created"
    assert args[0][1]["view_group_by"]["id"] == view_group_by.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_group_by_updated(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view_group_by = data_fixture.create_view_group_by(user=user)
    view_group_by = ViewHandler().update_group_by(
        user=user, view_group_by=view_group_by, order="DESC"
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_group_by.view.table.id}"
    assert args[0][1]["type"] == "view_group_by_updated"
    assert args[0][1]["view_group_by_id"] == view_group_by.id
    assert args[0][1]["view_group_by"]["id"] == view_group_by.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_group_by_deleted(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view_group_by = data_fixture.create_view_group_by(user=user)
    view_id = view_group_by.view.id
    view_group_by_id = view_group_by.id
    ViewHandler().delete_group_by(user=user, view_group_by=view_group_by)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_group_by.view.table.id}"
    assert args[0][1]["type"] == "view_group_by_deleted"
    assert args[0][1]["view_id"] == view_id
    assert args[0][1]["view_group_by_id"] == view_group_by_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_filter_group_created(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user=user, table=table)
    view_filter_group = ViewHandler().create_filter_group(user=user, view=view)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "view_filter_group_created"
    assert args[0][1]["view_filter_group"]["id"] == view_filter_group.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_filter_group_updated(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view_filter_group = data_fixture.create_view_filter_group(user=user)
    ViewHandler().update_filter_group(
        user=user, filter_group=view_filter_group, filter_type="OR"
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_filter_group.view.table.id}"
    assert args[0][1]["type"] == "view_filter_group_updated"
    assert args[0][1]["view_filter_group_id"] == view_filter_group.id
    assert args[0][1]["view_filter_group"]["id"] == view_filter_group.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_view_filter_group_deleted(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    view_filter_group = data_fixture.create_view_filter_group(user=user)
    view_id = view_filter_group.view.id
    view_filter_group_id = view_filter_group.id
    ViewHandler().delete_filter_group(user=user, filter_group=view_filter_group)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{view_filter_group.view.table.id}"
    assert args[0][1]["type"] == "view_filter_group_deleted"
    assert args[0][1]["view_id"] == view_id
    assert args[0][1]["view_filter_group_id"] == view_filter_group_id
