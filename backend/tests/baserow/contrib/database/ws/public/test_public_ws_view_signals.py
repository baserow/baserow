from unittest.mock import ANY, call, patch

from django.db import transaction

import pytest

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.api.views.serializers import PublicViewInfoSerializer
from baserow.contrib.database.views.handler import ViewHandler


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_when_view_filter_created_for_public_view_force_refresh_sent(
    mock_broadcast_to_channel_group, data_fixture, public_realtime_view_tester
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    public_view = public_realtime_view_tester.create_public_view(
        user, table, visible_fields=[field]
    )
    public_realtime_view_tester.create_other_views_that_should_not_get_realtime_signals(
        user, table, mock_broadcast_to_channel_group
    )
    ViewHandler().create_filter(
        user=user, view=public_view, type_name="equal", value="test", field=field
    )

    assert mock_broadcast_to_channel_group.delay.mock_calls == (
        [
            call(f"table-{table.id}", ANY, ANY, None),
            call(
                f"view-{public_view.slug}",
                {"type": "force_view_rows_refresh", "view_id": public_view.slug},
                None,
                None,
            ),
        ]
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_when_view_filter_updated_for_public_view_force_refresh_event_sent(
    mock_broadcast_to_channel_group, data_fixture, public_realtime_view_tester
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    public_view = public_realtime_view_tester.create_public_view(
        user, table, visible_fields=[field]
    )
    public_realtime_view_tester.create_other_views_that_should_not_get_realtime_signals(
        user, table, mock_broadcast_to_channel_group
    )
    view_filter = data_fixture.create_view_filter(
        user=user, view=public_view, field=field
    )
    ViewHandler().update_filter(user=user, view_filter=view_filter, value="test2")

    assert mock_broadcast_to_channel_group.delay.mock_calls == (
        [
            call(f"table-{table.id}", ANY, ANY, None),
            call(
                f"view-{public_view.slug}",
                {"type": "force_view_rows_refresh", "view_id": public_view.slug},
                None,
                None,
            ),
        ]
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_when_view_filter_deleted_for_public_view_force_refresh_event_sent(
    mock_broadcast_to_channel_group, data_fixture, public_realtime_view_tester
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    public_view = public_realtime_view_tester.create_public_view(
        user, table, visible_fields=[field]
    )
    public_realtime_view_tester.create_other_views_that_should_not_get_realtime_signals(
        user, table, mock_broadcast_to_channel_group
    )
    view_filter = data_fixture.create_view_filter(
        user=user, view=public_view, field=field
    )
    ViewHandler().delete_filter(user=user, view_filter=view_filter)

    assert mock_broadcast_to_channel_group.delay.mock_calls == (
        [
            call(f"table-{table.id}", ANY, ANY, None),
            call(
                f"view-{public_view.slug}",
                {"type": "force_view_rows_refresh", "view_id": public_view.slug},
                None,
                None,
            ),
        ]
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_when_field_hidden_in_public_view_field_force_refresh_sent(
    mock_broadcast_to_channel_group, data_fixture, public_realtime_view_tester
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    public_grid_view = public_realtime_view_tester.create_public_view(
        user, table, visible_fields=[text_field]
    )
    public_realtime_view_tester.create_other_views_that_should_not_get_realtime_signals(
        user, table, mock_broadcast_to_channel_group
    )

    # No public events should be sent to form views
    public_form_view = data_fixture.create_form_view(
        user=user, table=table, public=True
    )
    handler = ViewHandler()

    with transaction.atomic():
        handler.update_field_options(
            user=user,
            view=public_form_view,
            field_options={str(text_field.id): {"hidden": True}},
        )

    with transaction.atomic():
        handler.update_field_options(
            user=user,
            view=public_grid_view,
            field_options={str(text_field.id): {"hidden": True}},
        )

    view_serialized = PublicViewInfoSerializer(
        view=public_grid_view,
        fields=[],
    ).data

    assert mock_broadcast_to_channel_group.delay.mock_calls == (
        [
            call(f"table-{table.id}", ANY, ANY, None),
            call(f"table-{table.id}", ANY, ANY, None),
            call(
                f"view-{public_grid_view.slug}",
                {
                    "type": "force_view_refresh",
                    "view_id": public_grid_view.slug,
                    "fields": [],
                    "view": view_serialized["view"],
                },
                None,
                None,
            ),
        ]
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_when_field_unhidden_in_public_view_force_refresh_sent(
    mock_broadcast_to_channel_group, data_fixture, public_realtime_view_tester
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    public_grid_view = public_realtime_view_tester.create_public_view(
        user, table, visible_fields=[text_field]
    )
    public_realtime_view_tester.create_other_views_that_should_not_get_realtime_signals(
        user, table, mock_broadcast_to_channel_group
    )
    handler = ViewHandler()

    # No public events should be sent to form views
    public_form_view = data_fixture.create_form_view(
        user=user, table=table, public=True
    )

    with transaction.atomic():
        handler.update_field_options(
            user=user,
            view=public_form_view,
            field_options={str(text_field.id): {"hidden": False}},
        )

    with transaction.atomic():
        handler.update_field_options(
            user=user,
            view=public_grid_view,
            field_options={str(text_field.id): {"hidden": False}},
        )

    view_serialized = PublicViewInfoSerializer(
        view=public_grid_view,
        fields=[],
    ).data

    assert mock_broadcast_to_channel_group.delay.mock_calls == (
        [
            call(f"table-{table.id}", ANY, ANY, None),
            call(f"table-{table.id}", ANY, ANY, None),
            call(
                f"view-{public_grid_view.slug}",
                {
                    "type": "force_view_refresh",
                    "view_id": public_grid_view.slug,
                    "fields": [
                        {
                            "id": text_field.id,
                            "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                            "name": text_field.name,
                            "order": 0,
                            "type": "text",
                            "primary": False,
                            "text_default": "",
                            "read_only": False,
                            "description": None,
                            "immutable_properties": False,
                            "immutable_type": False,
                            "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                            "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                            "db_index": False,
                            "field_constraints": [],
                        }
                    ],
                    "view": view_serialized["view"],
                },
                None,
                None,
            ),
        ]
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_when_only_field_options_updated_in_public_grid_view_force_refresh_sent(
    mock_broadcast_to_channel_group, data_fixture, public_realtime_view_tester
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    visible_field = data_fixture.create_text_field(table=table)
    hidden_field = data_fixture.create_text_field(table=table)
    public_grid_view = public_realtime_view_tester.create_public_view(
        user, table, visible_fields=[visible_field], hidden_fields=[hidden_field]
    )
    public_realtime_view_tester.create_other_views_that_should_not_get_realtime_signals(
        user, table, mock_broadcast_to_channel_group
    )
    handler = ViewHandler()

    # No public events should be sent to form views
    public_form_view = data_fixture.create_form_view(
        user=user, table=table, public=True
    )
    with transaction.atomic():
        handler.update_field_options(
            user=user,
            view=public_form_view,
            field_options={
                str(visible_field.id): {"order": 2},
                str(hidden_field.id): {"order": 1},
            },
        )

    with transaction.atomic():
        handler.update_field_options(
            user=user,
            view=public_grid_view,
            field_options={
                str(visible_field.id): {"order": 2},
                str(hidden_field.id): {"order": 1},
            },
        )

    view_serialized = PublicViewInfoSerializer(
        view=public_grid_view,
        fields=[],
    ).data

    assert mock_broadcast_to_channel_group.delay.mock_calls == (
        [
            call(f"table-{table.id}", ANY, ANY, None),
            call(f"table-{table.id}", ANY, ANY, None),
            call(
                f"view-{public_grid_view.slug}",
                {
                    "type": "force_view_refresh",
                    "view_id": public_grid_view.slug,
                    "fields": [
                        {
                            "id": visible_field.id,
                            "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                            "name": visible_field.name,
                            "order": 0,
                            "type": "text",
                            "primary": False,
                            "text_default": "",
                            "read_only": False,
                            "description": None,
                            "immutable_properties": False,
                            "immutable_type": False,
                            "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                            "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                            "db_index": False,
                            "field_constraints": [],
                        }
                    ],
                    "view": view_serialized["view"],
                },
                None,
                None,
            ),
        ]
    )
