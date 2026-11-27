import uuid

from django.contrib.auth import get_user_model
from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT

from baserow.api.actions.serializers import UndoRedoResultCodeField
from baserow.contrib.database.fields.models import NumberField, TextField
from baserow.core.action.models import Action
from baserow.core.actions import CreateWorkspaceActionType
from baserow.core.models import Application, Workspace
from baserow.test_utils.helpers import independent_test_db_connection

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_named_group_undo_crosses_scopes_and_replays_the_whole_group(
    api_client, data_fixture, settings
):
    settings.MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP = 1
    user, token = data_fixture.create_user_and_token()
    unrelated_workspace = data_fixture.create_workspace(user=user)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}", "HTTP_CLIENTSESSIONID": "sender"}
    group_id = uuid.uuid4()
    grouped = {**headers, "HTTP_CLIENTUNDOREDOACTIONGROUPID": str(group_id)}
    workspace = api_client.post(
        reverse("api:workspaces:list"), {"name": "Projects"}, format="json", **grouped
    ).json()

    def create_app(workspace_id, headers):
        return api_client.post(
            reverse("api:applications:list", kwargs={"workspace_id": workspace_id}),
            {"type": "database", "name": "Tasks"},
            format="json",
            **headers,
        ).json()["id"]

    database_id = create_app(workspace["id"], grouped)
    unrelated_id = create_app(unrelated_workspace.id, headers)
    url = reverse("api:user:undo_group", args=[group_id])
    for wrong_headers in [
        {**headers, "HTTP_CLIENTSESSIONID": "other"},
        {
            **headers,
            "HTTP_AUTHORIZATION": f"JWT {data_fixture.create_user_and_token()[1]}",
        },
    ]:
        assert (
            api_client.patch(url, **wrong_headers).json()["result_code"]
            == UndoRedoResultCodeField.NOTHING_TO_DO
        )
    assert Application.objects.filter(id=database_id).exists()
    result = api_client.patch(
        url, {"scopes": {"workspace": unrelated_workspace.id}}, format="json", **headers
    ).json()
    assert result["result_code"] == UndoRedoResultCodeField.SUCCESS
    assert len(result["actions"]) == 2
    assert not Workspace.objects.filter(pk=workspace["id"]).exists()
    assert not Application.objects.filter(pk=database_id).exists()
    assert Application.objects.filter(pk=unrelated_id).exists()
    assert (
        api_client.patch(url, **headers).json()["result_code"]
        == UndoRedoResultCodeField.NOTHING_TO_DO
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_response_undo_only_applies_to_the_latest_group(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}", "HTTP_CLIENTSESSIONID": "test"}
    group = uuid.uuid4()
    ids = []
    for group_id in (group, uuid.uuid4()):
        response = api_client.post(
            reverse("api:workspaces:list"),
            {"name": "Test"},
            format="json",
            HTTP_CLIENTUNDOREDOACTIONGROUPID=str(group_id),
            **headers,
        )
        ids.append(response.json()["id"])

    def undo(url):
        response = api_client.patch(
            url, {"scopes": {"root": True}}, format="json", **headers
        )
        assert response.status_code == 200
        return response.json()["result_code"]

    url = reverse("api:user:undo_group", args=[group])
    assert undo(url) == UndoRedoResultCodeField.NOTHING_TO_DO
    assert Workspace.objects.filter(id__in=ids).count() == 2
    assert undo(reverse("api:user:undo")) == UndoRedoResultCodeField.SUCCESS
    assert Workspace.objects.filter(id=ids[0]).exists()
    assert undo(url) == UndoRedoResultCodeField.SUCCESS
    assert not Workspace.objects.filter(id__in=ids).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_when_nothing_to_do_response_with_correct_code(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    response = api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID="test",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "actions": [],
        "result_code": UndoRedoResultCodeField.NOTHING_TO_DO,
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_without_session_id_returns_error(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    response = api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CLIENT_SESSION_ID_HEADER_NOT_SET"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_an_action_and_get_correct_response_code(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    same_session_id = "test"
    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    workspace_id = response.json()["id"]

    assert Workspace.objects.filter(id=workspace_id).exists()

    response = api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    assert not Workspace.objects.filter(id=workspace_id).exists()
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "actions": [
            {
                "action_scope": CreateWorkspaceActionType.scope(),
                "action_type": CreateWorkspaceActionType.type,
            }
        ],
        "result_code": UndoRedoResultCodeField.SUCCESS,
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_an_action_which_fails_returns_correct_result_code(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()

    same_session_id = "test"
    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    workspace_id = response.json()["id"]

    Workspace.objects.filter(id=workspace_id).delete()

    response = api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "actions": [
            {
                "action_scope": CreateWorkspaceActionType.scope(),
                "action_type": CreateWorkspaceActionType.type,
            }
        ],
        "result_code": UndoRedoResultCodeField.SKIPPED_DUE_TO_ERROR,
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_when_nothing_to_do_response_with_correct_code(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    response = api_client.patch(
        reverse("api:user:redo"),
        {"scopes": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID="test",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "actions": [],
        "result_code": UndoRedoResultCodeField.NOTHING_TO_DO,
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_without_session_id_returns_error(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    response = api_client.patch(
        reverse("api:user:redo"),
        {"scopes": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CLIENT_SESSION_ID_HEADER_NOT_SET"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_redo_an_action_and_get_correct_response_code(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    same_session_id = "test"
    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    workspace_id = response.json()["id"]

    assert Workspace.objects.filter(id=workspace_id).exists()

    api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    assert not Workspace.objects.filter(id=workspace_id).exists()

    response = api_client.patch(
        reverse("api:user:redo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    assert Workspace.objects.filter(id=workspace_id).exists()

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "actions": [
            {
                "action_scope": CreateWorkspaceActionType.scope(),
                "action_type": CreateWorkspaceActionType.type,
            }
        ],
        "result_code": UndoRedoResultCodeField.SUCCESS,
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_an_action_which_fails_returns_correct_result_code(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()

    same_session_id = "test"
    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    workspace_id = response.json()["id"]

    api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    Workspace.objects_and_trash.filter(id=workspace_id).delete()

    response = api_client.patch(
        reverse("api:user:redo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "actions": [
            {
                "action_scope": CreateWorkspaceActionType.scope(),
                "action_type": CreateWorkspaceActionType.type,
            }
        ],
        "result_code": UndoRedoResultCodeField.SKIPPED_DUE_TO_ERROR,
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_an_action_group_and_get_correct_response_code(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token()

    same_session_id = "test"
    same_action_group = str(uuid.uuid4())

    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
        HTTP_CLIENTUNDOREDOACTIONGROUPID=same_action_group,
    )
    assert response.status_code == HTTP_200_OK
    workspace1_id = response.json()["id"]

    assert Workspace.objects.filter(id=workspace1_id).exists()

    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 2"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
        HTTP_CLIENTUNDOREDOACTIONGROUPID=same_action_group,
    )
    assert response.status_code == HTTP_200_OK
    workspace2_id = response.json()["id"]

    assert Workspace.objects.filter(id=workspace2_id).exists()

    # the undo should delete both workspaces
    response = api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    assert not Workspace.objects.filter(id__in=[workspace1_id, workspace2_id]).exists()
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "actions": [
            {
                "action_scope": CreateWorkspaceActionType.scope(),
                "action_type": CreateWorkspaceActionType.type,
            },
            {
                "action_scope": CreateWorkspaceActionType.scope(),
                "action_type": CreateWorkspaceActionType.type,
            },
        ],
        "result_code": UndoRedoResultCodeField.SUCCESS,
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_redo_an_action_group_and_get_correct_response_code(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token()

    same_session_id = "test"
    same_action_group_id = str(uuid.uuid4())

    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
        HTTP_CLIENTUNDOREDOACTIONGROUPID=same_action_group_id,
    )
    assert response.status_code == HTTP_200_OK
    workspace1_id = response.json()["id"]

    assert Workspace.objects.filter(id=workspace1_id).exists()

    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 2"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
        HTTP_CLIENTUNDOREDOACTIONGROUPID=same_action_group_id,
    )
    assert response.status_code == HTTP_200_OK
    workspace2_id = response.json()["id"]

    assert Workspace.objects.filter(id=workspace2_id).exists()

    api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    assert Workspace.objects.count() == 0

    # the redo should recreate both workspaces
    response = api_client.patch(
        reverse("api:user:redo"),
        {"scopes": {"root": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )

    assert Workspace.objects.filter(id=workspace1_id).exists()
    assert Workspace.objects.filter(id=workspace2_id).exists()
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "actions": [
            {
                "action_scope": CreateWorkspaceActionType.scope(),
                "action_type": CreateWorkspaceActionType.type,
            },
            {
                "action_scope": CreateWorkspaceActionType.scope(),
                "action_type": CreateWorkspaceActionType.type,
            },
        ],
        "result_code": UndoRedoResultCodeField.SUCCESS,
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_invalid_undo_redo_action_group_header_raise_error(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    same_session_id = "test"
    action_group = "invalid_header_should_be_uuid4"

    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
        HTTP_CLIENTUNDOREDOACTIONGROUPID=action_group,
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == [
        "An invalid ClientUndoRedoActionGroupId header was provided. "
        "It must be a valid Version 4 UUID."
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_undoing_when_field_locked_fails_and_doesnt_skip(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(user, table=table)

    same_session_id = "test"

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {"name": "Test 1", "type": "number"},
        format="json",
        HTTP_CLIENTSESSIONID=same_session_id,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_field where id = {field.id} FOR KEY SHARE"
            )
            assert len(cursor.fetchall()) == 1
        response = api_client.patch(
            reverse("api:user:undo"),
            {"scopes": {"table": table.id}},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
            HTTP_CLIENTSESSIONID=same_session_id,
        )
    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_UNDO_REDO_LOCK_CONFLICT"

    assert NumberField.objects.filter(id=field.id).exists()
    assert not TextField.objects.filter(id=field.id).exists()
    assert not Action.objects.get().is_undone()


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_redoing_when_field_locked_fails_and_doesnt_skip(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(user, table=table)

    same_session_id = "test"

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {"name": "Test 1", "type": "number"},
        format="json",
        HTTP_CLIENTSESSIONID=same_session_id,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"table": table.id}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_field where id = {field.id} FOR KEY SHARE"
            )
            assert len(cursor.fetchall()) == 1
        response = api_client.patch(
            reverse("api:user:redo"),
            {"scopes": {"table": table.id}},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
            HTTP_CLIENTSESSIONID=same_session_id,
        )
    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_UNDO_REDO_LOCK_CONFLICT"

    assert not NumberField.objects.filter(id=field.id).exists()
    assert TextField.objects.filter(id=field.id).exists()
    assert Action.objects.get().is_undone()


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_undoing_field_delete_whilst_field_locked_works(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(user, table=table)

    same_session_id = "test"

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        format="json",
        HTTP_CLIENTSESSIONID=same_session_id,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_field where id = {field.id} FOR KEY SHARE"
            )
            assert len(cursor.fetchall()) == 1
        response = api_client.patch(
            reverse("api:user:undo"),
            {"scopes": {"table": table.id}},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
            HTTP_CLIENTSESSIONID=same_session_id,
        )

    assert TextField.objects.filter(id=field.id).exists()
    assert Action.objects.get().is_undone()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_application_action_undoable_from_all_workspaces_but_not_another_workspace(
    api_client, data_fixture
):
    session_id = str(uuid.uuid4())
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(
        workspace=workspace_1, name="Before"
    )

    def undo(scopes):
        response = api_client.patch(
            reverse("api:user:undo"),
            {"scopes": scopes},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
            HTTP_CLIENTSESSIONID=session_id,
        )
        assert response.status_code == HTTP_200_OK
        return response.json()["result_code"]

    def redo(scopes):
        response = api_client.patch(
            reverse("api:user:redo"),
            {"scopes": scopes},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
            HTTP_CLIENTSESSIONID=session_id,
        )
        assert response.status_code == HTTP_200_OK
        return response.json()["result_code"]

    # Renamed from the all workspaces homepage, which has no workspace selected.
    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": application.id}),
        {"name": "After"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=session_id,
    )
    assert response.status_code == HTTP_200_OK

    # Another workspace never sees it.
    assert (
        undo({"root": True, "workspace": workspace_2.id})
        == UndoRedoResultCodeField.NOTHING_TO_DO
    )
    # The homepage does.
    assert (
        undo({"root": True, "all_workspaces": True}) == UndoRedoResultCodeField.SUCCESS
    )
    application.refresh_from_db()
    assert application.name == "Before"
    assert (
        redo({"root": True, "all_workspaces": True}) == UndoRedoResultCodeField.SUCCESS
    )
    application.refresh_from_db()
    assert application.name == "After"
    # And so does its own workspace.
    assert (
        undo({"root": True, "workspace": workspace_1.id})
        == UndoRedoResultCodeField.SUCCESS
    )
    application.refresh_from_db()
    assert application.name == "Before"
