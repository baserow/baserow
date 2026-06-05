import json

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND

from baserow.contrib.database.views.handler import ViewHandler


@pytest.mark.django_db
def test_returns_empty_tree_when_view_has_no_group_by(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table)
    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"nodes": [], "truncated": False, "total_nodes": 0}


@pytest.mark.django_db
def test_returns_single_level_tree(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "nodes": [
            {"path": {f"field_{color.id}": "Green"}, "depth": 0, "row_count": 2},
            {"path": {f"field_{color.id}": "Red"}, "depth": 0, "row_count": 1},
        ],
        "truncated": False,
        "total_nodes": 2,
    }


@pytest.mark.django_db
def test_returns_nested_tree_in_display_order(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 10})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 10})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 20})
    model.objects.create(**{f"field_{color.id}": "Red", f"field_{size.id}": 10})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "nodes": [
            {
                "path": {f"field_{color.id}": "Green"},
                "depth": 0,
                "row_count": 3,
                "children_count": 2,
            },
            {
                "path": {f"field_{color.id}": "Green", f"field_{size.id}": "10"},
                "depth": 1,
                "row_count": 2,
            },
            {
                "path": {f"field_{color.id}": "Green", f"field_{size.id}": "20"},
                "depth": 1,
                "row_count": 1,
            },
            {
                "path": {f"field_{color.id}": "Red"},
                "depth": 0,
                "row_count": 1,
                "children_count": 1,
            },
            {
                "path": {f"field_{color.id}": "Red", f"field_{size.id}": "10"},
                "depth": 1,
                "row_count": 1,
            },
        ],
        "truncated": False,
        "total_nodes": 5,
    }


@pytest.mark.django_db
def test_group_tree_respects_filters_and_search(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_filter(
        view=grid, field=color, type="not_equal", value="Red"
    )

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Greenish"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"search": "Green"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    values = [node["path"][f"field_{color.id}"] for node in response.json()["nodes"]]
    assert values == ["Green", "Greenish"]


@pytest.mark.django_db
def test_descending_group_by_order_is_reflected(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color, order="DESC")

    model = table.get_model()
    for value in ["A", "B", "C"]:
        model.objects.create(**{f"field_{color.id}": value})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    paths = [node["path"][f"field_{color.id}"] for node in response.json()["nodes"]]
    assert paths == ["C", "B", "A"]


@pytest.mark.django_db
def test_max_depth_and_expanded_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 10})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 20})
    model.objects.create(**{f"field_{color.id}": "Red", f"field_{size.id}": 10})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {
            "max_depth": 1,
            "expanded": json.dumps([{f"field_{color.id}": "Green"}]),
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    paths = [
        (
            node["path"].get(f"field_{color.id}"),
            node["path"].get(f"field_{size.id}"),
        )
        for node in response.json()["nodes"]
    ]
    assert paths == [("Green", None), ("Green", "10"), ("Green", "20"), ("Red", None)]


@pytest.mark.django_db
@override_settings(VIEW_GROUP_TREE_MAX_NODES=2)
def test_truncation_when_tree_exceeds_cap(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    for value in ["A", "B", "C"]:
        model.objects.create(**{f"field_{color.id}": value})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"nodes": [], "truncated": True, "total_nodes": 3}


@pytest.mark.django_db
def test_private_group_tree_view_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": 9999})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_public_group_tree(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table, public=True)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Red"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse(
        "api:database:views:grid:public_group_tree", kwargs={"slug": grid.slug}
    )
    response = api_client.get(url)

    assert response.status_code == HTTP_200_OK
    assert response.json()["nodes"] == [
        {"path": {f"field_{color.id}": "Green"}, "depth": 0, "row_count": 1},
        {"path": {f"field_{color.id}": "Red"}, "depth": 0, "row_count": 2},
    ]


@pytest.mark.django_db
def test_public_group_tree_requires_public_auth_token(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(
        table=table, public=True, public_view_password="password"
    )
    data_fixture.create_view_group_by(view=grid, field=color)

    url = reverse(
        "api:database:views:grid:public_group_tree", kwargs={"slug": grid.slug}
    )
    response = api_client.get(url)

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"

    public_view_token = ViewHandler().encode_public_view_token(grid)
    response = api_client.get(
        url, HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}"
    )

    assert response.status_code == HTTP_200_OK
