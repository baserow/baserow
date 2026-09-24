from itertools import product

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler

REQUEST_MODES = ["private_saved", "private_adhoc", "public_explicit"]
SELECTIONS = [(), (0,), (1,), (0, 1), (1, 0), (0, 2), (2, 0), (0, 1, 2)]


def _configure_ordering(data_fixture, view, groups, sorts, mode):
    """Public grids send the displayed rules explicitly, including saved rules."""
    if mode != "private_adhoc":
        for field, direction in groups:
            data_fixture.create_view_group_by(view=view, field=field, order=direction)
        for field, direction in sorts:
            data_fixture.create_view_sort(view=view, field=field, order=direction)

    def serialize(rules):
        return ",".join(
            ("-" if direction == "DESC" else "") + field.db_column
            for field, direction in rules
        )

    if mode == "private_saved":
        return {}
    return {"group_by": serialize(groups), "order_by": serialize(sorts)}


def _grid_urls_and_auth(view, token, mode):
    if mode == "public_explicit":
        return (
            reverse("api:database:views:grid:public_rows", kwargs={"slug": view.slug}),
            reverse(
                "api:database:views:grid:public-group-by-data",
                kwargs={"slug": view.slug},
            ),
            {},
        )
    return (
        reverse("api:database:views:grid:list", kwargs={"view_id": view.id}),
        reverse("api:database:views:grid:group-by-data", kwargs={"view_id": view.id}),
        {"HTTP_AUTHORIZATION": f"JWT {token}"},
    )


def _get_json(api_client, url, params, auth):
    response = api_client.get(url, params, **auth)
    assert response.status_code == HTTP_200_OK, response.content
    return response.json()


def _create_selection_matrix(data_fixture, user, table, field_kind="multiple_select"):
    fields = [
        getattr(data_fixture, f"create_{field_kind}_field")(
            table=table, name=f"Selections {index}"
        )
        for index in range(2)
    ]
    if field_kind == "multiple_select":
        options = [
            [
                data_fixture.create_select_option(
                    field=field, value=name, order=index
                ).id
                for index, name in enumerate("ABC")
            ]
            for field in fields
        ]
    else:
        collaborators = [
            data_fixture.create_user(
                workspace=table.database.workspace, first_name=name
            ).id
            for name in "ABC"
        ]
        options = [collaborators, collaborators]
    model = table.get_model()
    selections_by_row = {}
    for selections in product(SELECTIONS, repeat=2):
        # RowHandler preserves the user-selected order in the through table. A bare
        # many-to-many .set() does not provide that fixture guarantee.
        row = RowHandler().create_row(
            user,
            table,
            values={
                field.db_column: [choices[index] for index in selected]
                for field, choices, selected in zip(fields, options, selections)
            },
            model=model,
        )
        selections_by_row[row.id] = selections
    return fields, model, selections_by_row


def _expected_selection_order(selections_by_row, groups, sorts, separator=","):
    """Independent oracle: group by sets, sort by the ordered selection labels.

    Only ASCII A/B/C labels and option orders 0/1/2 are used, so the expected
    ordering does not depend on locale. No production ordering hook, queryset
    annotation, or previously sorted queryset supplies the expected result.
    """
    result = list(selections_by_row)
    streams = [("group", *rule) for rule in groups] + [
        ("sort", *rule) for rule in sorts
    ]
    for stream, field_index, direction in reversed(streams):

        def key(row_id):
            selected = selections_by_row[row_id][field_index]
            if stream == "group":
                return tuple(sorted(selected))
            return separator.join("ABC"[index] for index in selected)

        # Stable passes retain row insertion order for equal keys and allow each
        # stream to have its own direction.
        result.sort(key=key, reverse=direction == "DESC")
    return result


@pytest.mark.django_db
@pytest.mark.parametrize("mode", REQUEST_MODES)
@pytest.mark.parametrize("field_kind", ["multiple_select", "multiple_collaborators"])
@pytest.mark.parametrize("direction", ["ASC", "DESC"])
def test_m2m_group_and_sort_rows_match_group_offsets(
    api_client, data_fixture, mode, field_kind, direction
):
    """An unrelated M2M sort must not split the same logical group in two."""
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    group_field = getattr(data_fixture, f"create_{field_kind}_field")(table=table)
    sort_field = data_fixture.create_multiple_select_field(table=table)
    included = data_fixture.create_boolean_field(table=table, name="Included")
    if field_kind == "multiple_select":
        group_ids = [
            data_fixture.create_select_option(
                field=group_field, value=name, order=index
            ).id
            for index, name in enumerate("ABC")
        ]
    else:
        group_ids = [
            data_fixture.create_user(
                workspace=table.database.workspace, first_name=name
            ).id
            for name in "ABC"
        ]
    sort_ids = [
        data_fixture.create_select_option(field=sort_field, value=name, order=index).id
        for index, name in enumerate("XY")
    ]
    view = data_fixture.create_grid_view(table=table, public=True)
    data_fixture.create_view_filter(
        view=view, field=included, type="boolean", value="true"
    )
    params = _configure_ordering(
        data_fixture,
        view,
        [(group_field, direction)],
        [(sort_field, direction)],
        mode,
    )
    model = table.get_model()
    rows = [
        RowHandler().create_row(
            user,
            table,
            values={
                group_field.db_column: [group_ids[index] for index in group],
                sort_field.db_column: [sort_ids[index] for index in sort],
                included.db_column: True,
            },
            model=model,
        )
        for group, sort in [((0, 2), (0, 1)), ((0, 1), (0,)), ((2, 0), (1,))]
    ]
    # Both row and group endpoints must apply the saved view filter before
    # calculating counts or offsets, including for ad-hoc and public requests.
    excluded = RowHandler().create_row(
        user,
        table,
        values={
            group_field.db_column: [group_ids[0]],
            sort_field.db_column: sort_ids,
            included.db_column: False,
        },
        model=model,
    )
    # AB sorts before AC. The AC and CA selections are one group, with XY
    # preceding Y inside that group. Different sort cardinalities (2/1/1) expose
    # join multiplication; using B instead of AB as the other group hides it.
    expected_ids = [
        rows[index].id for index in ([1, 0, 2] if direction == "ASC" else [2, 0, 1])
    ]
    ab, ac = [group_ids[0], group_ids[1]], [group_ids[0], group_ids[2]]
    expected_groups = (
        [(ab, 1, 0), (ac, 2, 1)] if direction == "ASC" else [(ac, 2, 0), (ab, 1, 2)]
    )
    rows_url, groups_url, auth = _grid_urls_and_auth(view, token, mode)
    group_data = _get_json(api_client, groups_url, params, auth)
    assert len(group_data["pages"]) == 1
    page = group_data["pages"][0]
    assert page["group_count"] == 2
    assert [
        (group["path"][group_field.db_column], group["row_count"], group["row_offset"])
        for group in page["groups"]
    ] == expected_groups

    response = _get_json(
        api_client, rows_url, {**params, "include": "group_by_metadata"}, auth
    )
    assert response["count"] == 3
    assert excluded.id not in [row["id"] for row in response["results"]]
    assert [row["id"] for row in response["results"]] == expected_ids
    assert sorted(
        (entry[group_field.db_column], entry["count"])
        for entry in response["group_by_metadata"][group_field.db_column]
    ) == [(ab, 1), (ac, 2)]

    # The virtual grid loads rows at these offsets. Matching group counts alone
    # cannot catch rows disappearing when a group occupies nonadjacent positions.
    for _, row_count, row_offset in expected_groups:
        window = _get_json(
            api_client,
            rows_url,
            {**params, "offset": row_offset, "limit": row_count},
            auth,
        )
        assert window["count"] == 3
        assert [row["id"] for row in window["results"]] == expected_ids[
            row_offset : row_offset + row_count
        ]
    paginated_ids = []
    for offset in range(3):
        window = _get_json(
            api_client, rows_url, {**params, "offset": offset, "limit": 1}, auth
        )
        paginated_ids.extend(row["id"] for row in window["results"])
    assert paginated_ids == expected_ids


@pytest.mark.django_db
@pytest.mark.parametrize("mode", REQUEST_MODES)
@pytest.mark.parametrize("direction", ["ASC", "DESC"])
def test_grouping_same_m2m_field_preserves_selection_order_sort(
    api_client, data_fixture, mode, direction
):
    """Adding grouping must not reorder unchanged AB/BA and AC/CA sort keys."""
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    fields, _, selections = _create_selection_matrix(data_fixture, user, table)
    view = data_fixture.create_grid_view(table=table, public=True)
    params = _configure_ordering(
        data_fixture, view, [(fields[0], "ASC")], [(fields[0], direction)], mode
    )
    rows_url, _, auth = _grid_urls_and_auth(view, token, mode)

    # The 64 real rows exercise empty selections, equal keys, reversed selections,
    # and different cardinalities. A four-row AB/BA example can pass accidentally
    # because an unordered aggregate happens to read its inputs in insertion order.
    response = _get_json(api_client, rows_url, {**params, "size": 100}, auth)
    assert response["count"] == 64
    assert [row["id"] for row in response["results"]] == _expected_selection_order(
        selections, [(0, "ASC")], [(0, direction)]
    )


@pytest.mark.django_db
@pytest.mark.parametrize("persisted", [False, True], ids=["adhoc", "saved"])
@pytest.mark.parametrize(
    "groups,sorts",
    [
        ([(0, "ASC"), (1, "DESC")], []),
        ([], [(0, "DESC"), (1, "ASC")]),
        ([(0, "ASC")], [(0, "DESC"), (1, "ASC")]),
        ([(0, "DESC"), (1, "ASC")], [(0, "ASC"), (1, "DESC")]),
    ],
    ids=["two_groups", "two_sorts", "shared_field_and_second_sort", "both_streams"],
)
def test_multiple_m2m_ordering_streams_keep_independent_keys(
    data_fixture, persisted, groups, sorts
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    fields, model, selections = _create_selection_matrix(data_fixture, user, table)
    view = data_fixture.create_grid_view(table=table)
    params = _configure_ordering(
        data_fixture,
        view,
        [(fields[index], direction) for index, direction in groups],
        [(fields[index], direction) for index, direction in sorts],
        "private_saved" if persisted else "private_adhoc",
    )
    queryset = model.objects.all()
    if persisted:
        queryset = ViewHandler().apply_ordering(view, queryset)
    else:
        queryset = queryset.order_by_fields_string(
            params["order_by"], group_by_string=params["group_by"]
        )

    assert [row.id for row in queryset] == _expected_selection_order(
        selections, groups, sorts
    )


@pytest.mark.django_db
@pytest.mark.parametrize("persisted", [False, True], ids=["adhoc", "saved"])
@pytest.mark.parametrize("direction", ["ASC", "DESC"])
def test_grouping_collaborators_preserves_selection_order_sort(
    data_fixture, persisted, direction
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    fields, model, selections = _create_selection_matrix(
        data_fixture, user, table, field_kind="multiple_collaborators"
    )
    view = data_fixture.create_grid_view(table=table)
    params = _configure_ordering(
        data_fixture,
        view,
        [(fields[0], "ASC")],
        [(fields[0], direction)],
        "private_saved" if persisted else "private_adhoc",
    )
    queryset = model.objects.all()
    if persisted:
        queryset = ViewHandler().apply_ordering(view, queryset)
    else:
        queryset = queryset.order_by_fields_string(
            params["order_by"], group_by_string=params["group_by"]
        )
    # Collaborator sorting concatenates names without the comma used by multiple
    # select. Grouping still treats reversed selections as the same set.
    assert [row.id for row in queryset] == _expected_selection_order(
        selections, [(0, "ASC")], [(0, direction)], separator=""
    )
