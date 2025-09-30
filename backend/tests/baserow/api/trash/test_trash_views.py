from datetime import datetime, timedelta, timezone

from django.shortcuts import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.models import Application, TrashEntry, Workspace
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import AnyStr


@pytest.mark.django_db
def test_deleting_a_workspace_moves_it_to_the_trash_and_hides_it(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace_to_delete = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    token = data_fixture.generate_token(user)
    response = api_client.get(
        reverse("api:workspaces:list"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == []

    response = api_client.get(
        reverse(
            "api:trash:contents",
            kwargs={
                "workspace_id": workspace_to_delete.id,
            },
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "application": None,
                "workspace": workspace_to_delete.id,
                "id": TrashEntry.objects.first().id,
                "parent_trash_item_id": None,
                "trash_item_id": workspace_to_delete.id,
                "trash_item_type": "workspace",
                "trashed_at": "2020-01-01T12:00:00Z",
                "user_who_trashed": user.first_name,
                "name": workspace_to_delete.name,
                "parent_name": None,
                "names": None,
            }
        ],
    }


@pytest.mark.django_db
def test_can_restore_a_deleted_trash_item(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace_to_delete = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_204_NO_CONTENT

    token = data_fixture.generate_token(user)
    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "workspace",
            "trash_item_id": workspace_to_delete.id,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT

    assert Workspace.objects.count() == 1
    assert Workspace.trash.count() == 0

    response = api_client.get(
        reverse(
            "api:trash:contents",
            kwargs={
                "workspace_id": workspace_to_delete.id,
            },
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db
def test_cant_restore_a_deleted_trash_item_if_not_in_workspace(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    other_user, other_token = data_fixture.create_user_and_token()
    workspace_to_delete = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "workspace",
            "trash_item_id": workspace_to_delete.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_cant_restore_a_non_existent_trashed_item(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "workspace",
            "trash_item_id": 99999,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TRASH_ITEM_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_cant_restore_a_trashed_item_with_a_missing_parent(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = data_fixture.create_database_table(user=user, database=application)
    model = table.get_model()
    row = model.objects.create()

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_204_NO_CONTENT

    token = data_fixture.generate_token(user)
    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "row",
            "parent_trash_item_id": 99999,
            "trash_item_id": row.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TRASH_ITEM_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_cant_restore_a_trash_item_marked_for_perm_deletion(
    api_client, data_fixture, settings
):
    user, token = data_fixture.create_user_and_token()
    workspace_to_delete = data_fixture.create_workspace(user=user)

    trashed_at = datetime.now(tz=timezone.utc)
    time_when_trash_item_old_enough = trashed_at + timedelta(
        hours=settings.HOURS_UNTIL_TRASH_PERMANENTLY_DELETED + 1
    )

    with freeze_time(trashed_at):
        url = reverse(
            "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
        )
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    with freeze_time(time_when_trash_item_old_enough):
        TrashHandler.mark_old_trash_for_permanent_deletion()
        TrashHandler.permanently_delete_marked_trash()

    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "workspace",
            "trash_item_id": workspace_to_delete.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TRASH_ITEM_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_can_get_trash_structure(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace_to_delete = data_fixture.create_workspace()
    normal_workspace = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        user=user, workspace=workspace_to_delete, order=1
    )
    data_fixture.create_user_workspace(user=user, workspace=normal_workspace, order=2)
    # Another workspace for a different user which should not be displayed below
    data_fixture.create_workspace()
    application = data_fixture.create_database_application(
        user=user, workspace=workspace_to_delete
    )
    trashed_application = data_fixture.create_database_application(
        user=user, workspace=normal_workspace
    )

    url = reverse(
        "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse(
        "api:applications:item", kwargs={"application_id": trashed_application.id}
    )
    with freeze_time("2020-01-01 12:00"):
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_204_NO_CONTENT

    token = data_fixture.generate_token(user)
    response = api_client.get(
        reverse(
            "api:trash:list",
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "workspaces": [
            {
                "id": workspace_to_delete.id,
                "trashed": True,
                "name": workspace_to_delete.name,
                "applications": [
                    {
                        "id": application.id,
                        "name": application.name,
                        "trashed": False,
                        "type": "database",
                    }
                ],
            },
            {
                "id": normal_workspace.id,
                "trashed": False,
                "name": normal_workspace.name,
                "applications": [
                    {
                        "id": trashed_application.id,
                        "name": trashed_application.name,
                        "trashed": True,
                        "type": "database",
                    }
                ],
            },
        ],
    }


@pytest.mark.django_db
def test_getting_a_non_existent_workspace_returns_404(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse(
            "api:trash:contents",
            kwargs={"workspace_id": 99999},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_getting_a_non_existent_app_returns_404(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:trash:contents",
        kwargs={"workspace_id": workspace.id},
    )
    response = api_client.get(
        f"{url}?application_id=99999",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_getting_a_app_for_diff_workspace_returns_400(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)

    app = data_fixture.create_database_application(user=user, workspace=other_workspace)

    url = reverse(
        "api:trash:contents",
        kwargs={"workspace_id": workspace.id},
    )
    response = api_client.get(
        f"{url}?application_id={app.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_APPLICATION_NOT_IN_GROUP"


@pytest.mark.django_db
def test_user_cant_get_trash_contents_for_workspace_they_are_not_a_member_of(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    (
        other_unpermissioned_user,
        unpermissioned_token,
    ) = data_fixture.create_user_and_token()

    workspace_to_delete = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse(
        "api:trash:contents",
        kwargs={
            "workspace_id": workspace_to_delete.id,
        },
    )

    token = data_fixture.generate_token(user)
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {unpermissioned_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_can_get_trash_contents_for_undeleted_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    workspace = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:trash:contents",
        kwargs={
            "workspace_id": workspace.id,
        },
    )
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db
def test_can_get_trash_contents_for_undeleted_app(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    workspace = data_fixture.create_workspace(user=user)
    app = data_fixture.create_database_application(user=user, workspace=workspace)

    url = reverse(
        "api:trash:contents",
        kwargs={
            "workspace_id": workspace.id,
        },
    )
    response = api_client.get(
        f"{url}?application_id={app.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db
def test_emptying_a_trashed_workspace_marks_it_for_perm_deletion(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace_to_delete = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse(
        "api:trash:contents",
        kwargs={
            "workspace_id": workspace_to_delete.id,
        },
    )
    token = data_fixture.generate_token(user)
    response = api_client.delete(
        f"{url}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT

    assert Workspace.objects.count() == 0
    assert Workspace.trash.count() == 1
    assert TrashEntry.objects.get(
        trash_item_id=workspace_to_delete.id
    ).should_be_permanently_deleted

    response = api_client.get(
        reverse(
            "api:trash:contents",
            kwargs={
                "workspace_id": workspace_to_delete.id,
            },
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_emptying_a_non_existent_workspace_returns_404(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.delete(
        reverse(
            "api:trash:contents",
            kwargs={"workspace_id": 99999},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_emptying_a_non_existent_app_returns_404(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:trash:contents",
        kwargs={"workspace_id": workspace.id},
    )
    response = api_client.delete(
        f"{url}?application_id=99999",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_emptying_a_app_for_diff_workspace_returns_400(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)

    app = data_fixture.create_database_application(user=user, workspace=other_workspace)

    url = reverse(
        "api:trash:contents",
        kwargs={"workspace_id": workspace.id},
    )
    response = api_client.delete(
        f"{url}?application_id={app.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_APPLICATION_NOT_IN_GROUP"


@pytest.mark.django_db
def test_user_cant_empty_trash_contents_for_workspace_they_are_not_a_member_of(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    (
        other_unpermissioned_user,
        unpermissioned_token,
    ) = data_fixture.create_user_and_token()

    workspace_to_delete = data_fixture.create_workspace(user=user)

    url = reverse(
        "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse(
        "api:trash:contents",
        kwargs={
            "workspace_id": workspace_to_delete.id,
        },
    )
    token = data_fixture.generate_token(user)
    response = api_client.delete(
        url,
        HTTP_AUTHORIZATION=f"JWT {unpermissioned_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_emptying_a_trashed_app_marks_it_for_perm_deletion(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    trashed_database = data_fixture.create_database_application(
        user=user, workspace=workspace
    )

    url = reverse(
        "api:applications:item", kwargs={"application_id": trashed_database.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse(
        "api:trash:contents",
        kwargs={
            "workspace_id": workspace.id,
        },
    )
    token = data_fixture.generate_token(user)
    response = api_client.delete(
        f"{url}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT

    assert Application.objects.count() == 0
    assert Application.trash.count() == 1
    assert TrashEntry.objects.get(
        trash_item_id=trashed_database.id
    ).should_be_permanently_deleted

    url = reverse(
        "api:trash:contents",
        kwargs={
            "workspace_id": workspace.id,
        },
    )
    response = api_client.get(
        f"{url}?application_id={trashed_database.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_deleting_a_user_who_trashed_something_returns_null_user_who_trashed(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    other_user, other_token = data_fixture.create_user_and_token()
    workspace_to_delete = data_fixture.create_workspace(user=user)
    data_fixture.create_user_workspace(user=other_user, workspace=workspace_to_delete)

    url = reverse(
        "api:workspaces:item", kwargs={"workspace_id": workspace_to_delete.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    user.delete()

    token = data_fixture.generate_token(other_user)
    response = api_client.get(
        reverse(
            "api:trash:contents",
            kwargs={
                "workspace_id": workspace_to_delete.id,
            },
        ),
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "application": None,
                "workspace": workspace_to_delete.id,
                "id": TrashEntry.objects.first().id,
                "parent_trash_item_id": None,
                "trash_item_id": workspace_to_delete.id,
                "trash_item_type": "workspace",
                "trashed_at": "2020-01-01T12:00:00Z",
                "user_who_trashed": None,
                "name": workspace_to_delete.name,
                "parent_name": None,
                "names": None,
            }
        ],
    }


@pytest.mark.django_db
def test_restoring_an_item_which_doesnt_need_parent_id_with_one_returns_error(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(
        user=user, workspace=workspace
    )

    url = reverse("api:applications:item", kwargs={"application_id": application.id})
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    token = data_fixture.generate_token(user)
    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "application",
            "parent_trash_item_id": 99999,
            "trash_item_id": application.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PARENT_ID_MUST_NOT_BE_PROVIDED"


@pytest.mark.django_db
def test_cant_restore_a_trashed_item_requiring_a_parent_id_without_providing_it(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = data_fixture.create_database_table(user=user, database=application)
    model = table.get_model()
    row = model.objects.create()

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
    )
    with freeze_time("2020-01-01 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    token = data_fixture.generate_token(user)
    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "row",
            "trash_item_id": row.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PARENT_ID_MUST_BE_PROVIDED"


@pytest.mark.django_db
def test_cant_delete_same_item_twice(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(user=user)
    row_table, _, rows = data_fixture.build_table(
        user=user, columns=[("text", "text")], rows=["test"]
    )
    row = rows[0]

    def get_token():
        return data_fixture.generate_token(user)

    url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace.id})
    _assert_delete_called_twice_returns_correct_api_error(
        api_client, workspace, get_token, url
    )

    url = reverse("api:applications:item", kwargs={"application_id": database.id})
    _assert_delete_called_twice_returns_correct_api_error(
        api_client, database, get_token, url
    )
    url = reverse("api:database:tables:item", kwargs={"table_id": table.id})
    _assert_delete_called_twice_returns_correct_api_error(
        api_client, table, get_token, url
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": field.id})
    _assert_delete_called_twice_returns_correct_api_error(
        api_client, field, get_token, url, response_code=HTTP_200_OK
    )

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": row_table.id, "row_id": row.id}
    )
    _assert_delete_called_twice_returns_correct_api_error(
        api_client, row, get_token, url
    )


def _assert_delete_called_twice_returns_correct_api_error(
    api_client, deletable_item, get_token, url, response_code=HTTP_204_NO_CONTENT
):
    with freeze_time("2020-01-01 12:00"):
        token = get_token()
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == response_code
    # Fake two requests doing the deletion at once by manually unsetting the trashed
    # flag so we can attempt to trash again and hit the integrity error.
    deletable_item.trashed = False
    deletable_item.save()
    with freeze_time("2020-01-01 12:00"):
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM"


@pytest.mark.django_db
def test_restoring_a_field_which_depends_on_trashed_table_fails(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table_1 = data_fixture.create_database_table(name="Table 1", database=database)
    table_2 = data_fixture.create_database_table(name="Table 2", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    table_1_primary_field = field_handler.create_field(
        user=user, table=table_1, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=table_1,
        values={f"field_{table_1_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=table_1,
        values={f"field_{table_1_primary_field.id}": "Jane"},
    )

    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=table_2, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user, table=table_2, values={f"field_{cars_primary_field.id}": "BMW"}
    )
    row_handler.create_row(
        user=user, table=table_2, values={f"field_{cars_primary_field.id}": "Audi"}
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table_1,
        type_name="link_row",
        name="Customer",
        link_row_table=table_2,
    )
    TrashHandler.trash(user, database.workspace, database, link_field_1)
    TrashHandler.trash(user, database.workspace, database, table_1)
    TrashHandler.trash(user, database.workspace, database, table_2)
    TrashHandler.restore_item(user, "table", table_1.id)

    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "field",
            "trash_item_id": link_field_1.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANT_RESTORE_AS_RELATED_TABLE_TRASHED"


@pytest.mark.django_db
def test_restoring_managed_trash_entry_disallowed(
    api_client, data_fixture, stub_trash_operation_type
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    model = table.get_model()
    row = model.objects.create()

    with stub_trash_operation_type(type_managed=True) as operation_type:
        trash_entry = TrashHandler.trash(
            user,
            workspace,
            database,
            row,
            trash_operation_type=operation_type.type,
        )
        assert trash_entry.managed
        assert trash_entry.trash_operation_type == operation_type.type

    response = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "row",
            "trash_item_id": row.id,
            "parent_trash_item_id": table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_TRASH_ITEM_DISALLOWED",
        "detail": "This trash entry is managed internally "
        "and cannot be restored manually.",
    }


@pytest.mark.django_db
def test_managed_trash_entries_excluded_from_contents(
    api_client, data_fixture, stub_trash_operation_type
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    model = table.get_model()
    managed_row = model.objects.create()
    with stub_trash_operation_type(type_managed=True) as operation_type:
        managed_trash_entry = TrashHandler.trash(
            user,
            workspace,
            database,
            managed_row,
            trash_operation_type=operation_type.type,
        )
        assert managed_trash_entry.managed
        assert managed_trash_entry.trash_operation_type == operation_type.type

    unmanaged_row = model.objects.create()
    unmanaged_trash_entry = TrashHandler.trash(user, workspace, database, unmanaged_row)
    assert not unmanaged_trash_entry.managed

    response = api_client.get(
        reverse(
            "api:trash:contents",
            kwargs={
                "workspace_id": workspace.id,
            },
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": unmanaged_trash_entry.id,
                "user_who_trashed": user.get_full_name(),
                "trash_item_type": "row",
                "trash_item_id": unmanaged_row.id,
                "parent_trash_item_id": table.id,
                "trashed_at": AnyStr(),
                "application": database.id,
                "workspace": workspace.id,
                "name": AnyStr(),
                "names": [AnyStr()],
                "parent_name": AnyStr(),
            }
        ],
    }
