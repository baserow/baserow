from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
)
from baserow.core.services.models import Service


@pytest.mark.django_db
def test_create_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:list",
            kwargs={"field_id": button_field.id},
        ),
        {"type": "local_baserow_create_row"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    data = response.json()
    assert data["type"] == "local_baserow_create_row"
    assert data["order"] == 1
    assert data["service"]["type"] == "local_baserow_upsert_row"
    assert DatabaseWorkflowAction.objects.count() == 1


@pytest.mark.django_db
def test_create_ignores_a_supplied_integration(api_client, data_fixture):
    """A service tied to an integration dispatches as that integration's
    `authorized_user` instead of as the clicker, so the id must never be
    accepted here (ADR 006 section 5)."""

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    other_user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(
        user=other_user, authorized_user=other_user
    )

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:list",
            kwargs={"field_id": button_field.id},
        ),
        {
            "type": "local_baserow_create_row",
            "service": {
                "type": "local_baserow_upsert_row",
                "integration_id": integration.id,
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    action = LocalBaserowCreateRowWorkflowAction.objects.get(id=response.json()["id"])
    assert action.service.integration_id is None


@pytest.mark.django_db
def test_update_ignores_a_supplied_integration(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    other_user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(
        user=other_user, authorized_user=other_user
    )

    response = api_client.patch(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": action.id},
        ),
        {
            "type": "local_baserow_create_row",
            "service": {
                "type": "local_baserow_upsert_row",
                "integration_id": integration.id,
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    action.refresh_from_db()
    assert action.service.integration_id is None


@pytest.mark.django_db
def test_create_with_an_unknown_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:list",
            kwargs={"field_id": button_field.id},
        ),
        {"type": "nonsense"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_list_workflow_actions_in_order(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    first = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    response = api_client.get(
        reverse(
            "api:database:workflow_actions:list",
            kwargs={"field_id": button_field.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert [a["id"] for a in response.json()] == [first.id, second.id]


@pytest.mark.django_db
def test_list_for_a_field_in_another_workspace(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=other_user)
    button_field = data_fixture.create_button_field(table=table)

    response = api_client.get(
        reverse(
            "api:database:workflow_actions:list",
            kwargs={"field_id": button_field.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_update_workflow_action_service(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    target_table = data_fixture.create_database_table(
        user=user, database=table.database
    )
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    response = api_client.patch(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": action.id},
        ),
        {
            "type": "local_baserow_create_row",
            "service": {
                "type": "local_baserow_upsert_row",
                "table_id": target_table.id,
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    action.refresh_from_db()
    assert action.service.specific.table_id == target_table.id


# `transaction=True`: the old service is deleted from an `on_commit` receiver.
@pytest.mark.django_db(transaction=True)
def test_update_workflow_action_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    first = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    old_service_id = action.service_id

    response = api_client.patch(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": action.id},
        ),
        {"type": "local_baserow_delete_row"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["type"] == "local_baserow_delete_row"

    (updated,) = [
        a.specific
        for a in DatabaseWorkflowAction.objects.filter(field=button_field)
        if a.id != first.id
    ]
    assert isinstance(updated, LocalBaserowDeleteRowWorkflowAction)
    assert updated.service.specific.get_type().type == "local_baserow_delete_row"
    assert updated.field_id == button_field.id
    assert updated.order == action.order
    # The old service must be disposed of, not left orphaned.
    assert not Service.objects.filter(id=old_service_id).exists()


@pytest.mark.django_db
def test_update_a_workflow_action_in_another_workspace(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=other_user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    target_table = data_fixture.create_database_table(
        user=other_user, database=table.database
    )

    response = api_client.patch(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": action.id},
        ),
        {
            "type": "local_baserow_create_row",
            "service": {
                "type": "local_baserow_upsert_row",
                "table_id": target_table.id,
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    action.refresh_from_db()
    assert action.service.specific.table_id is None


@pytest.mark.django_db
def test_delete_a_workflow_action_in_another_workspace(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=other_user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    response = api_client.delete(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": action.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert DatabaseWorkflowAction.objects.filter(id=action.id).exists()


@pytest.mark.django_db
def test_delete_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    response = api_client.delete(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": action.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert DatabaseWorkflowAction.objects.count() == 0


@pytest.mark.django_db
def test_delete_a_missing_workflow_action(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    response = api_client.delete(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": 0},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_order_workflow_actions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    first = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:order",
            kwargs={"field_id": button_field.id},
        ),
        {"workflow_action_ids": [second.id, first.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    first.refresh_from_db()
    second.refresh_from_db()
    assert second.order < first.order


@pytest.mark.django_db
def test_can_create_open_url_action_with_a_field_reference(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Slug")
    button = data_fixture.create_button_field(table=table)

    response = api_client.post(
        reverse("api:database:workflow_actions:list", kwargs={"field_id": button.id}),
        {"type": "open_url"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    action_id = response.json()["id"]

    response = api_client.patch(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": action_id},
        ),
        {
            "url": {
                # `fields.field_<id>` is the reference form the migration
                # writes and the frontend data provider resolves.
                "formula": (
                    f"concat('https://x.test/', get('fields.field_{text_field.id}'))"
                ),
                "mode": "simple",
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    # The response is built from the persisted object, so the exact string
    # coming back proves the formula survived validation and storage intact.
    assert response.json()["url"]["formula"] == (
        f"concat('https://x.test/', get('fields.field_{text_field.id}'))"
    )
    assert response.json()["url"]["mode"] == "simple"


@pytest.mark.django_db
def test_order_with_an_action_from_another_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    other_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    foreign = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=other_field
    )

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:order",
            kwargs={"field_id": button_field.id},
        ),
        {"workflow_action_ids": [foreign.id, action.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_WORKFLOW_ACTION_NOT_IN_FIELD"
