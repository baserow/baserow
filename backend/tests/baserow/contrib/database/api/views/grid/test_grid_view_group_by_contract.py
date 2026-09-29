"""The rows and group-tree APIs must agree on omitted, empty and ad-hoc grouping."""

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK


@pytest.fixture
def grouped_grid(data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    group = data_fixture.create_text_field(table=table, name="Group", primary=True)
    category = data_fixture.create_text_field(table=table, name="Category")
    rank = data_fixture.create_number_field(table=table, name="Rank")
    view = data_fixture.create_grid_view(table=table, public=True)
    data_fixture.create_view_group_by(view=view, field=group, order="ASC")
    data_fixture.create_view_sort(view=view, field=rank, order="DESC")

    model = table.get_model()
    rows = [
        model.objects.create(
            order=index,
            **{group.db_column: value, category.db_column: label, rank.db_column: n},
        )
        for index, (value, label, n) in enumerate(
            [("B", "X", 2), ("A", "X", 3), ("B", "Y", 4), ("A", "X", 1)]
        )
    ]
    return view, token, group, category, rank, rows


def _options(group_mode, sort_mode, category, rank):
    options = {}
    if group_mode != "inherit":
        options["group_by"] = "" if group_mode == "clear" else f"-{category.db_column}"
    if sort_mode != "inherit":
        options["order_by"] = "" if sort_mode == "clear" else rank.db_column
    return options


def _endpoint(view, token, public, *, group_data=False):
    if public:
        name = "public-group-by-data" if group_data else "public_rows"
        return (
            reverse(f"api:database:views:grid:{name}", kwargs={"slug": view.slug}),
            {},
        )
    name = "group-by-data" if group_data else "list"
    return (
        reverse(f"api:database:views:grid:{name}", kwargs={"view_id": view.id}),
        {"HTTP_AUTHORIZATION": f"JWT {token}"},
    )


# Explicit expected row positions avoid reproducing the implementation's sort logic.
EXPECTED_ORDER = {
    ("inherit", "inherit"): [1, 3, 2, 0],
    ("inherit", "clear"): [1, 3, 0, 2],
    ("inherit", "replace"): [3, 1, 0, 2],
    ("clear", "inherit"): [2, 1, 0, 3],
    ("clear", "clear"): [0, 1, 2, 3],
    ("clear", "replace"): [3, 0, 1, 2],
    ("replace", "inherit"): [2, 1, 0, 3],
    ("replace", "clear"): [2, 0, 1, 3],
    ("replace", "replace"): [2, 3, 0, 1],
}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "public,group_mode,sort_mode",
    [
        pytest.param(
            public, group_mode, sort_mode, id=f"{scope}-{group_mode}-{sort_mode}"
        )
        for public, scope in [(False, "private"), (True, "public")]
        for group_mode in ["inherit", "clear", "replace"]
        for sort_mode in ["inherit", "clear", "replace"]
        # The public UI supplies an ordering option. The both-omitted public path
        # has a separate baseline defect outside these PR regression cases.
        if not (public and group_mode == sort_mode == "inherit")
    ],
)
def test_rows_keep_grouping_and_sorting_overrides_independent(
    grouped_grid, api_client, public, group_mode, sort_mode
):
    view, token, _, category, rank, rows = grouped_grid
    url, headers = _endpoint(view, token, public)
    options = _options(group_mode, sort_mode, category, rank)

    response = api_client.get(url, options, **headers)

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["count"] == 4
    assert [row["id"] for row in response.json()["results"]] == [
        rows[index].id for index in EXPECTED_ORDER[group_mode, sort_mode]
    ]
    # Fetching ad-hoc results must not rewrite the saved view configuration.
    assert list(view.viewgroupby_set.values_list("field_id", "order")) == [
        (grouped_grid[2].id, "ASC")
    ]
    assert list(view.viewsort_set.values_list("field_id", "order")) == [
        (rank.id, "DESC")
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("public", [False, True], ids=["private", "public"])
@pytest.mark.parametrize("group_mode", ["inherit", "clear", "replace"])
def test_group_tree_distinguishes_omitted_empty_and_replacement_group_by(
    grouped_grid, api_client, public, group_mode
):
    view, token, group, category, rank, _ = grouped_grid
    url, headers = _endpoint(view, token, public, group_data=True)
    options = _options(group_mode, "inherit", category, rank)

    response = api_client.get(url, {**options, "limit": 10}, **headers)

    assert response.status_code == HTTP_200_OK, response.json()
    pages = response.json()["pages"]
    assert len(pages) == 1
    page = pages[0]
    assert page["parent"] == {}
    if group_mode == "clear":
        assert page["groups"] == [], (
            "group_by= explicitly clears grouping; the group tree must not fall "
            "back to the saved view while the rows endpoint returns ungrouped rows."
        )
        assert page["group_count"] == 0
        return

    field = group if group_mode == "inherit" else category
    values_and_counts = (
        [("A", 2), ("B", 2)]
        if group_mode == "inherit"
        else [
            ("Y", 1),
            ("X", 3),
        ]
    )
    expected_groups = [
        {
            "path": {field.db_column: value},
            "depth": 0,
            "row_count": count,
            "sibling_index": index,
            "row_offset": 0 if index == 0 else values_and_counts[0][1],
        }
        for index, (value, count) in enumerate(values_and_counts)
    ]
    assert page == {
        "parent": {},
        "groups": expected_groups,
        "offset": 0,
        "limit": 10,
        "group_count": 2,
    }

    response = api_client.get(url, {**options, "offset": 1, "limit": 1}, **headers)

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["pages"] == [
        {
            "parent": {},
            "groups": expected_groups[1:],
            "offset": 1,
            "limit": 1,
            "group_count": 2,
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("group_mode", ["inherit", "clear", "replace"])
def test_private_row_group_metadata_uses_the_effective_grouping(
    grouped_grid, api_client, group_mode
):
    view, token, group, category, rank, _ = grouped_grid
    url, headers = _endpoint(view, token, False)
    options = _options(group_mode, "inherit", category, rank)

    response = api_client.get(
        url, {**options, "include": "group_by_metadata"}, **headers
    )

    assert response.status_code == HTTP_200_OK, response.json()
    metadata = response.json().get("group_by_metadata", {})
    if group_mode == "clear":
        assert metadata == {}, "Cleared grouping must not return saved group metadata."
        return

    field = group if group_mode == "inherit" else category
    expected_counts = {"A": 2, "B": 2} if group_mode == "inherit" else {"X": 3, "Y": 1}
    assert set(metadata) == {field.db_column}
    assert len(metadata[field.db_column]) == 2
    assert {
        entry[field.db_column]: entry["count"] for entry in metadata[field.db_column]
    } == expected_counts


@pytest.mark.django_db
def test_private_rows_saved_group_by_metadata_excludes_hidden_fields(
    api_client, data_fixture
):
    """
    When hidden_field_ids is non-None (enterprise restricted view), saved
    group-bys on hidden fields must not leak in group_by_metadata on the
    private rows endpoint.
    """

    from unittest.mock import patch

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    visible = data_fixture.create_text_field(table=table, name="Visible")
    hidden = data_fixture.create_text_field(table=table, name="Hidden")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=visible)
    data_fixture.create_view_group_by(view=grid, field=hidden)

    model = table.get_model()
    model.objects.create(**{f"field_{visible.id}": "A", f"field_{hidden.id}": "secret"})

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})

    with patch(
        "baserow.contrib.database.api.views.grid.views.get_hidden_field_ids_for_view_user",
        return_value={hidden.id},
    ):
        response = api_client.get(
            url,
            {"include": "group_by_metadata"},
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    metadata = response.json().get("group_by_metadata", {})
    assert visible.db_column in metadata, "Visible group-by must appear in metadata."
    assert hidden.db_column not in metadata, (
        "Hidden group-by must NOT appear in metadata."
    )
