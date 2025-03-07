from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewSort
from baserow.contrib.database.views.registries import view_type_registry


@pytest.mark.django_db
def test_list_view_sortings(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    field_1 = data_fixture.create_text_field(table=table_1)
    field_2 = data_fixture.create_text_field(table=table_1)
    field_3 = data_fixture.create_text_field(table=table_2)
    view_1 = data_fixture.create_grid_view(table=table_1, order=1)
    data_fixture.create_grid_view(table=table_1, order=2)
    view_3 = data_fixture.create_grid_view(table=table_2, order=1)
    sort_1 = data_fixture.create_view_sort(view=view_1, field=field_1)
    sort_2 = data_fixture.create_view_sort(view=view_1, field=field_2)
    data_fixture.create_view_sort(view=view_3, field=field_3)

    response = api_client.get(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_3.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:database:views:list_sortings", kwargs={"view_id": 999999}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert len(response_json) == 2
    assert response_json[0]["id"] == sort_1.id
    assert response_json[0]["view"] == view_1.id
    assert response_json[0]["field"] == field_1.id
    assert response_json[0]["order"] == sort_1.order
    assert response_json[0]["type"] == sort_1.type
    assert response_json[1]["id"] == sort_2.id

    response = api_client.delete(
        reverse(
            "api:workspaces:item",
            kwargs={"workspace_id": view_1.table.database.workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.get(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_view_sort(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    field_1 = data_fixture.create_text_field(table=table_1)
    field_2 = data_fixture.create_text_field(table=table_2)
    field_3 = data_fixture.create_text_field(table=table_1)
    field_4 = data_fixture.create_text_field(table=table_1)
    password_field = data_fixture.create_password_field(table=table_1)
    view_1 = data_fixture.create_grid_view(table=table_1)
    view_2 = data_fixture.create_grid_view(table=table_2)

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_2.id}),
        {
            "field": field_2.id,
            "order": "ASC",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": 99999}),
        {"field": field_1.id, "order": "ASC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {"field": 9999999, "order": "NOT_EXISTING"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["field"][0]["code"] == "does_not_exist"
    assert response_json["detail"]["order"][0]["code"] == "invalid_choice"

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {
            "field": field_2.id,
            "order": "ASC",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_NOT_IN_TABLE"

    grid_view_type = view_type_registry.get("grid")
    grid_view_type.can_sort = False
    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {"field": field_1.id, "order": "ASC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_SORT_NOT_SUPPORTED"
    grid_view_type.can_sort = True

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {"field": password_field.id, "order": "ASC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED"

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {"field": field_1.id, "order": "ASC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert ViewSort.objects.all().count() == 1
    first = ViewSort.objects.all().first()
    assert response_json["id"] == first.id
    assert response_json["view"] == view_1.id
    assert response_json["field"] == field_1.id
    assert response_json["order"] == "ASC"

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {"field": field_1.id, "order": "ASC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS"

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {"field": field_3.id, "order": "DESC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["order"] == "DESC"
    assert response_json["type"] == "default"

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {
            "field": field_4.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["order"] == "ASC"
    assert response_json["type"] == "default"

    assert ViewSort.objects.all().count() == 3


@pytest.mark.django_db
def test_create_view_sort_with_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(table=table_1)
    select_1 = data_fixture.create_single_select_field(table=table_1)
    view_1 = data_fixture.create_grid_view(table=table_1)

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {"field": field_1.id, "order": "ASC", "type": "unknown"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED"

    response = api_client.post(
        reverse("api:database:views:list_sortings", kwargs={"view_id": view_1.id}),
        {"field": select_1.id, "order": "DESC", "type": "order"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["order"] == "DESC"
    assert response_json["type"] == "order"


@pytest.mark.django_db
def test_get_view_sort(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    sort_1 = data_fixture.create_view_sort(user=user, order="DESC")
    sort_2 = data_fixture.create_view_sort()

    response = api_client.get(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_2.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": 99999}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_SORT_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert ViewSort.objects.all().count() == 2
    first = ViewSort.objects.get(pk=sort_1.id)
    assert response_json["id"] == first.id
    assert response_json["view"] == first.view_id
    assert response_json["field"] == first.field_id
    assert response_json["order"] == "DESC"
    assert response_json["type"] == "default"

    response = api_client.delete(
        reverse(
            "api:workspaces:item",
            kwargs={"workspace_id": sort_1.view.table.database.workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.get(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_SORT_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_view_sort(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    sort_1 = data_fixture.create_view_sort(user=user, order="DESC")
    sort_2 = data_fixture.create_view_sort()
    sort_3 = data_fixture.create_view_sort(view=sort_1.view, order="ASC")
    field_1 = data_fixture.create_text_field(table=sort_1.view.table)
    password_field = data_fixture.create_password_field(table=sort_1.view.table)
    field_2 = data_fixture.create_text_field()

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_2.id}),
        {"order": "ASC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": 9999}),
        {"order": "ASC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_SORT_DOES_NOT_EXIST"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        {
            "field": 9999999,
            "order": "EXISTING",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["field"][0]["code"] == "does_not_exist"
    assert response_json["detail"]["order"][0]["code"] == "invalid_choice"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        {"field": field_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_NOT_IN_TABLE"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        {"field": password_field.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_3.id}),
        {"field": sort_1.field_id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        {
            "field": field_1.id,
            "order": "ASC",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert ViewSort.objects.all().count() == 3
    first = ViewSort.objects.get(pk=sort_1.id)
    assert first.field_id == field_1.id
    assert first.order == "ASC"
    assert response_json["id"] == first.id
    assert response_json["view"] == first.view_id
    assert response_json["field"] == field_1.id
    assert response_json["order"] == "ASC"
    assert response_json["type"] == "default"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        {"order": "DESC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    first = ViewSort.objects.get(pk=sort_1.id)
    assert first.field_id == field_1.id
    assert first.order == "DESC"
    assert response_json["id"] == first.id
    assert response_json["view"] == first.view_id
    assert response_json["field"] == field_1.id
    assert response_json["order"] == "DESC"
    assert response_json["type"] == "default"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    first = ViewSort.objects.get(pk=sort_1.id)
    assert first.field_id == field_1.id
    assert first.order == "DESC"
    assert response_json["id"] == first.id
    assert response_json["view"] == first.view_id
    assert response_json["field"] == field_1.id
    assert response_json["order"] == "DESC"


@pytest.mark.django_db
def test_update_view_sort_with_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(table=table)
    select_2 = data_fixture.create_single_select_field(table=table)
    sort_1 = data_fixture.create_view_sort(user=user, order="DESC", field=field_1)
    sort_2 = data_fixture.create_view_sort(user=user, order="DESC", field=select_2)

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        {"field": field_1.id, "type": "unknown"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    print(response_json)
    assert response_json["error"] == "ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_2.id}),
        {
            "field": select_2.id,
            "order": "ASC",
            "type": "order",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["order"] == "ASC"
    assert response_json["type"] == "order"

    response = api_client.patch(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_2.id}),
        {
            "field": select_2.id,
            "order": "DESC",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["order"] == "DESC"
    assert response_json["type"] == "order"


@pytest.mark.django_db
def test_delete_view_sort(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    sort_1 = data_fixture.create_view_sort(user=user, order="DESC")
    sort_2 = data_fixture.create_view_sort()

    response = api_client.delete(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_2.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.delete(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": 9999}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_SORT_DOES_NOT_EXIST"

    response = api_client.delete(
        reverse("api:database:views:sort_item", kwargs={"view_sort_id": sort_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    assert ViewSort.objects.all().count() == 1


@pytest.mark.django_db
def test_list_views_including_sortings(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    field_1 = data_fixture.create_text_field(table=table_1)
    field_2 = data_fixture.create_text_field(table=table_1)
    field_3 = data_fixture.create_text_field(table=table_2)
    view_1 = data_fixture.create_grid_view(table=table_1, order=1)
    view_2 = data_fixture.create_grid_view(table=table_1, order=2)
    view_3 = data_fixture.create_grid_view(table=table_2, order=1)
    sort_1 = data_fixture.create_view_sort(view=view_1, field=field_1)
    sort_2 = data_fixture.create_view_sort(view=view_1, field=field_2)
    sort_3 = data_fixture.create_view_sort(view=view_2, field=field_1)
    data_fixture.create_view_sort(view=view_3, field=field_3)

    response = api_client.get(
        "{}".format(
            reverse("api:database:views:list", kwargs={"table_id": table_1.id})
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 2
    assert "sortings" not in response_json[0]
    assert "sortings" not in response_json[1]

    response = api_client.get(
        "{}?include=sortings".format(
            reverse("api:database:views:list", kwargs={"table_id": table_1.id})
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json[0]["sortings"]) == 2
    assert response_json[0]["sortings"][0]["id"] == sort_1.id
    assert response_json[0]["sortings"][0]["view"] == view_1.id
    assert response_json[0]["sortings"][0]["field"] == field_1.id
    assert response_json[0]["sortings"][0]["order"] == sort_1.order
    assert response_json[0]["sortings"][0]["type"] == sort_1.type
    assert response_json[0]["sortings"][1]["id"] == sort_2.id
    assert len(response_json[1]["sortings"]) == 1
    assert response_json[1]["sortings"][0]["id"] == sort_3.id


@pytest.mark.django_db
def test_cant_get_view_sort_when_view_trashed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_form_view(table=table)

    ViewHandler().delete_view(user, view)

    url = reverse("api:database:views:sort_item", kwargs={"view_sort_id": view.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_cant_update_view_sort_when_view_trashed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_number_field(user, table=table)

    view_sort = ViewHandler().create_sort(user, view, field, "asc")
    ViewHandler().delete_view(user, view)

    url = reverse(
        "api:database:views:sort_item",
        kwargs={"view_sort_id": view_sort.id},
    )

    response = api_client.patch(
        url,
        {"order": "ASC"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_cant_delete_view_sort_when_view_trashed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_number_field(user, table=table)

    view_sort = ViewHandler().create_sort(user, view, field, "asc")
    ViewHandler().delete_view(user, view)

    url = reverse(
        "api:database:views:sort_item",
        kwargs={"view_sort_id": view_sort.id},
    )

    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND
