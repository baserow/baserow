from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST

from baserow.contrib.database.rows.handler import RowHandler
from baserow.test_utils.helpers import is_dict_subset


@pytest.mark.field_multiple_collaborators
@pytest.mark.django_db
def test_multiple_collaborators_field_type_create(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Collaborator 1",
            "type": "multiple_collaborators",
            "notify_user_when_added": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Collaborator 1"
    assert response_json["type"] == "multiple_collaborators"
    assert response_json["notify_user_when_added"] is False
    assert response_json["available_collaborators"] == [
        {"id": user.id, "name": user.first_name}
    ]


@pytest.mark.field_multiple_collaborators
@pytest.mark.django_db
def test_multiple_collaborators_field_type_update(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user_2 = data_fixture.create_user(workspace=workspace, first_name="Test2")
    database = data_fixture.create_database_application(
        user=user, name="Placeholder", workspace=workspace
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": collaborator_field.id}),
        {"name": "New collaborator 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "New collaborator 1"
    assert response_json["type"] == "multiple_collaborators"
    assert response_json["available_collaborators"] == [
        {"id": user.id, "name": user.first_name},
        {"id": user_2.id, "name": user_2.first_name},
    ]


@pytest.mark.field_multiple_collaborators
@pytest.mark.django_db
def test_multiple_collaborators_field_type_delete(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": collaborator_field.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    collaborator_field.refresh_from_db()
    assert collaborator_field.trashed is True


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_insert_row_validation(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    user2 = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )

    # not a list

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{collaborator_field.id}": "Nothing"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"][f"field_{collaborator_field.id}"]["non_field_errors"][
            0
        ]["code"]
        == "not_a_list"
    )

    # wrong user id

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{collaborator_field.id}": [{"id": 999999}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "The provided user id [999999] is not a valid collaborator."
    )

    # user not in workspace

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{collaborator_field.id}": [{"id": user2.id}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == f"The provided user id [{user2.id}] is not a valid collaborator."
    )


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_insert_row(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )

    # empty list

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{collaborator_field.id}": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert is_dict_subset({f"field_{collaborator_field.id}": []}, response.json())

    # list

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{collaborator_field.id}": [{"id": user2.id}, {"id": user3.id}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            f"field_{collaborator_field.id}": [
                {"id": user2.id, "name": user2.first_name},
                {"id": user3.id, "name": user3.first_name},
            ]
        },
        response.json(),
    )


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_update_row_validation(
    api_client, data_fixture
):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user()
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )
    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )

    # not a list

    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        {f"field_{collaborator_field.id}": 43},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"][f"field_{collaborator_field.id}"]["non_field_errors"][
            0
        ]["code"]
        == "not_a_list"
    )

    # wrong user id

    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        {f"field_{collaborator_field.id}": [{"id": 999999}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "The provided user id [999999] is not a valid collaborator."
    )

    # user not in workspace

    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        {f"field_{collaborator_field.id}": [{"id": user2.id}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == f"The provided user id [{user2.id}] is not a valid collaborator."
    )


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_update_row(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )
    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )

    # list

    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        {f"field_{collaborator_field.id}": [{"id": user2.id}, {"id": user3.id}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    # Django does not guarantee the ordering of model_instance.m2m_field = [
    # id2, id3]
    assert {val["id"] for val in response_json[f"field_{collaborator_field.id}"]} == {
        user2.id,
        user3.id,
    }

    # empty list

    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        {f"field_{collaborator_field.id}": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert is_dict_subset({f"field_{collaborator_field.id}": []}, response.json())


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_delete_row(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )
    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )

    response = api_client.delete(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    model = table.get_model()
    assert model.objects.count() == 0


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_batch_insert_rows_validation(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    user2 = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )

    # not a list

    response = api_client.post(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {f"field_{collaborator_field.id}": user.id},
                {f"field_{collaborator_field.id}": "Nothing"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["items"]["0"][f"field_{collaborator_field.id}"][
            "non_field_errors"
        ][0]["code"]
        == "not_a_list"
    )
    assert (
        response_json["detail"]["items"]["1"][f"field_{collaborator_field.id}"][
            "non_field_errors"
        ][0]["code"]
        == "not_a_list"
    )

    # wrong user id

    response = api_client.post(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {f"field_{collaborator_field.id}": [{"id": user.id}]},
                {f"field_{collaborator_field.id}": [{"id": 999999}]},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "The provided user id [999999] is not a valid collaborator."
    )

    # user not in workspace

    response = api_client.post(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {f"field_{collaborator_field.id}": [{"id": user2.id}]},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == f"The provided user id [{user2.id}] is not a valid collaborator."
    )


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_batch_insert_rows(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )

    # empty list

    response = api_client.post(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {f"field_{collaborator_field.id}": []},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {f"field_{collaborator_field.id}": []}, response.json()["items"][0]
    )

    # list

    response = api_client.post(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {
                    f"field_{collaborator_field.id}": [
                        {"id": user2.id},
                        {"id": user3.id},
                    ]
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # assert response.json() == {}
    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            "items": [
                {
                    f"field_{collaborator_field.id}": [
                        {"id": user2.id, "name": user2.first_name},
                        {"id": user3.id, "name": user3.first_name},
                    ]
                }
            ]
        },
        response.json(),
    )


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_batch_update_rows_validation(
    api_client, data_fixture
):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user()
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )
    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )
    row2 = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )

    # not a list

    response = api_client.patch(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {
                    "id": row.id,
                    f"field_{collaborator_field.id}": 43,
                },
                {
                    "id": row2.id,
                    f"field_{collaborator_field.id}": None,
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["items"]["0"][f"field_{collaborator_field.id}"][
            "non_field_errors"
        ][0]["code"]
        == "not_a_list"
    )
    assert (
        response_json["detail"]["items"]["1"][f"field_{collaborator_field.id}"][0][
            "code"
        ]
        == "null"
    )

    # wrong user id

    response = api_client.patch(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {
                    "id": row.id,
                    f"field_{collaborator_field.id}": [{"id": 999999}],
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "The provided user id [999999] is not a valid collaborator."
    )

    # user not in workspace

    response = api_client.patch(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {
                    "id": row.id,
                    f"field_{collaborator_field.id}": [{"id": user2.id}],
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == f"The provided user id [{user2.id}] is not a valid collaborator."
    )


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_batch_update_rows(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )
    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )
    row2 = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )

    # list

    response = api_client.patch(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {
                    "id": row.id,
                    f"field_{collaborator_field.id}": [
                        {"id": user2.id},
                        {"id": user3.id},
                    ],
                },
                {"id": row2.id, f"field_{collaborator_field.id}": [{"id": user3.id}]},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert (
        response_json["items"][0][f"field_{collaborator_field.id}"][0]["id"] == user2.id
    )
    assert (
        response_json["items"][0][f"field_{collaborator_field.id}"][1]["id"] == user3.id
    )
    assert (
        response_json["items"][1][f"field_{collaborator_field.id}"][0]["id"] == user3.id
    )

    # empty list

    response = api_client.patch(
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}),
        {
            "items": [
                {
                    "id": row.id,
                    f"field_{collaborator_field.id}": [],
                },
                {
                    "id": row2.id,
                    f"field_{collaborator_field.id}": [],
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            "items": [
                {f"field_{collaborator_field.id}": []},
                {f"field_{collaborator_field.id}": []},
            ]
        },
        response.json(),
    )


@pytest.mark.field_multiple_collaborators
@pytest.mark.api_rows
@pytest.mark.django_db
def test_multiple_collaborators_field_type_batch_delete_rows(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )
    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )
    row2 = row_handler.create_row(
        user=user, table=table, values={collaborator_field.id: [{"id": user.id}]}
    )

    response = api_client.post(
        reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id}),
        {"items": [row.id, row2.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    model = table.get_model()
    assert model.objects.count() == 0
