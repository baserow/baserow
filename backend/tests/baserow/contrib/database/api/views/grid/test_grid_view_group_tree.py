import json

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND


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
    body = response.json()
    assert body["truncated"] is False
    assert body["total_nodes"] == 2
    # Single-level group-by: depth-0 IS the leaf depth, so no children_count.
    assert body["nodes"] == [
        {"path": {f"field_{color.id}": "Green"}, "depth": 0, "row_count": 2},
        {"path": {f"field_{color.id}": "Red"}, "depth": 0, "row_count": 1},
    ]


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
    body = response.json()
    assert body["truncated"] is False
    assert body["total_nodes"] == 5

    # depth-0 carries children_count (immediate sub-groups); depth-1 is leaf,
    # so children_count is omitted there.
    assert body["nodes"] == [
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
    ]


@pytest.mark.django_db
def test_view_filter_excludes_rows_from_counts(api_client, data_fixture):
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
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    body = response.json()
    assert body["nodes"] == [
        {"path": {f"field_{color.id}": "Green"}, "depth": 0, "row_count": 2},
    ]


@pytest.mark.django_db
def test_adhoc_filter_overrides_view_filter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Red"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {f"filter__field_{color.id}__equal": "Red"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    body = response.json()
    assert body["nodes"] == [
        {"path": {f"field_{color.id}": "Red"}, "depth": 0, "row_count": 2},
    ]


@pytest.mark.django_db
def test_search_narrows_counts(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Greenish"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"search": "Green"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    body = response.json()
    paths = [node["path"][f"field_{color.id}"] for node in body["nodes"]]
    assert set(paths) == {"Green", "Greenish"}
    assert all(node["depth"] == 0 for node in body["nodes"])


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
    body = response.json()
    assert body["truncated"] is True
    assert body["nodes"] == []
    assert body["total_nodes"] == 3


@pytest.mark.django_db
def test_view_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": 9999})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_descending_group_by_order_is_reflected(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color, order="DESC")

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "A"})
    model.objects.create(**{f"field_{color.id}": "B"})
    model.objects.create(**{f"field_{color.id}": "C"})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    paths = [node["path"][f"field_{color.id}"] for node in response.json()["nodes"]]
    assert paths == ["C", "B", "A"]


@pytest.mark.django_db
def test_max_depth_returns_only_depth_0_outline(api_client, data_fixture):
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
    response = api_client.get(url, {"max_depth": 1}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    body = response.json()
    # Only depth-0 nodes; each carries children_count for layout reservation.
    assert body["nodes"] == [
        {
            "path": {f"field_{color.id}": "Green"},
            "depth": 0,
            "row_count": 2,
            "children_count": 2,
        },
        {
            "path": {f"field_{color.id}": "Red"},
            "depth": 0,
            "row_count": 1,
            "children_count": 1,
        },
    ]


@pytest.mark.django_db
def test_expanded_path_returns_subtree_alongside_outline(api_client, data_fixture):
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
    response = api_client.get(
        url,
        {
            "max_depth": 1,
            "expanded": json.dumps([{f"field_{color.id}": "Green"}]),
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    body = response.json()
    # Both depth-0 nodes plus the subtree under Green.
    assert body["nodes"] == [
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
    ]


@pytest.mark.django_db
def test_expanded_path_silently_ignores_unknown_paths(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {
            "max_depth": 1,
            "expanded": json.dumps([{f"field_{color.id}": "Vanished"}]),
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    body = response.json()
    paths = [node["path"][f"field_{color.id}"] for node in body["nodes"]]
    assert set(paths) == {"Green", "Red"}


@pytest.mark.django_db
def test_expanded_only_returns_just_those_subtrees(api_client, data_fixture):
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
    model.objects.create(**{f"field_{color.id}": "Red", f"field_{size.id}": 10})

    url = reverse("api:database:views:grid:group-tree", kwargs={"view_id": grid.id})
    # No max_depth, only expanded → outline omitted, only the requested subtree
    # comes back. This is the "incremental fetch on expand" call shape.
    response = api_client.get(
        url,
        {"expanded": json.dumps([{f"field_{color.id}": "Green"}])},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    body = response.json()
    paths = [
        (node["path"].get(f"field_{color.id}"), node["path"].get(f"field_{size.id}"))
        for node in body["nodes"]
    ]
    assert paths == [("Green", "10")]
