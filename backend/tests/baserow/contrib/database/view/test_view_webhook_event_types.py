from django.contrib.auth.models import AnonymousUser

import pytest

from baserow.contrib.database.webhooks.registries import webhook_event_type_registry


@pytest.mark.django_db()
def test_view_created_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(name="View", table=table)

    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("view.created").get_payload(
        event_id="1", webhook=webhook, view=view, table=table, user=AnonymousUser
    )
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.created",
        "view": {
            "id": view.id,
            "table_id": view.table_id,
            "name": "View",
            "order": 0,
            "type": "grid",
            "table": {
                "id": view.table_id,
                "name": view.table.name,
                "order": 0,
                "database_id": view.table.database_id,
            },
            "filter_type": "AND",
            "filters_disabled": False,
            "public_view_has_password": False,
            "show_logo": True,
            "allow_public_export": False,
            "ownership_type": "collaborative",
            "owned_by_id": None,
            "row_identifier_type": "id",
            "public": False,
            "slug": view.slug,
            "row_height_size": "small",
        },
    }


@pytest.mark.django_db()
def test_view_created_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("view.created")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    del payload["view"]["slug"]
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.created",
        "view": {
            "id": 0,
            "table_id": 0,
            "name": "View",
            "order": 1,
            "type": "grid",
            "table": None,
            "filter_type": "AND",
            "filters_disabled": False,
            "public_view_has_password": False,
            "show_logo": True,
            "allow_public_export": False,
            "ownership_type": "collaborative",
            "owned_by_id": None,
            "row_identifier_type": "id",
            "public": False,
            "row_height_size": "small",
        },
    }


@pytest.mark.django_db()
def test_view_updated_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(name="View", table=table)

    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("view.updated").get_payload(
        event_id="1",
        webhook=webhook,
        view=view,
        old_view=view,
        table=table,
        user=AnonymousUser,
    )
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.updated",
        "view": {
            "id": view.id,
            "table_id": view.table_id,
            "name": "View",
            "order": 0,
            "type": "grid",
            "table": {
                "id": view.table_id,
                "name": view.table.name,
                "order": 0,
                "database_id": view.table.database_id,
            },
            "filter_type": "AND",
            "filters_disabled": False,
            "public_view_has_password": False,
            "show_logo": True,
            "allow_public_export": False,
            "ownership_type": "collaborative",
            "owned_by_id": None,
            "row_identifier_type": "id",
            "public": False,
            "slug": view.slug,
            "row_height_size": "small",
        },
    }


@pytest.mark.django_db()
def test_view_updated_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("view.updated")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    del payload["view"]["slug"]
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.updated",
        "view": {
            "id": 0,
            "table_id": 0,
            "name": "View",
            "order": 1,
            "type": "grid",
            "table": None,
            "filter_type": "AND",
            "filters_disabled": False,
            "public_view_has_password": False,
            "show_logo": True,
            "allow_public_export": False,
            "ownership_type": "collaborative",
            "owned_by_id": None,
            "row_identifier_type": "id",
            "public": False,
            "row_height_size": "small",
        },
    }


@pytest.mark.django_db()
def test_view_deleted_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(table=table, name="Test 1")

    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("view.deleted").get_payload(
        event_id="1", webhook=webhook, view_id=view.id, table=table, user=AnonymousUser
    )

    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.deleted",
        "view_id": view.id,
    }


@pytest.mark.django_db()
def test_view_deleted_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("view.deleted")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.deleted",
        "view_id": 1,
    }
