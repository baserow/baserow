from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.action.scopes import ViewActionScopeType
from baserow.core.action.handler import ActionHandler


@pytest.mark.django_db
def test_copy_view_configuration(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(
        table=table,
        filter_type="OR",
        row_height_size="large",
        frozen_column_count=2,
    )
    dest_view = data_fixture.create_grid_view(table=table)

    filter_group = data_fixture.create_view_filter_group(view=source_view)
    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a", group=filter_group
    )
    data_fixture.create_view_sort(view=source_view, field=field, order="DESC")
    data_fixture.create_view_group_by(view=source_view, field=field)
    data_fixture.create_view_decoration(view=source_view)

    response = api_client.post(
        reverse(
            "api:database:views:copy_configuration",
            kwargs={"view_id": dest_view.id},
        ),
        {
            "source_view_id": source_view.id,
            "categories": [
                "filters",
                "sorts",
                "group_bys",
                "decorations",
                "view_settings",
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == dest_view.id
    assert response_json["filter_type"] == "OR"
    assert response_json["row_height_size"] == "large"
    assert response_json["frozen_column_count"] == 2
    assert len(response_json["filters"]) == 1
    assert response_json["filters"][0]["value"] == "a"
    assert len(response_json["filter_groups"]) == 1
    assert (
        response_json["filters"][0]["group"] == response_json["filter_groups"][0]["id"]
    )
    assert len(response_json["sortings"]) == 1
    assert len(response_json["group_bys"]) == 1
    assert len(response_json["decorations"]) == 1


@pytest.mark.django_db
def test_copy_view_configuration_errors(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    other_user, other_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    other_table = data_fixture.create_database_table(user=user)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)
    gallery_view = data_fixture.create_gallery_view(table=table)
    other_table_view = data_fixture.create_grid_view(table=other_table)

    def post(view_id, body, token_to_use=None):
        return api_client.post(
            reverse(
                "api:database:views:copy_configuration", kwargs={"view_id": view_id}
            ),
            body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_to_use or token}",
        )

    response = post(9999, {"source_view_id": source_view.id, "categories": ["filters"]})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    response = post(dest_view.id, {"source_view_id": 9999, "categories": ["filters"]})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    response = post(dest_view.id, {"source_view_id": source_view.id, "categories": []})
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = post(
        dest_view.id, {"source_view_id": dest_view.id, "categories": ["filters"]}
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"] == "ERROR_CANNOT_COPY_VIEW_CONFIGURATION_TO_SAME_VIEW"
    )

    response = post(
        dest_view.id,
        {"source_view_id": other_table_view.id, "categories": ["filters"]},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_VIEW_NOT_IN_TABLE"

    response = post(
        gallery_view.id,
        {"source_view_id": source_view.id, "categories": ["view_settings"]},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"]
        == "ERROR_VIEW_CONFIGURATION_COPY_CATEGORY_NOT_SUPPORTED"
    )

    response = post(
        dest_view.id,
        {"source_view_id": source_view.id, "categories": ["unknown"]},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = post(
        dest_view.id,
        {"source_view_id": source_view.id, "categories": ["filters"]},
        token_to_use=other_token,
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_cannot_copy_configuration_from_another_users_personal_view(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_user_workspace(
        workspace=table.database.workspace, user=other_user
    )
    field = data_fixture.create_text_field(table=table)
    personal_view = data_fixture.create_grid_view(
        table=table, ownership_type="personal", owned_by=other_user
    )
    data_fixture.create_view_filter(
        view=personal_view, field=field, type="equal", value="secret"
    )
    dest_view = data_fixture.create_grid_view(table=table)

    response = api_client.post(
        reverse(
            "api:database:views:copy_configuration",
            kwargs={"view_id": dest_view.id},
        ),
        {"source_view_id": personal_view.id, "categories": ["filters"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"
    assert dest_view.viewfilter_set.count() == 0


@pytest.mark.django_db
def test_copy_view_configuration_is_a_single_undoable_action(api_client, data_fixture):
    session_id = "session-id"
    user, token = data_fixture.create_user_and_token(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)
    for value in ["a", "b", "c"]:
        data_fixture.create_view_filter(
            view=source_view, field=field, type="equal", value=value
        )

    response = api_client.post(
        reverse(
            "api:database:views:copy_configuration",
            kwargs={"view_id": dest_view.id},
        ),
        {"source_view_id": source_view.id, "categories": ["filters"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=session_id,
    )
    assert response.status_code == HTTP_200_OK
    assert dest_view.viewfilter_set.count() == 3

    undone_actions = ActionHandler.undo(
        user, [ViewActionScopeType.value(dest_view.id)], session_id
    )
    assert len(undone_actions) == 1
    assert dest_view.viewfilter_set.count() == 0
