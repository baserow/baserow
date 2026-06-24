import json

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND

from baserow.contrib.database.api.views.grid import utils as grid_view_utils
from baserow.contrib.database.views.handler import ViewHandler


def _get_only_page(response):
    response_json = response.json()
    assert set(response_json.keys()) == {"pages"}
    assert len(response_json["pages"]) == 1
    return response_json["pages"][0]


def _get_page_by_parent(response_json, parent):
    for page in response_json["pages"]:
        if page["parent"] == parent:
            return page
    pytest.fail(f"Could not find group-by data page for parent {parent}")


@pytest.mark.django_db
def test_returns_empty_group_by_data_when_view_has_no_group_by(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table)
    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "pages": [
            {
                "parent": {},
                "groups": [],
                "offset": 0,
                "limit": 40,
                "group_count": 0,
            }
        ]
    }


@pytest.mark.django_db
def test_returns_paged_top_level_group_by_data(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Blue"})
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"offset": 1, "limit": 1}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "pages": [
            {
                "parent": {},
                "groups": [
                    {
                        "path": {f"field_{color.id}": "Green"},
                        "depth": 0,
                        "row_count": 2,
                        "sibling_index": 1,
                        "row_offset": 1,
                    }
                ],
                "offset": 1,
                "limit": 1,
                "group_count": 3,
            }
        ]
    }


@pytest.mark.django_db
def test_returns_nested_child_group_by_data_with_absolute_offsets(
    api_client, data_fixture
):
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
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": 1})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 10})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 10})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 20})
    model.objects.create(**{f"field_{color.id}": "Red", f"field_{size.id}": 10})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"parent": json.dumps({f"field_{color.id}": "Green"})},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "pages": [
            {
                "parent": {f"field_{color.id}": "Green"},
                "groups": [
                    {
                        "path": {
                            f"field_{color.id}": "Green",
                            f"field_{size.id}": "10",
                        },
                        "depth": 1,
                        "row_count": 2,
                        "sibling_index": 0,
                        "row_offset": 1,
                    },
                    {
                        "path": {
                            f"field_{color.id}": "Green",
                            f"field_{size.id}": "20",
                        },
                        "depth": 1,
                        "row_count": 1,
                        "sibling_index": 1,
                        "row_offset": 3,
                    },
                ],
                "offset": 0,
                "limit": 40,
                "group_count": 2,
            }
        ]
    }


@pytest.mark.django_db
def test_group_by_data_depth_page_returns_total_limited_groups_split_by_parent(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_text_field(table=table, name="Size")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    for color_value, size_value in [
        ("Blue", "Large"),
        ("Blue", "Medium"),
        ("Blue", "Small"),
        ("Green", "Large"),
        ("Green", "Small"),
        ("Red", "Large"),
    ]:
        model.objects.create(
            **{f"field_{color.id}": color_value, f"field_{size.id}": size_value}
        )

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"depth": 1, "offset": 1, "limit": 4},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert sum(len(page["groups"]) for page in response_json["pages"]) == 4

    blue_page = _get_page_by_parent(response_json, {f"field_{color.id}": "Blue"})
    assert blue_page["offset"] == 1
    assert blue_page["limit"] == 2
    assert blue_page["group_count"] == 3
    assert [
        (
            group["path"][f"field_{size.id}"],
            group["sibling_index"],
            group["row_offset"],
        )
        for group in blue_page["groups"]
    ] == [("Medium", 1, 1), ("Small", 2, 2)]

    green_page = _get_page_by_parent(response_json, {f"field_{color.id}": "Green"})
    assert green_page["offset"] == 0
    assert green_page["limit"] == 2
    assert green_page["group_count"] == 2
    assert [
        (
            group["path"][f"field_{size.id}"],
            group["sibling_index"],
            group["row_offset"],
        )
        for group in green_page["groups"]
    ] == [("Large", 0, 3), ("Small", 1, 4)]

    assert not any(
        page["parent"] == {f"field_{color.id}": "Red"}
        for page in response_json["pages"]
    )


@pytest.mark.django_db
def test_returns_group_by_data_for_multiple_parent_pages(api_client, data_fixture):
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
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": 1})
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": 2})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 10})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 20})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 20})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    parents = [
        {
            "parent": {f"field_{color.id}": "Blue"},
            "offset": 0,
            "limit": 10,
        },
        {
            "parent": {f"field_{color.id}": "Green"},
            "offset": 1,
            "limit": 1,
        },
    ]
    response = api_client.get(
        url,
        {"parents": json.dumps(parents)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "pages": [
            {
                "parent": {f"field_{color.id}": "Blue"},
                "groups": [
                    {
                        "path": {
                            f"field_{color.id}": "Blue",
                            f"field_{size.id}": "1",
                        },
                        "depth": 1,
                        "row_count": 1,
                        "sibling_index": 0,
                        "row_offset": 0,
                    },
                    {
                        "path": {
                            f"field_{color.id}": "Blue",
                            f"field_{size.id}": "2",
                        },
                        "depth": 1,
                        "row_count": 1,
                        "sibling_index": 1,
                        "row_offset": 1,
                    },
                ],
                "offset": 0,
                "limit": 10,
                "group_count": 2,
            },
            {
                "parent": {f"field_{color.id}": "Green"},
                "groups": [
                    {
                        "path": {
                            f"field_{color.id}": "Green",
                            f"field_{size.id}": "20",
                        },
                        "depth": 1,
                        "row_count": 2,
                        "sibling_index": 1,
                        "row_offset": 3,
                    }
                ],
                "offset": 1,
                "limit": 1,
                "group_count": 2,
            },
        ]
    }


@pytest.mark.django_db
def test_group_by_data_can_include_bounded_descendant_pages(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )
    status = data_fixture.create_text_field(table=table, name="Status")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)
    data_fixture.create_view_group_by(view=grid, field=status)

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{color.id}": "Blue",
            f"field_{size.id}": 1,
            f"field_{status.id}": "Todo",
        }
    )
    model.objects.create(
        **{
            f"field_{color.id}": "Blue",
            f"field_{size.id}": 2,
            f"field_{status.id}": "Done",
        }
    )
    model.objects.create(
        **{
            f"field_{color.id}": "Green",
            f"field_{size.id}": 10,
            f"field_{status.id}": "Todo",
        }
    )

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"include_descendants": "true", "descendant_limit": 1},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "truncated" not in response_json
    assert len(response_json["pages"]) == 5

    root_page = _get_page_by_parent(response_json, {})
    assert root_page["group_count"] == 2
    assert [group["path"][f"field_{color.id}"] for group in root_page["groups"]] == [
        "Blue",
        "Green",
    ]

    blue_page = _get_page_by_parent(response_json, {f"field_{color.id}": "Blue"})
    assert blue_page["group_count"] == 2
    assert [group["path"][f"field_{size.id}"] for group in blue_page["groups"]] == ["1"]

    blue_status_page = _get_page_by_parent(
        response_json,
        {f"field_{color.id}": "Blue", f"field_{size.id}": "1"},
    )
    assert [
        group["path"][f"field_{status.id}"] for group in blue_status_page["groups"]
    ] == ["Todo"]
    assert not any(
        page["parent"] == {f"field_{color.id}": "Blue", f"field_{size.id}": "2"}
        for page in response_json["pages"]
    )


@pytest.mark.django_db
def test_group_by_data_descendants_respect_total_group_limit(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_text_field(table=table, name="Size")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    for size_value in ["Large", "Medium", "Small"]:
        model.objects.create(
            **{f"field_{color.id}": "Blue", f"field_{size.id}": size_value}
        )
    for size_value in ["Large", "Small"]:
        model.objects.create(
            **{f"field_{color.id}": "Green", f"field_{size.id}": size_value}
        )

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"include_descendants": "true", "limit": 4},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    returned_group_count = sum(len(page["groups"]) for page in response_json["pages"])
    assert returned_group_count == 4
    assert response_json["truncated"] is True

    root_page = _get_page_by_parent(response_json, {})
    assert [group["path"][f"field_{color.id}"] for group in root_page["groups"]] == [
        "Blue",
        "Green",
    ]

    blue_page = _get_page_by_parent(response_json, {f"field_{color.id}": "Blue"})
    assert blue_page["group_count"] == 3
    assert [group["path"][f"field_{size.id}"] for group in blue_page["groups"]] == [
        "Large",
        "Medium",
    ]
    assert not any(
        page["parent"] == {f"field_{color.id}": "Green"}
        for page in response_json["pages"]
    )


@pytest.mark.django_db
def test_group_by_data_reuses_parent_offsets_for_descendant_pages(
    api_client, data_fixture, monkeypatch
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_text_field(table=table, name="Size")
    status = data_fixture.create_text_field(table=table, name="Status")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)
    data_fixture.create_view_group_by(view=grid, field=status)

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{color.id}": "Blue",
            f"field_{size.id}": "Large",
            f"field_{status.id}": "Done",
        }
    )
    model.objects.create(
        **{
            f"field_{color.id}": "Blue",
            f"field_{size.id}": "Small",
            f"field_{status.id}": "Todo",
        }
    )
    model.objects.create(
        **{
            f"field_{color.id}": "Green",
            f"field_{size.id}": "Medium",
            f"field_{status.id}": "Todo",
        }
    )

    looked_up_paths = []
    original_lookup = ViewHandler._get_group_by_path_row_offset

    def spy_lookup(self, group_by_levels, base_queryset, path):
        looked_up_paths.append(path.copy())
        return original_lookup(self, group_by_levels, base_queryset, path)

    monkeypatch.setattr(ViewHandler, "_get_group_by_path_row_offset", spy_lookup)

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"include_descendants": "true", "descendant_limit": 1},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert len(response.json()["pages"]) == 5
    assert looked_up_paths == [{}]


@pytest.mark.django_db
def test_group_by_data_descendant_loading_is_capped(
    api_client, data_fixture, monkeypatch
):
    monkeypatch.setattr(grid_view_utils, "GROUP_BY_DATA_DESCENDANT_MAX_PAGES", 2)

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
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": 1})
    model.objects.create(**{f"field_{color.id}": "Green", f"field_{size.id}": 2})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"include_descendants": "true"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["truncated"] is True
    assert len(response_json["pages"]) == 2


@pytest.mark.django_db
def test_group_by_data_includes_descendants_for_multiple_parent_pages(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )
    status = data_fixture.create_text_field(table=table, name="Status")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)
    data_fixture.create_view_group_by(view=grid, field=status)

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{color.id}": "Blue",
            f"field_{size.id}": 1,
            f"field_{status.id}": "Todo",
        }
    )
    model.objects.create(
        **{
            f"field_{color.id}": "Green",
            f"field_{size.id}": 2,
            f"field_{status.id}": "Done",
        }
    )

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    parents = [
        {"parent": {f"field_{color.id}": "Blue"}, "offset": 0, "limit": 40},
        {"parent": {f"field_{color.id}": "Green"}, "offset": 0, "limit": 40},
    ]
    response = api_client.get(
        url,
        {"parents": json.dumps(parents), "include_descendants": "true"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert _get_page_by_parent(response_json, {f"field_{color.id}": "Blue"})
    assert _get_page_by_parent(response_json, {f"field_{color.id}": "Green"})
    assert _get_page_by_parent(
        response_json,
        {f"field_{color.id}": "Blue", f"field_{size.id}": "1"},
    )
    assert _get_page_by_parent(
        response_json,
        {f"field_{color.id}": "Green", f"field_{size.id}": "2"},
    )


@pytest.mark.django_db
def test_group_by_data_respects_filters_search_and_order(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color, order="DESC")
    data_fixture.create_view_filter(
        view=grid, field=color, type="not_equal", value="Red"
    )

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Greenish"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"search": "Green"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    page = _get_only_page(response)
    values = [group["path"][f"field_{color.id}"] for group in page["groups"]]
    assert values == ["Greenish", "Green"]


@pytest.mark.django_db
def test_group_by_data_can_order_single_select_groups(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    select = data_fixture.create_single_select_field(table=table, name="Status")
    option_b = data_fixture.create_select_option(field=select, value="B", order=1)
    option_a = data_fixture.create_select_option(field=select, value="A", order=2)
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=select)

    model = table.get_model()
    model.objects.create(**{f"field_{select.id}_id": option_b.id})
    model.objects.create(**{f"field_{select.id}_id": option_a.id})
    model.objects.create(**{f"field_{select.id}_id": option_a.id})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    page = _get_only_page(response)
    assert [group["path"][f"field_{select.id}"] for group in page["groups"]] == [
        option_a.id,
        option_b.id,
    ]
    assert [group["row_offset"] for group in page["groups"]] == [0, 2]
    assert page["group_count"] == 2
    assert "total_rows" not in response_json


@pytest.mark.django_db
def test_group_by_data_orders_when_order_keys_are_not_projected(
    api_client, data_fixture, monkeypatch
):
    # The window query normally orders by projected "order key" aliases. When an
    # ordering can't be projected into one (e.g. a plugin field type whose
    # get_order returns a non-OrderBy), the handler falls back to compiling the
    # raw ordering SQL and rewriting its table alias. Forcing the projection to a
    # no-op leaves the field's real Collate(...) ordering in place, which
    # exercises that fallback end to end.
    monkeypatch.setattr(
        ViewHandler,
        "_add_group_by_data_order_key_annotations",
        lambda self, queryset, order_by_args: (queryset, [], order_by_args),
    )

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Blue"})
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Green"})
    model.objects.create(**{f"field_{color.id}": "Red"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    page = _get_only_page(response)
    assert [group["path"][f"field_{color.id}"] for group in page["groups"]] == [
        "Blue",
        "Green",
        "Red",
    ]
    assert [group["sibling_index"] for group in page["groups"]] == [0, 1, 2]
    assert [group["row_offset"] for group in page["groups"]] == [0, 1, 3]
    assert [group["row_count"] for group in page["groups"]] == [1, 2, 1]
    assert page["group_count"] == 3


@pytest.mark.django_db
def test_group_by_data_has_no_global_truncation_cap(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    for index in range(45):
        model.objects.create(**{f"field_{color.id}": f"Value {index:02d}"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"offset": 40, "limit": 10}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    page = _get_only_page(response)
    assert page["group_count"] == 45
    assert "total_rows" not in response_json
    assert [group["sibling_index"] for group in page["groups"]] == [
        40,
        41,
        42,
        43,
        44,
    ]
    assert [group["row_offset"] for group in page["groups"]] == [
        40,
        41,
        42,
        43,
        44,
    ]


@pytest.mark.django_db
def test_group_by_data_empty_page_returns_group_count(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    for value in ["Blue", "Green", "Red"]:
        model.objects.create(**{f"field_{color.id}": value})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"offset": 10, "limit": 5}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    page = _get_only_page(response)
    assert page["groups"] == []
    assert page["offset"] == 10
    assert page["limit"] == 5
    assert page["group_count"] == 3
    assert "total_rows" not in response_json


@pytest.mark.django_db
def test_group_by_data_includes_empty_value_group(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    # Two rows have no value for the grouped field, exercising the null group.
    model.objects.create(**{f"field_{color.id}": None})
    model.objects.create(**{f"field_{color.id}": None})
    model.objects.create(**{f"field_{color.id}": "Blue"})
    model.objects.create(**{f"field_{color.id}": "Green"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    page = _get_only_page(response)
    assert page["group_count"] == 3
    # The null group sorts first in ascending order, taking row offset 0.
    assert page["groups"] == [
        {
            "path": {f"field_{color.id}": None},
            "depth": 0,
            "row_count": 2,
            "sibling_index": 0,
            "row_offset": 0,
        },
        {
            "path": {f"field_{color.id}": "Blue"},
            "depth": 0,
            "row_count": 1,
            "sibling_index": 1,
            "row_offset": 2,
        },
        {
            "path": {f"field_{color.id}": "Green"},
            "depth": 0,
            "row_count": 1,
            "sibling_index": 2,
            "row_offset": 3,
        },
    ]


@pytest.mark.django_db
def test_group_by_data_returns_children_for_empty_value_parent(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_text_field(table=table, name="Size")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": None, f"field_{size.id}": "Large"})
    model.objects.create(**{f"field_{color.id}": None, f"field_{size.id}": "Large"})
    model.objects.create(**{f"field_{color.id}": None, f"field_{size.id}": "Small"})
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": "Small"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"parent": json.dumps({f"field_{color.id}": None})},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "pages": [
            {
                "parent": {f"field_{color.id}": None},
                "groups": [
                    {
                        "path": {
                            f"field_{color.id}": None,
                            f"field_{size.id}": "Large",
                        },
                        "depth": 1,
                        "row_count": 2,
                        "sibling_index": 0,
                        "row_offset": 0,
                    },
                    {
                        "path": {
                            f"field_{color.id}": None,
                            f"field_{size.id}": "Small",
                        },
                        "depth": 1,
                        "row_count": 1,
                        "sibling_index": 1,
                        "row_offset": 2,
                    },
                ],
                "offset": 0,
                "limit": 40,
                "group_count": 2,
            }
        ]
    }


@pytest.mark.django_db
def test_group_by_data_clamps_limit_to_row_page_size_limit(
    api_client, data_fixture, settings
):
    settings.ROW_PAGE_SIZE_LIMIT = 2

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    for value in ["Blue", "Green", "Orange", "Red"]:
        model.objects.create(**{f"field_{color.id}": value})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(url, {"limit": 1000}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    page = _get_only_page(response)
    # The over-large limit is clamped to ROW_PAGE_SIZE_LIMIT.
    assert page["limit"] == 2
    assert len(page["groups"]) == 2
    assert page["group_count"] == 4
    assert [group["path"][f"field_{color.id}"] for group in page["groups"]] == [
        "Blue",
        "Green",
    ]


@pytest.mark.django_db
def test_group_by_data_clamps_descendant_limit_to_row_page_size_limit(
    api_client, data_fixture, settings
):
    settings.ROW_PAGE_SIZE_LIMIT = 2

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_text_field(table=table, name="Size")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    for size_value in ["Large", "Medium", "Small"]:
        model.objects.create(
            **{f"field_{color.id}": "Blue", f"field_{size.id}": size_value}
        )

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"include_descendants": "true", "descendant_limit": 1000},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    blue_page = _get_page_by_parent(response_json, {f"field_{color.id}": "Blue"})
    # The over-large descendant_limit is clamped to ROW_PAGE_SIZE_LIMIT.
    assert blue_page["limit"] == 2
    assert blue_page["group_count"] == 3


@pytest.mark.django_db
def test_group_by_data_malformed_parent_degrades_to_empty_page(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Blue"})
    model.objects.create(**{f"field_{color.id}": "Green"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"parent": "not-json"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    page = _get_only_page(response)
    assert page["groups"] == []
    assert page["group_count"] == 0


@pytest.mark.django_db
def test_group_by_data_malformed_parents_degrades_to_empty_page(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Blue"})
    model.objects.create(**{f"field_{color.id}": "Green"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    # ``parents`` must be a JSON list; a JSON object degrades silently.
    response = api_client.get(
        url,
        {"parents": json.dumps({"parent": {}})},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    page = _get_only_page(response)
    assert page["groups"] == []
    assert page["group_count"] == 0


def test_group_by_data_does_not_use_python_offset_summing_helper():
    assert not hasattr(ViewHandler, "_sum_group_by_row_counts")


@pytest.mark.django_db
def test_private_group_by_data_view_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": 9999})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_public_group_by_data(api_client, data_fixture):
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
        "api:database:views:grid:public-group-by-data", kwargs={"slug": grid.slug}
    )
    response = api_client.get(url)

    assert response.status_code == HTTP_200_OK
    page = _get_only_page(response)
    assert page["groups"] == [
        {
            "path": {f"field_{color.id}": "Green"},
            "depth": 0,
            "row_count": 1,
            "sibling_index": 0,
            "row_offset": 0,
        },
        {
            "path": {f"field_{color.id}": "Red"},
            "depth": 0,
            "row_count": 2,
            "sibling_index": 1,
            "row_offset": 1,
        },
    ]


@pytest.mark.django_db
def test_public_group_by_data_supports_depth_pages(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_text_field(table=table, name="Size")
    grid = data_fixture.create_grid_view(table=table, public=True)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    for color_value, size_value in [
        ("Blue", "Large"),
        ("Blue", "Small"),
        ("Green", "Large"),
    ]:
        model.objects.create(
            **{f"field_{color.id}": color_value, f"field_{size.id}": size_value}
        )

    url = reverse(
        "api:database:views:grid:public-group-by-data", kwargs={"slug": grid.slug}
    )
    response = api_client.get(url, {"depth": 1, "offset": 1, "limit": 2})

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert sum(len(page["groups"]) for page in response_json["pages"]) == 2

    blue_page = _get_page_by_parent(response_json, {f"field_{color.id}": "Blue"})
    assert blue_page["offset"] == 1
    assert blue_page["limit"] == 1
    assert blue_page["group_count"] == 2
    assert [group["path"][f"field_{size.id}"] for group in blue_page["groups"]] == [
        "Small"
    ]

    green_page = _get_page_by_parent(response_json, {f"field_{color.id}": "Green"})
    assert green_page["offset"] == 0
    assert green_page["limit"] == 1
    assert green_page["group_count"] == 1
    assert [group["path"][f"field_{size.id}"] for group in green_page["groups"]] == [
        "Large"
    ]


@pytest.mark.django_db
def test_public_group_by_data_can_include_bounded_descendant_pages(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )
    grid = data_fixture.create_grid_view(table=table, public=True)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": 1})
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": 2})

    url = reverse(
        "api:database:views:grid:public-group-by-data", kwargs={"slug": grid.slug}
    )
    response = api_client.get(
        url, {"include_descendants": "true", "descendant_limit": 1}
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    blue_page = _get_page_by_parent(response_json, {f"field_{color.id}": "Blue"})
    assert blue_page["group_count"] == 2
    assert [group["path"][f"field_{size.id}"] for group in blue_page["groups"]] == ["1"]


@pytest.mark.django_db
def test_public_group_by_data_requires_public_auth_token(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(
        table=table, public=True, public_view_password="password"
    )
    data_fixture.create_view_group_by(view=grid, field=color)

    url = reverse(
        "api:database:views:grid:public-group-by-data", kwargs={"slug": grid.slug}
    )
    response = api_client.get(url)

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"

    public_view_token = ViewHandler().encode_public_view_token(grid)
    response = api_client.get(
        url, HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}"
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_group_by_data_threaded_parent_row_offset_is_a_pure_speedup(
    api_client, data_fixture, monkeypatch
):
    """
    Passing ``parent_row_offset`` should only save work. It must return the same
    child groups and row offsets as the normal path, while skipping the extra
    lookup that recalculates where the parent group starts.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_text_field(table=table, name="Size")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=color)
    data_fixture.create_view_group_by(view=grid, field=size)

    model = table.get_model()
    # "Aaa" sorts before "Blue", so Blue's first row is not at absolute offset 0 and a
    # wrong/skipped offset would be observable.
    model.objects.create(**{f"field_{color.id}": "Aaa", f"field_{size.id}": "Small"})
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": "Large"})
    model.objects.create(**{f"field_{color.id}": "Blue", f"field_{size.id}": "Small"})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    blue_parent = {f"field_{color.id}": "Blue"}

    # Discover Blue's true absolute row offset from the top-level request.
    top = api_client.get(
        url, {"parent": json.dumps({})}, HTTP_AUTHORIZATION=f"JWT {token}"
    ).json()
    blue = next(
        group
        for group in top["pages"][0]["groups"]
        if group["path"][f"field_{color.id}"] == "Blue"
    )
    assert blue["row_offset"] == 1  # the single "Aaa" row precedes Blue

    looked_up_paths = []
    original_lookup = ViewHandler._get_group_by_path_row_offset

    def spy_lookup(self, group_by_levels, base_queryset, path):
        looked_up_paths.append(path.copy())
        return original_lookup(self, group_by_levels, base_queryset, path)

    monkeypatch.setattr(ViewHandler, "_get_group_by_path_row_offset", spy_lookup)

    # Recursive path: only the parent path is supplied, so the server recomputes the
    # parent's absolute offset.
    looked_up_paths.clear()
    without_hint = api_client.get(
        url, {"parent": json.dumps(blue_parent)}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    recursive_lookups = [path for path in looked_up_paths if path]

    # Threaded path: the client passes the already-known parent_row_offset.
    looked_up_paths.clear()
    with_hint = api_client.get(
        url,
        {
            "parents": json.dumps(
                [
                    {
                        "parent": blue_parent,
                        "offset": 0,
                        "limit": 40,
                        "parent_row_offset": blue["row_offset"],
                    }
                ]
            )
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    threaded_lookups = [path for path in looked_up_paths if path]

    assert without_hint.status_code == HTTP_200_OK
    assert with_hint.status_code == HTTP_200_OK

    # (a) Consistency: identical child groups, including the absolute row offsets.
    without_groups = without_hint.json()["pages"][0]["groups"]
    with_groups = with_hint.json()["pages"][0]["groups"]
    assert with_groups == without_groups
    assert [group["row_offset"] for group in with_groups] == [1, 2]

    # (b) Profile: the recursive offset lookup fires without the hint and is skipped
    # with it.
    assert len(recursive_lookups) >= 1
    assert threaded_lookups == []


@pytest.mark.django_db
def test_group_by_data_includes_multiple_collaborators_display_values(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    collaborator = data_fixture.create_user(
        workspace=database.workspace, first_name="Davide"
    )
    field = data_fixture.create_multiple_collaborators_field(table=table, name="People")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=field)

    model = table.get_model()
    getattr(model.objects.create(), field.db_column).set([collaborator.id])

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    group = _get_only_page(response)["groups"][0]
    assert group["path"][f"field_{field.id}"] == [collaborator.id]
    assert group["display"][f"field_{field.id}"] == [
        {"id": collaborator.id, "name": "Davide"}
    ]


@pytest.mark.django_db
def test_group_by_data_includes_link_row_display_values(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    linked_table = data_fixture.create_database_table(user=user, database=database)
    linked_primary = data_fixture.create_text_field(
        table=linked_table, name="Name", primary=True
    )
    field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table, name="Links"
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=field)

    linked_model = linked_table.get_model()
    linked = linked_model.objects.create(**{f"field_{linked_primary.id}": "Row A"})

    model = table.get_model()
    getattr(model.objects.create(), field.db_column).set([linked.id])

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    group = _get_only_page(response)["groups"][0]
    assert group["path"][f"field_{field.id}"] == [linked.id]
    assert group["display"][f"field_{field.id}"] == [
        {"id": linked.id, "value": "Row A"}
    ]


@pytest.mark.django_db
def test_group_by_data_includes_single_select_display_values(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_single_select_field(table=table, name="Status")
    option = data_fixture.create_select_option(
        field=field, value="Open", color="blue", order=0
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=field)

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}_id": option.id})

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    group = _get_only_page(response)["groups"][0]
    assert group["path"][f"field_{field.id}"] == option.id
    assert group["display"][f"field_{field.id}"] == {
        "id": option.id,
        "value": "Open",
        "color": "blue",
    }


@pytest.mark.django_db
def test_group_by_data_includes_multiple_select_display_values(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_multiple_select_field(table=table, name="Tags")
    option = data_fixture.create_select_option(
        field=field, value="Red", color="red", order=0
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=field)

    model = table.get_model()
    getattr(model.objects.create(), field.db_column).set([option.id])

    url = reverse("api:database:views:grid:group-by-data", kwargs={"view_id": grid.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    group = _get_only_page(response)["groups"][0]
    assert group["path"][f"field_{field.id}"] == [option.id]
    assert group["display"][f"field_{field.id}"] == [
        {"id": option.id, "value": "Red", "color": "red"}
    ]
