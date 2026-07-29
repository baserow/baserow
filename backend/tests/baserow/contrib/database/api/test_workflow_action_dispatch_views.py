from django.core.cache import cache
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import CreateRowWorkflowAction


def _button_with_create_action(data_fixture, user, value="Ada"):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value=f"'{value}'", enabled=True)
    return table, name_field, button_field, row, action


@pytest.mark.django_db
def test_dispatch_runs_the_actions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": row.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["workflow_action_id"] == action.id
    assert results[0]["status"] == "completed"
    created = table.get_model().objects.exclude(id=row.id).get()
    assert getattr(created, f"field_{name_field.id}") == "Ada"


@pytest.mark.django_db
def test_dispatch_for_a_missing_row(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    _, _, button_field, _, _ = _button_with_create_action(data_fixture, user)

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_dispatch_for_a_non_button_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    row = table.get_model().objects.create()

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": text_field.id},
        ),
        {"row_id": row.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_dispatch_in_another_workspace(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    other_user = data_fixture.create_user()
    table, _, button_field, row, _ = _button_with_create_action(
        data_fixture, other_user
    )

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": row.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert table.get_model().objects.exclude(id=row.id).count() == 0


@pytest.mark.django_db
def test_a_concurrent_click_conflicts(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, _, button_field, row, _ = _button_with_create_action(data_fixture, user)
    cache.add(f"button_dispatch_{button_field.id}_{row.id}", True, timeout=30)

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": row.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS"
    assert table.get_model().objects.exclude(id=row.id).count() == 0


@pytest.mark.django_db
def test_dispatch_requires_authentication(api_client, data_fixture):
    user = data_fixture.create_user()
    _, _, button_field, row, _ = _button_with_create_action(data_fixture, user)

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": row.id},
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
