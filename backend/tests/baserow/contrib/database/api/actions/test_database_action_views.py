from django.contrib.auth import get_user_model
from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.models import TextField
from baserow.core.action.models import Action

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_a_database_action_and_get_correct_response_code(
    api_client, data_fixture
):
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

    api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"table": table.id, "application": table.database.id}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    assert response.status_code == HTTP_200_OK

    assert TextField.objects.filter(id=field.id).exists()
    assert Action.objects.get().is_undone()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_asking_for_an_unknown_scope_returns_an_error(api_client, data_fixture):
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

    response = api_client.patch(
        reverse("api:user:undo"),
        {
            "scopes": {
                "table": table.id,
                "application": table.database.id,
                "unknown_scope": True,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"] == {
        "scopes": {
            "non_field_errors": [
                {
                    "code": "invalid",
                    "error": "Your request body had the following unknown attributes: "
                    "unknown_scope. Please check the api documentation and only "
                    "provide valid fields.",
                }
            ]
        }
    }

    assert not TextField.objects.filter(id=field.id).exists()
    assert not Action.objects.get().is_undone()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_redo_table_renames_across_expanded_applications(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    headers = {"HTTP_CLIENTSESSIONID": "sidebar", "HTTP_AUTHORIZATION": f"JWT {token}"}
    tables = []
    for name in ("A", "B", "C"):
        database = data_fixture.create_database_application(workspace=workspace)
        table = data_fixture.create_database_table(database=database, name=name)
        response = api_client.patch(
            reverse("api:database:tables:item", kwargs={"table_id": table.id}),
            {"name": name + " renamed"},
            format="json",
            **headers,
        )
        assert response.status_code == HTTP_200_OK
        tables.append(table)

    a, b, c = tables
    scopes = {"application": a.database_id, "applications": [b.database_id]}
    for command, table, expected_name in (
        ("undo", b, "B"),
        ("undo", a, "A"),
        ("redo", a, "A renamed"),
        ("redo", b, "B renamed"),
    ):
        response = api_client.patch(
            reverse(f"api:user:{command}"), {"scopes": scopes}, format="json", **headers
        )
        assert response.status_code == HTTP_200_OK
        table.refresh_from_db()
        assert table.name == expected_name
    c.refresh_from_db()
    assert c.name == "C renamed"


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_undo_redo_import_from_another_database_in_the_sidebar(
    api_client, data_fixture, patch_filefield_storage
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    active_database = data_fixture.create_database_application(workspace=workspace)
    active_table = data_fixture.create_database_table(
        database=active_database, name="Original"
    )
    import_database = data_fixture.create_database_application(workspace=workspace)
    import_table = data_fixture.create_database_table(database=import_database)
    field = data_fixture.create_text_field(table=import_table)
    rows = import_table.get_model().objects
    rows.create(**{field.db_column: "existing"})
    headers = {"HTTP_CLIENTSESSIONID": "sidebar", "HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.patch(
        reverse("api:database:tables:item", kwargs={"table_id": active_table.id}),
        {"name": "Renamed"},
        format="json",
        **headers,
    )
    assert response.status_code == HTTP_200_OK
    with patch_filefield_storage():
        response = api_client.post(
            reverse(
                "api:database:tables:import_async", kwargs={"table_id": import_table.id}
            ),
            {"data": [["imported"]], "configuration": {"undo_in_application": True}},
            format="json",
            **headers,
        )
    assert response.status_code == HTTP_200_OK
    values = rows.order_by("id").values_list(field.db_column, flat=True)
    assert list(values) == ["existing", "imported"]

    scopes = {
        "table": active_table.id,
        "application": active_database.id,
        "applications": [import_database.id],
    }
    for command, expected_rows in (
        ("undo", ["existing"]),
        ("redo", ["existing", "imported"]),
    ):
        response = api_client.patch(
            reverse(f"api:user:{command}"), {"scopes": scopes}, format="json", **headers
        )
        assert response.status_code == HTTP_200_OK
        active_table.refresh_from_db()
        assert active_table.name == "Renamed"
        assert list(values.all()) == expected_rows
