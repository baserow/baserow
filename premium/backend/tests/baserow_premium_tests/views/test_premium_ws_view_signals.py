from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.contrib.database.api.views.serializers import ViewSerializer
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import OWNERSHIP_TYPE_COLLABORATIVE
from baserow.contrib.database.views.registries import view_type_registry
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL


@pytest.mark.django_db(transaction=True)
def test_view_signals_not_collaborative(
    data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Group 1")
    user = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    field = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    view.ownership_type = "personal"
    view.owned_by = user
    view.save()

    # view_created

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().create_view(
            user=user,
            table=table,
            type_name="grid",
            name="Grid",
            ownership_type="personal",
        )
        broadcast.delay.assert_not_called()

    with patch(
        "baserow.contrib.database.ws.views.signals.broadcast_to_users"
    ) as broadcast:
        ViewHandler().create_view(
            user=user,
            table=table,
            type_name="grid",
            name="Grid",
            ownership_type="personal",
        )
        args = broadcast.delay.call_args
        assert args[0][0] == [user.id]

    # view_updated

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().update_view(user=user, view=view, name="View")
        broadcast.delay.assert_not_called()

    # view_deleted

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        with transaction.atomic():
            ViewHandler().delete_view(user=user, view=view)
        broadcast.delay.assert_not_called()

    view = data_fixture.create_grid_view(user=user, table=table)
    view.ownership_type = "personal"
    view.owned_by = user
    view.save()

    with patch(
        "baserow.contrib.database.ws.views.signals.broadcast_to_users"
    ) as broadcast:
        with transaction.atomic():
            ViewHandler().delete_view(user=user, view=view)
        args = broadcast.delay.call_args
        assert args[0][0] == [user.id]

    view = data_fixture.create_grid_view(user=user, table=table)
    view.ownership_type = "personal"
    view.owned_by = user
    view.save()
    filter = ViewHandler().create_filter(user, view, field, "equal", "value")
    equal_sort = data_fixture.create_view_sort(user=user, view=view, field=field)
    decorator_type_name = "left_border_color"
    value_provider_type_name = ""
    value_provider_conf = {}
    decoration = data_fixture.create_view_decoration(user=user, view=view)

    # views_reordered

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().order_views(user=user, table=table, order=[view.id])
        broadcast.delay.assert_not_called()

    # view_filter_created

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().create_filter(user, view, field, "equal", "value")
        broadcast.delay.assert_not_called()

    # view_filter_updated

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().update_filter(user, filter, field, "equal", "another value")
        broadcast.delay.assert_not_called()

    # view_filter_deleted

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().delete_filter(user, filter)
        broadcast.delay.assert_not_called()

    # view_sort_created

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().create_sort(user=user, view=view, field=field2, order="ASC")
        broadcast.delay.assert_not_called()

    # view_sort_updated

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().update_sort(user, equal_sort, field)
        broadcast.delay.assert_not_called()

    # view_sort_deleted

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().delete_sort(user, equal_sort)
        broadcast.delay.assert_not_called()

    # view_decoration_created

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().create_decoration(
            view,
            decorator_type_name,
            value_provider_type_name,
            value_provider_conf,
            user=user,
        )
        broadcast.delay.assert_not_called()

    # view_decoration_updated

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().update_decoration(decoration, user)
        broadcast.delay.assert_not_called()

    # view_decoration_deleted

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().delete_decoration(decoration, user)
        broadcast.delay.assert_not_called()

    # view_field_options_updated

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        ViewHandler().update_field_options(view, {}, user)
        broadcast.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.pages.TablePageType.broadcast")
@patch("baserow.ws.tasks.broadcast_to_users.delay")
def test_view_updated_to_personal_signals(
    mock_broadcast_to_owner,
    mock_broadcast_from_page_type,
    data_fixture,
    alternative_per_workspace_license_service,
):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )

    view = data_fixture.create_grid_view(
        owned_by=user,
        table=table,
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    ViewHandler().update_view(
        user=user, view=view, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )

    mock_broadcast_from_page_type.assert_called_once()

    call_args_to_users = mock_broadcast_from_page_type.call_args
    assert call_args_to_users[0][0] == {
        "type": "view_deleted",
        "table_id": table.id,
        "view_id": view.id,
    }
    assert call_args_to_users[0][1] == user.web_socket_id
    assert call_args_to_users[1]["table_id"] == table.id
    assert call_args_to_users[1]["exclude_user_ids"] == [user.id]

    call_args_to_owner = mock_broadcast_to_owner.call_args
    assert call_args_to_owner[0][0] == [user.id]
    assert call_args_to_owner[0][1]["type"] == "view_updated"
    assert (
        call_args_to_owner[0][1]["view"]
        == view_type_registry.get_serializer(
            view,
            ViewSerializer,
            filters=False,
            sortings=False,
            decorations=False,
            group_bys=False,
        ).data
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.pages.TablePageType.broadcast")
@patch("baserow.ws.tasks.broadcast_to_users.delay")
def test_view_updated_to_collaborative_signals(
    mock_broadcast_to_owner,
    mock_broadcast_from_page_type,
    data_fixture,
    alternative_per_workspace_license_service,
):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )

    view = data_fixture.create_grid_view(
        owned_by=user,
        table=table,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )
    ViewHandler().update_view(
        user=user, view=view, ownership_type=OWNERSHIP_TYPE_COLLABORATIVE
    )

    mock_broadcast_from_page_type.assert_called_once()
    call_args_to_users = mock_broadcast_from_page_type.call_args

    assert call_args_to_users[0][0]["type"] == "view_created"
    assert (
        call_args_to_users[0][0]["view"]
        == view_type_registry.get_serializer(
            view,
            ViewSerializer,
            filters=True,
            sortings=True,
            decorations=True,
            group_bys=True,
        ).data
    )
    assert call_args_to_users[0][1] == user.web_socket_id
    assert call_args_to_users[1]["table_id"] == table.id
    assert call_args_to_users[1]["exclude_user_ids"] == [user.id]

    call_args_to_owner = mock_broadcast_to_owner.call_args
    assert call_args_to_owner[0][0] == [user.id]
    assert call_args_to_owner[0][1]["type"] == "view_updated"
    assert (
        call_args_to_owner[0][1]["view"]
        == view_type_registry.get_serializer(
            view,
            ViewSerializer,
            filters=False,
            sortings=False,
            decorations=False,
            group_bys=False,
        ).data
    )


@pytest.mark.parametrize(
    "original_ownership_type,new_ownership_type",
    [
        (OWNERSHIP_TYPE_PERSONAL, OWNERSHIP_TYPE_COLLABORATIVE),
        (OWNERSHIP_TYPE_COLLABORATIVE, OWNERSHIP_TYPE_PERSONAL),
        (OWNERSHIP_TYPE_PERSONAL, OWNERSHIP_TYPE_PERSONAL),
        (OWNERSHIP_TYPE_COLLABORATIVE, OWNERSHIP_TYPE_COLLABORATIVE),
    ],
)
@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.views.signals.broadcast_to_users_ownership_change")
def test_broadcast_to_users_ownership_changed(
    mock_broadcast_to_users_ownership_change,
    data_fixture,
    alternative_per_workspace_license_service,
    original_ownership_type,
    new_ownership_type,
):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )

    old_view = data_fixture.create_grid_view(
        owned_by=user,
        table=table,
        ownership_type=original_ownership_type,
    )
    updated_view = (
        ViewHandler()
        .update_view(user=user, view=old_view, ownership_type=new_ownership_type)
        .updated_view_instance
    )

    payload = {
        "type": "view_updated",
        "view_id": updated_view.id,
        "view": view_type_registry.get_serializer(
            updated_view,
            ViewSerializer,
            filters=False,
            sortings=False,
            decorations=False,
            group_bys=False,
        ).data,
    }

    if new_ownership_type != original_ownership_type:
        mock_broadcast_to_users_ownership_change.assert_called_once_with(
            user,
            updated_view,
            old_view,
            payload,
        )
    else:
        mock_broadcast_to_users_ownership_change.assert_not_called()
