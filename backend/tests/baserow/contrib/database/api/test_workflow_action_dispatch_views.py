from unittest.mock import patch

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
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.workflow_action_types import (
    DatabaseWorkflowServiceActionType,
)


def _button_with_create_action(data_fixture, user, value="Ada"):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
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
def test_dispatch_returns_client_actions_for_open_url(api_client, data_fixture):
    """`client_actions` is the contract the frontend reads to run frontend-only
    actions itself: the key name, that it is a list, and that each entry carries
    `type`, `url` and `target`."""

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )
    open_url = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    open_url.url = "'https://example.com'"
    open_url.target = "blank"
    open_url.save()

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
    # The create_row action still ran server side and is unaffected.
    assert len(response.json()["results"]) == 1
    client_actions = response.json()["client_actions"]
    assert len(client_actions) == 1
    assert client_actions[0]["type"] == "open_url"
    assert client_actions[0]["url"]["formula"] == "'https://example.com'"
    assert client_actions[0]["target"] == "blank"


@pytest.mark.django_db
def test_dispatch_acts_as_the_clicker_after_an_integration_was_offered(
    api_client, data_fixture
):
    """The other half of the integration guard: even after a request tried to
    attach one, the click still runs as the person who clicked."""

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )
    impersonated = data_fixture.create_user()
    # A member of the same workspace, so a click that ran as them would succeed
    # and be attributed to them rather than failing on a permission check.
    data_fixture.create_user_workspace(
        workspace=table.database.workspace, user=impersonated
    )
    integration = data_fixture.create_local_baserow_integration(
        user=impersonated, authorized_user=impersonated
    )

    update = api_client.patch(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": action.id},
        ),
        {
            "type": "local_baserow_create_row",
            "service": {
                "type": "local_baserow_upsert_row",
                "table_id": table.id,
                "integration_id": integration.id,
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert update.status_code == HTTP_200_OK, update.json()

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
    created = table.get_model().objects.exclude(id=row.id).get()
    assert created.created_by_id == user.id


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


@pytest.mark.django_db
def test_a_database_token_cannot_dispatch(api_client, data_fixture):
    """A database token never authenticates here, so the actions of a button
    can't be run by something that has no user behind it."""

    user = data_fixture.create_user()
    table, _, button_field, row, _ = _button_with_create_action(data_fixture, user)
    token = data_fixture.create_token(user=user, workspace=table.database.workspace)

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": row.id},
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert table.get_model().objects.exclude(id=row.id).count() == 0


@pytest.mark.django_db
def test_a_failed_action_returns_the_dispatch_error(api_client, data_fixture):
    """ADR 006 section 3: the clicker is told which action failed and why,
    rather than getting an opaque 500."""

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )
    # A delete-row action with no table configured fails at dispatch.
    broken = data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
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

    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    assert response.json()["error"] == "ERROR_WORKFLOW_ACTION_DISPATCH_FAILED"
    # Named by its place in the list, which the clicker can count in the editor.
    assert response.json()["detail"] == "Action 2 failed: No table selected"
    # The action before the broken one already ran, and stays (ADR 006 section 3).
    created = table.get_model().objects.exclude(id=row.id).get()
    assert getattr(created, f"field_{name_field.id}") == "Ada"


@pytest.mark.django_db
def test_a_failed_action_stops_the_client_actions(api_client, data_fixture):
    """`client_actions` never reaches the browser when an action failed, so a
    failed click leaves the user on the error rather than navigating away."""

    user, token = data_fixture.create_user_and_token()
    _, _, button_field, row, _ = _button_with_create_action(data_fixture, user)
    data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )
    open_url = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    open_url.url = "'https://example.com'"
    open_url.save()

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
    assert response.json()["error"] == "ERROR_WORKFLOW_ACTION_DISPATCH_FAILED"
    assert "client_actions" not in response.json()


@pytest.mark.django_db
def test_a_result_names_the_fields_it_returned(api_client, data_fixture):
    """The result is keyed by field name, so the browser needs the ids to
    resolve a `previous_action.<id>.field_<id>` path in an `open_url`."""

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )
    # Only a client action reads a result, so only then are the names built.
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"formula": "'https://example.com'", "mode": "simple"},
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
    (result,) = response.json()["results"]
    assert result["workflow_action_id"] == action.id
    assert result["field_names"][f"field_{name_field.id}"] == "Name"
    assert result["data"]["Name"] == "Ada"


@pytest.mark.django_db
def test_an_action_returning_no_row_names_no_fields(api_client, data_fixture):
    """A delete produces no row, so there is nothing for the browser to resolve
    a name against and no reason to build a table model for it."""

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )
    target = table.get_model().objects.create()
    delete_action = data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )
    service = delete_action.service.specific
    service.table = table
    service.row_id = str(target.id)
    service.save()
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"formula": "'https://example.com'", "mode": "simple"},
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
    results = {r["workflow_action_id"]: r for r in response.json()["results"]}
    # The create still names its fields; the delete has none to name.
    assert results[action.id]["field_names"] != {}
    assert results[delete_action.id]["field_names"] == {}


@pytest.mark.django_db
def test_no_client_action_means_no_field_names(api_client, data_fixture):
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

    (result,) = response.json()["results"]
    assert result["field_names"] == {}


@pytest.mark.django_db
def test_two_actions_on_one_table_name_its_fields_once(api_client, data_fixture):
    """Naming the fields builds the table model, so a second action against the
    same table must not build it again."""

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )
    second = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = second.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value="'Grace'", enabled=True)
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"formula": "'https://example.com'", "mode": "simple"},
    )

    with patch(
        "baserow.contrib.database.workflow_actions.workflow_action_types"
        ".DatabaseWorkflowServiceActionType.get_result_field_names",
        wraps=DatabaseWorkflowServiceActionType.get_result_field_names,
        autospec=True,
    ) as names:
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
    assert len(results) == 2
    # Both results are named, from the one lookup.
    assert all(r["field_names"][f"field_{name_field.id}"] == "Name" for r in results)
    assert names.call_count == 1
