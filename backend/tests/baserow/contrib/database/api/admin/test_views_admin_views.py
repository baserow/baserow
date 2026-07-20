from unittest.mock import patch

from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.views.view_types import GridViewType


@pytest.mark.django_db
def test_non_admin_cannot_access_admin_views_endpoints(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=False)
    view = data_fixture.create_grid_view(public=True)

    urls = [
        ("get", reverse("api:database:admin:views:list")),
        (
            "patch",
            reverse("api:database:admin:views:edit", kwargs={"view_id": view.id}),
        ),
        (
            "post",
            reverse(
                "api:database:admin:views:rotate_slug", kwargs={"view_id": view.id}
            ),
        ),
    ]

    for method, url in urls:
        response = getattr(api_client, method)(url, format="json")
        assert response.status_code == HTTP_401_UNAUTHORIZED

        response = getattr(api_client, method)(
            url, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_can_list_views_with_all_fields(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    owner = data_fixture.create_user(email="owner@baserow.io")
    table = data_fixture.create_database_table(name="Table")
    grid_view = data_fixture.create_grid_view(
        table=table,
        name="Grid",
        public=True,
        owned_by=owner,
        public_view_password=View.make_password("secret"),
    )
    form_view = data_fixture.create_form_view(table=table, name="Form", public=True)

    response = api_client.get(
        reverse("api:database:admin:views:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 2

    database = table.database
    workspace = database.workspace
    # The default ordering is by descending id, so the form view comes first.
    assert response_json["results"][0]["id"] == form_view.id
    assert response_json["results"][0]["type"] == "form"
    assert response_json["results"][0]["public_view_has_password"] is False
    assert response_json["results"][0]["owned_by_username"] is None
    grid_view_result = response_json["results"][1]
    assert grid_view_result == {
        "id": grid_view.id,
        "name": "Grid",
        "slug": str(grid_view.slug),
        "type": "grid",
        "table_id": table.id,
        "table_name": "Table",
        "database_id": database.id,
        "database_name": database.name,
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "public": True,
        "public_view_has_password": True,
        "owned_by_id": owner.id,
        "owned_by_username": "owner@baserow.io",
        "ownership_type": "collaborative",
        "created_on": grid_view.created_on.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
    }


@pytest.mark.django_db
def test_admin_can_filter_views_on_only_public(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    public_view = data_fixture.create_grid_view(public=True)
    private_view = data_fixture.create_grid_view(public=False)

    url = reverse("api:database:admin:views:list")
    response = api_client.get(
        f"{url}?only_public=true", format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == public_view.id

    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response_json["count"] == 2
    assert {result["id"] for result in response_json["results"]} == {
        public_view.id,
        private_view.id,
    }


@pytest.mark.django_db
def test_admin_can_search_views(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    workspace = data_fixture.create_workspace(name="Unique workspace name")
    database = data_fixture.create_database_application(
        workspace=workspace, name="Unique database name"
    )
    table = data_fixture.create_database_table(
        database=database, name="Unique table name"
    )
    owner = data_fixture.create_user(email="unique-owner@baserow.io")
    view = data_fixture.create_grid_view(
        table=table, name="Unique view name", owned_by=owner
    )
    data_fixture.create_grid_view(name="Something else")

    searches = [
        "Unique view name",
        str(view.id),
        str(view.slug),
        "Unique table name",
        str(table.id),
        "Unique database name",
        str(database.id),
        "Unique workspace name",
        str(workspace.id),
        "unique-owner@baserow.io",
        str(owner.id),
    ]

    url = reverse("api:database:admin:views:list")
    for search in searches:
        response = api_client.get(
            url,
            {"search": search},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        result_ids = {result["id"] for result in response.json()["results"]}
        assert view.id in result_ids, search

    response = api_client.get(
        url,
        {"search": "Unique view name"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert {result["id"] for result in response.json()["results"]} == {view.id}

    response = api_client.get(
        url,
        {"search": "No view matches this"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_admin_can_sort_views(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    view_a = data_fixture.create_grid_view(name="A")
    view_b = data_fixture.create_grid_view(name="B")

    url = reverse("api:database:admin:views:list")
    response = api_client.get(
        f"{url}?sorts=%2Bname", format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert [result["id"] for result in response.json()["results"]] == [
        view_a.id,
        view_b.id,
    ]

    response = api_client.get(
        f"{url}?sorts=-name", format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert [result["id"] for result in response.json()["results"]] == [
        view_b.id,
        view_a.id,
    ]

    response = api_client.get(
        f"{url}?sorts=%2Bunknown", format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_SORT_ATTRIBUTE"


@pytest.mark.django_db
def test_admin_can_sort_views_on_all_sortable_columns(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    owner_a = data_fixture.create_user(email="a-owner@baserow.io")
    owner_b = data_fixture.create_user(email="b-owner@baserow.io")
    workspace_a = data_fixture.create_workspace(name="A workspace")
    workspace_b = data_fixture.create_workspace(name="B workspace")
    database_a = data_fixture.create_database_application(
        workspace=workspace_a, name="A database"
    )
    database_b = data_fixture.create_database_application(
        workspace=workspace_b, name="B database"
    )
    table_a = data_fixture.create_database_table(database=database_a)
    table_b = data_fixture.create_database_table(database=database_b)
    grid_view = data_fixture.create_grid_view(
        table=table_a, public=True, owned_by=owner_a
    )
    gallery_view = data_fixture.create_gallery_view(
        table=table_b, public=False, owned_by=owner_b
    )

    ascending_orders = {
        "type": [gallery_view.id, grid_view.id],
        "database_name": [grid_view.id, gallery_view.id],
        "workspace_name": [grid_view.id, gallery_view.id],
        "public": [gallery_view.id, grid_view.id],
        "owned_by_username": [grid_view.id, gallery_view.id],
    }

    url = reverse("api:database:admin:views:list")
    for attribute, expected in ascending_orders.items():
        response = api_client.get(
            f"{url}?sorts=%2B{attribute}",
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert [result["id"] for result in response.json()["results"]] == expected, (
            attribute
        )

        response = api_client.get(
            f"{url}?sorts=-{attribute}",
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert [result["id"] for result in response.json()["results"]] == list(
            reversed(expected)
        ), attribute


@pytest.mark.django_db
def test_admin_list_views_excludes_trashed_snapshots_and_templates(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    view = data_fixture.create_grid_view()

    data_fixture.create_grid_view(trashed=True)
    trashed_table = data_fixture.create_database_table(trashed=True)
    data_fixture.create_grid_view(table=trashed_table)
    trashed_database = data_fixture.create_database_application(trashed=True)
    data_fixture.create_grid_view(
        table=data_fixture.create_database_table(database=trashed_database)
    )
    trashed_workspace = data_fixture.create_workspace(trashed=True)
    data_fixture.create_grid_view(
        table=data_fixture.create_database_table(
            database=data_fixture.create_database_application(
                workspace=trashed_workspace
            )
        )
    )
    snapshot_database = data_fixture.create_database_application(workspace=None)
    data_fixture.create_grid_view(
        table=data_fixture.create_database_table(database=snapshot_database)
    )
    template_workspace = data_fixture.create_workspace()
    data_fixture.create_template(workspace=template_workspace)
    data_fixture.create_grid_view(
        table=data_fixture.create_database_table(
            database=data_fixture.create_database_application(
                workspace=template_workspace
            )
        )
    )

    response = api_client.get(
        reverse("api:database:admin:views:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == view.id


@pytest.mark.django_db
def test_admin_list_views_number_of_queries_is_constant(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    url = reverse("api:database:admin:views:list")

    def fetch_and_count_queries():
        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(
                url, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
            )
            assert response.status_code == HTTP_200_OK
        return len(queries.captured_queries)

    data_fixture.create_grid_view(public=True)
    first_count = fetch_and_count_queries()

    data_fixture.create_grid_view(public=True)
    data_fixture.create_gallery_view(public=True)
    data_fixture.create_form_view(public=True, owned_by=data_fixture.create_user())
    assert fetch_and_count_queries() == first_count


@pytest.mark.django_db
def test_admin_can_update_view_public(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    # The staff user is deliberately not a member of the view's workspace.
    view = data_fixture.create_grid_view(public=True)

    url = reverse("api:database:admin:views:edit", kwargs={"view_id": view.id})
    with patch(
        "baserow.contrib.database.admin.views.handler.view_updated.send"
    ) as mock_view_updated:
        response = api_client.patch(
            url,
            {"public": False},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert response.json()["public"] is False
    view.refresh_from_db()
    assert view.public is False
    assert mock_view_updated.call_count == 1
    assert mock_view_updated.call_args[1]["view"].id == view.id

    # It must also be possible to make the view public again because it could
    # mistakenly have been made private.
    response = api_client.patch(
        url,
        {"public": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["public"] is True
    view.refresh_from_db()
    assert view.public is True


@pytest.mark.django_db
def test_admin_can_rotate_view_slug(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    view = data_fixture.create_grid_view(public=True)
    old_slug = str(view.slug)

    response = api_client.post(
        reverse("api:database:admin:views:rotate_slug", kwargs={"view_id": view.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    view.refresh_from_db()
    assert str(view.slug) != old_slug
    assert response.json()["slug"] == str(view.slug)


@pytest.mark.django_db
def test_admin_view_actions_with_unknown_view_or_unshareable_type(
    api_client, data_fixture
):
    class UnShareableViewType(GridViewType):
        can_share = False

    _, token = data_fixture.create_user_and_token(is_staff=True)
    view = data_fixture.create_grid_view(public=True)

    edit_url = reverse("api:database:admin:views:edit", kwargs={"view_id": 99999})
    response = api_client.patch(
        edit_url, {"public": False}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    rotate_url = reverse(
        "api:database:admin:views:rotate_slug", kwargs={"view_id": 99999}
    )
    response = api_client.post(
        rotate_url, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # `get_for_class` is lru_cached, so the mapping to the real `GridViewType` can
    # already be cached by earlier tests, making `patch.dict` on the registry
    # unreliable here.
    with patch.object(
        view_type_registry, "get_for_class", return_value=UnShareableViewType()
    ):
        response = api_client.patch(
            reverse("api:database:admin:views:edit", kwargs={"view_id": view.id}),
            {"public": False},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_CANNOT_SHARE_VIEW_TYPE"

        response = api_client.post(
            reverse(
                "api:database:admin:views:rotate_slug", kwargs={"view_id": view.id}
            ),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_CANNOT_SHARE_VIEW_TYPE"
