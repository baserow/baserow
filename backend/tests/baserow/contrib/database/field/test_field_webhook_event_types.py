import pytest

from baserow.contrib.database.webhooks.registries import webhook_event_type_registry


@pytest.mark.django_db()
def test_field_created_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(name="Field", primary=False, table=table)

    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("field.created").get_payload(
        event_id="1", webhook=webhook, field=field, table=table
    )
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "field.created",
        "field": {
            "id": field.id,
            "table_id": table.id,
            "name": "Field",
            "order": 0,
            "type": "text",
            "primary": False,
            "read_only": False,
            "immutable_type": False,
            "immutable_properties": False,
            "description": None,
            "text_default": "",
            "database_id": table.database_id,
            "workspace_id": table.database.workspace_id,
            "db_index": False,
            "field_constraints": [],
        },
    }


@pytest.mark.django_db()
def test_field_created_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("field.created")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "field.created",
        "field": {
            "id": 0,
            "table_id": 0,
            "name": "Field",
            "order": 1,
            "type": "text",
            "primary": False,
            "read_only": False,
            "immutable_type": False,
            "immutable_properties": False,
            "description": None,
            "text_default": "",
            "database_id": None,
            "workspace_id": None,
            "db_index": False,
            "field_constraints": [],
        },
    }


@pytest.mark.django_db()
def test_field_updated_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(name="Field", table=table)

    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("field.updated").get_payload(
        event_id="1",
        webhook=webhook,
        field=field,
        old_field=field,
        table=table,
    )
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "field.updated",
        "field": {
            "id": field.id,
            "table_id": table.id,
            "name": "Field",
            "order": 0,
            "type": "text",
            "primary": False,
            "read_only": False,
            "immutable_type": False,
            "immutable_properties": False,
            "description": None,
            "text_default": "",
            "database_id": table.database_id,
            "workspace_id": table.database.workspace_id,
            "db_index": False,
            "field_constraints": [],
        },
    }


@pytest.mark.django_db()
def test_field_updated_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("field.updated")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "field.updated",
        "field": {
            "id": 0,
            "table_id": 0,
            "name": "Field",
            "order": 1,
            "type": "text",
            "primary": False,
            "read_only": False,
            "immutable_type": False,
            "immutable_properties": False,
            "description": None,
            "text_default": "",
            "database_id": None,
            "workspace_id": None,
            "db_index": False,
            "field_constraints": [],
        },
    }


@pytest.mark.django_db()
def test_field_deleted_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Test 1")

    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("field.deleted").get_payload(
        event_id="1",
        webhook=webhook,
        field_id=field.id,
        table=table,
    )

    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "field.deleted",
        "field_id": field.id,
    }


@pytest.mark.django_db()
def test_field_deleted_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("field.deleted")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "field.deleted",
        "field_id": 1,
    }
