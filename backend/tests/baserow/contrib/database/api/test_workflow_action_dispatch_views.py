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
    assert update.status_code == HTTP_400_BAD_REQUEST, update.json()

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
def test_a_result_carries_the_action_order(api_client, data_fixture):
    """A client action always runs last, so its own place in the list is the
    only thing that says which results it may read."""

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )
    client_action = data_fixture.create_database_workflow_action(
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
    body = response.json()
    (result,) = body["results"]
    assert result["order"] == action.order
    # Both sides of the comparison the browser makes are in the response.
    assert body["client_actions"][0]["order"] == client_action.order


@pytest.mark.django_db
def test_two_actions_on_one_table_are_both_named(api_client, data_fixture):
    """A client action resolves a `previous_action` path through these names,
    so every result that returned a row needs its own set."""

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
    assert all(r["field_names"][f"field_{name_field.id}"] == "Name" for r in results)


@pytest.mark.django_db
def test_a_reference_to_a_deleted_field_fails_the_click(api_client, data_fixture):
    """A path names a field as `field_<id>` and the service turns that into the
    field's name. A field the reference outlived has no name to be turned into,
    so a field named literally `field_<id>` must not answer for it."""

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    # An id no field of this table has, and a field named after it.
    missing_id = name_field.id + 1000
    alias_field = data_fixture.create_text_field(
        table=table, name=f"field_{missing_id}"
    )
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    first = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    first.service.specific.table = table
    first.service.specific.save()
    first.service.specific.field_mappings.create(
        field=alias_field, value="'aliased value'", enabled=True
    )

    second = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    second.service.specific.table = table
    second.service.specific.save()
    second.service.specific.field_mappings.create(
        field=name_field,
        value=f"get('previous_action.{first.id}.field_{missing_id}')",
        enabled=True,
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
    assert "Action 2 failed" in response.json()["detail"]
    # The chain stopped rather than copying the value of the field that shares
    # the deleted one's token.
    names = [
        getattr(created, f"field_{name_field.id}")
        for created in table.get_model().objects.exclude(id=row.id)
    ]
    assert "aliased value" not in names


@pytest.mark.django_db
def test_actions_sharing_an_order_are_told_apart_by_position(api_client, data_fixture):
    """Two actions created at once can be given the same `order`, which
    execution then breaks by id. The browser only lets a client action read
    what ran before it, so it needs the position rather than the order."""

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, action = _button_with_create_action(
        data_fixture, user
    )
    open_url = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    open_url.url = "'https://example.com'"
    open_url.save()
    # Both at the same order, with the client action second by id.
    button_field.workflow_actions.update(order=1)
    assert action.id < open_url.id

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
    body = response.json()
    # The orders are equal, so only the positions say which ran first.
    assert body["results"][0]["order"] == body["client_actions"][0]["order"]
    assert body["results"][0]["position"] == 1
    assert body["client_actions"][0]["position"] == 2


@pytest.mark.django_db
def test_a_result_no_client_action_can_read_is_not_sent(api_client, data_fixture):
    """
    Configuring a button needs more permission than clicking one, so the person
    who clicks may never have been allowed to see how it was set up. A result
    the browser has no client action to hand it to is therefore not sent at
    all: it carries whatever the action returned, and for a request that is the
    endpoint's reply and its response headers.
    """

    user, token = data_fixture.create_user_and_token()
    table, name_field, button_field, row, before = _button_with_create_action(
        data_fixture, user
    )
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"formula": "'https://example.com'", "mode": "simple"},
    )
    after = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = after.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value="'Grace'", enabled=True)

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
    # The open URL sits between them and can only read what ran before it.
    assert results[before.id]["data"]["Name"] == "Ada"
    assert results[after.id]["data"] is None
    assert results[after.id]["field_names"] == {}
    # Both still ran: it is only the answer that is withheld.
    assert table.get_model().objects.count() == 3
