from unittest.mock import Mock

from django.conf import settings
from django.db import connection
from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_402_PAYMENT_REQUIRED

from baserow.contrib.database.api.rows.serializers import serialize_rows_for_response
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.registries import (
    data_sync_type_registry,
    two_way_sync_strategy_type_registry,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.db import specific_iterator
from baserow.core.notifications.models import Notification
from baserow_enterprise.data_sync.notification_types import (
    TwoWaySyncDeactivatedNotificationType,
    TwoWaySyncUpdateFailedNotificationType,
)


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_create_two_way_data_sync_strategy_without_enterprise_license(
    enterprise_data_fixture, create_postgresql_test_table, api_client
):
    default_database = settings.DATABASES["default"]
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id", "text_col"],
            "two_way_sync": True,
            "postgresql_host": default_database["HOST"],
            "postgresql_username": default_database["USER"],
            "postgresql_password": default_database["PASSWORD"],
            "postgresql_port": default_database["PORT"],
            "postgresql_database": default_database["NAME"],
            "postgresql_table": create_postgresql_test_table,
            "postgresql_sslmode": default_database["OPTIONS"].get("sslmode", "prefer"),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["error"] == "ERROR_FEATURE_NOT_AVAILABLE"
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db(transaction=True)
def test_update_two_way_data_sync_strategy_without_enterprise_license(
    enterprise_data_fixture, create_postgresql_test_table, api_client
):
    default_database = settings.DATABASES["default"]
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id", "text_col"],
            "two_way_sync": False,
            "postgresql_host": default_database["HOST"],
            "postgresql_username": default_database["USER"],
            "postgresql_password": default_database["PASSWORD"],
            "postgresql_port": default_database["PORT"],
            "postgresql_database": default_database["NAME"],
            "postgresql_table": create_postgresql_test_table,
            "postgresql_sslmode": default_database["OPTIONS"].get("sslmode", "prefer"),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    data_sync_id = response_json["data_sync"]["id"]

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync_id})
    response = api_client.patch(
        url,
        {
            "two_way_sync": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["error"] == "ERROR_FEATURE_NOT_AVAILABLE"
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_update_row_is_retried_on_sync_error(
    enterprise_data_fixture, create_postgresql_test_table, api_client, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    row_handler = RowHandler()
    rows = row_handler.create_rows(
        user=user,
        table=data_sync.table,
        rows_values=[
            {
                f"field_{text_field.id}": "text",
            }
        ],
        signal_params={"skip_two_way_sync": True},
    ).created_rows

    model = data_sync.table.get_model()
    serialized_rows = serialize_rows_for_response(rows, model)
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    # Rename the table, so that the rows_created call will fail.
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {create_postgresql_test_table} RENAME TO {create_postgresql_test_table}_tmp;"
        )

    mock_task_context = Mock()
    mock_task_context.request.retries = 0
    mock_task_context.retry = Mock()

    two_way_sync_strategy.rows_created(mock_task_context, serialized_rows, data_sync)

    mock_task_context.retry.assert_called_once_with(countdown=2**0)

    # Rename the table, so that the rows_created call will fail.
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {create_postgresql_test_table}_tmp RENAME TO {create_postgresql_test_table};"
        )


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_two_way_sync_is_notified_after_retries(
    enterprise_data_fixture, create_postgresql_test_table, api_client, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    row_handler = RowHandler()
    rows = row_handler.create_rows(
        user=user,
        table=data_sync.table,
        rows_values=[
            {
                f"field_{text_field.id}": "text",
            }
        ],
        signal_params={"skip_two_way_sync": True},
    ).created_rows

    model = data_sync.table.get_model()
    serialized_rows = serialize_rows_for_response(rows, model)
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    # Rename the table, so that the rows_created call will fail.
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {create_postgresql_test_table} RENAME TO {create_postgresql_test_table}_tmp;"
        )

    mock_task_context = Mock()
    mock_task_context.request.retries = 3
    mock_task_context.retry = Mock()

    two_way_sync_strategy.rows_created(mock_task_context, serialized_rows, data_sync)

    all_notifications = list(Notification.objects.all())
    assert len(all_notifications) == 1
    recipient_ids = [r.id for r in all_notifications[0].recipients.all()]
    assert recipient_ids == [user.id]
    notification = all_notifications[0]
    assert notification.type == TwoWaySyncUpdateFailedNotificationType.type
    assert notification.broadcast is False
    assert notification.workspace_id == data_sync.table.database.workspace_id
    assert notification.sender is None
    assert notification.data["data_sync_id"] == data_sync.id
    assert notification.data["table_name"] == data_sync.table.name
    assert notification.data["table_id"] == data_sync.table.id
    assert notification.data["database_id"] == data_sync.table.database_id
    assert notification.data["error"].startswith(
        """Database error: relation "public.test_table" does not exist"""
    )

    mock_task_context.retry.assert_not_called()

    data_sync.refresh_from_db()
    assert data_sync.two_way_sync_consecutive_failures == 1

    # Change the table name back, so that it will properly be deleted when this test
    # finishes.
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {create_postgresql_test_table}_tmp RENAME TO {create_postgresql_test_table};"
        )


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_two_way_sync_is_deactivated_after_consecutive_failure(
    enterprise_data_fixture, create_postgresql_test_table, api_client, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)

    # Create a field unrelated to the data sync that is writeable to make sure that
    # one is not set to read_only after the data sync is deactivated.
    enterprise_data_fixture.create_text_field(read_only=False)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.two_way_sync_consecutive_failures = 8
    data_sync.save()

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    row_handler = RowHandler()
    rows = row_handler.create_rows(
        user=user,
        table=data_sync.table,
        rows_values=[
            {
                f"field_{text_field.id}": "text",
            }
        ],
        signal_params={"skip_two_way_sync": True},
    ).created_rows

    model = data_sync.table.get_model()
    serialized_rows = serialize_rows_for_response(rows, model)
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    # Rename the table, so that the rows_created call will fail.
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {create_postgresql_test_table} RENAME TO {create_postgresql_test_table}_tmp;"
        )

    mock_task_context = Mock()
    mock_task_context.request.retries = 3
    mock_task_context.retry = Mock()

    two_way_sync_strategy.rows_created(mock_task_context, serialized_rows, data_sync)

    all_notifications = list(Notification.objects.all().order_by("id"))
    assert len(all_notifications) == 2
    recipient_ids = [r.id for r in all_notifications[1].recipients.all()]
    assert recipient_ids == [user.id]
    assert all_notifications[1].type == TwoWaySyncDeactivatedNotificationType.type
    assert all_notifications[1].broadcast is False
    assert all_notifications[1].workspace_id == data_sync.table.database.workspace_id
    assert all_notifications[1].sender is None
    assert all_notifications[1].data == {
        "data_sync_id": data_sync.id,
        "table_name": data_sync.table.name,
        "table_id": data_sync.table.id,
        "database_id": data_sync.table.database_id,
    }

    mock_task_context.retry.assert_not_called()

    data_sync.refresh_from_db()
    assert data_sync.two_way_sync_consecutive_failures == 9
    assert data_sync.two_way_sync is False

    # Should be equal to one because we created one independant writable field.
    assert Field.objects.filter(read_only=False).count() == 1

    # Change the table name back, so that it will properly be deleted when this test
    # finishes.
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {create_postgresql_test_table}_tmp RENAME TO {create_postgresql_test_table};"
        )


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_two_way_sync_consecutive_failures_are_reset_on_success(
    enterprise_data_fixture, create_postgresql_test_table, api_client, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)

    # Create a field unrelated to the data sync that is writeable to make sure that
    # one is not set to read_only after the data sync is deactivated.
    enterprise_data_fixture.create_text_field(read_only=False)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.two_way_sync_consecutive_failures = 3
    data_sync.save()

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    row_handler = RowHandler()
    rows = row_handler.create_rows(
        user=user,
        table=data_sync.table,
        rows_values=[
            {
                f"field_{text_field.id}": "text",
            }
        ],
        signal_params={"skip_two_way_sync": True},
    ).created_rows

    model = data_sync.table.get_model()
    serialized_rows = serialize_rows_for_response(rows, model)
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    mock_task_context = Mock()
    mock_task_context.request.retries = 0
    mock_task_context.retry = Mock()

    two_way_sync_strategy.rows_created(mock_task_context, serialized_rows, data_sync)

    data_sync.refresh_from_db()
    assert data_sync.two_way_sync_consecutive_failures == 0


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_two_way_sync_update_without_valid_license(
    enterprise_data_fixture, create_postgresql_test_table, api_client
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)

    # Create a field unrelated to the data sync that is writeable to make sure that
    # one is not set to read_only after the data sync is deactivated.
    enterprise_data_fixture.create_text_field(read_only=False)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    enterprise_data_fixture.delete_all_licenses()

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    row_handler = RowHandler()
    rows = row_handler.create_rows(
        user=user,
        table=data_sync.table,
        rows_values=[
            {
                f"field_{text_field.id}": "text",
            }
        ],
        signal_params={"skip_two_way_sync": True},
    ).created_rows

    model = data_sync.table.get_model()
    serialized_rows = serialize_rows_for_response(rows, model)
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    mock_task_context = Mock()
    mock_task_context.request.retries = 0
    mock_task_context.retry = Mock()

    two_way_sync_strategy.rows_created(mock_task_context, serialized_rows, data_sync)

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT count(*) " f"FROM {create_postgresql_test_table}",
        )
        result = cursor.fetchone()
        # Should be equal to the old number because no rows should have been created.
        assert result[0] == 2
