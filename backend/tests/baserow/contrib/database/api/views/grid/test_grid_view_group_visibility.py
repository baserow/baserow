import json

from django.db.models import Q
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.api.views.grid.group_visibility import (
    build_group_visibility_paths_q,
    parse_group_visibility_paths,
)


def test_parse_group_visibility_paths_valid_json():
    raw = '[{"field_1": "Alice"}, {"field_1": "Bob", "field_2": 42}]'
    assert parse_group_visibility_paths(raw) == [
        {"field_1": "Alice"},
        {"field_1": "Bob", "field_2": 42},
    ]


@pytest.mark.parametrize("raw", ["", None, "not json", '{"field_1": "Alice"}'])
def test_parse_group_visibility_paths_invalid_payloads(raw):
    assert parse_group_visibility_paths(raw) == []


def test_parse_group_visibility_paths_mixed_valid_and_invalid():
    raw = '[{"field_1": "Alice"}, "bad", {"field_2": 42}]'
    assert parse_group_visibility_paths(raw) == [
        {"field_1": "Alice"},
        {"field_2": 42},
    ]


@pytest.mark.django_db
def test_build_group_visibility_paths_q_single_group(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    row_red = model.objects.create(**{f"field_{text_field.id}": "Red"})
    row_blue = model.objects.create(**{f"field_{text_field.id}": "Blue"})

    base_qs = model.objects.all()
    q = build_group_visibility_paths_q(
        [text_field], [{f"field_{text_field.id}": "Green"}], base_qs
    )

    assert list(base_qs.exclude(q).values_list("id", flat=True)) == [
        row_red.id,
        row_blue.id,
    ]


@pytest.mark.django_db
def test_build_group_visibility_paths_q_nested_groups(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    number_field = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )

    model = table.get_model()
    row_g10 = model.objects.create(
        **{f"field_{text_field.id}": "Green", f"field_{number_field.id}": 10}
    )
    row_g20 = model.objects.create(
        **{f"field_{text_field.id}": "Green", f"field_{number_field.id}": 20}
    )
    row_r10 = model.objects.create(
        **{f"field_{text_field.id}": "Red", f"field_{number_field.id}": 10}
    )

    base_qs = model.objects.all()
    q = build_group_visibility_paths_q(
        [text_field, number_field],
        [{f"field_{text_field.id}": "Green"}],
        base_qs,
    )
    assert list(base_qs.exclude(q).values_list("id", flat=True)) == [row_r10.id]

    q = build_group_visibility_paths_q(
        [text_field, number_field],
        [{f"field_{text_field.id}": "Green", f"field_{number_field.id}": "10"}],
        base_qs,
    )
    assert set(base_qs.exclude(q).values_list("id", flat=True)) == {
        row_g20.id,
        row_r10.id,
    }
    assert row_g10.id not in set(base_qs.exclude(q).values_list("id", flat=True))


@pytest.mark.django_db
def test_build_group_visibility_paths_q_empty_paths(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})

    q = build_group_visibility_paths_q([text_field], [], model.objects.all())

    assert q == Q()
    assert model.objects.exclude(q).count() == 1


@pytest.mark.django_db
def test_grid_view_list_rows_with_group_visibility_paths(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Red"})

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    visibility_paths = json.dumps([{f"field_{text_field.id}": "Green"}])
    response = api_client.get(
        url,
        {"group_visibility_paths": visibility_paths},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0][f"field_{text_field.id}"] == "Red"


@pytest.mark.django_db
def test_grid_view_list_rows_with_collapse_all_mode(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Red"})

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {"group_visibility_mode": "collapse"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 0
    assert response_json["results"] == []


@pytest.mark.django_db
def test_grid_view_list_rows_with_collapse_all_mode_and_expanded_group(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    green_1 = model.objects.create(**{f"field_{text_field.id}": "Green"})
    green_2 = model.objects.create(**{f"field_{text_field.id}": "Green"})
    red = model.objects.create(**{f"field_{text_field.id}": "Red"})

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    expanded = json.dumps([{f"field_{text_field.id}": "Green"}])
    response = api_client.get(
        url,
        {
            "group_visibility_paths": expanded,
            "group_visibility_mode": "collapse",
            "limit": 10,
            "offset": 0,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 2
    assert [row["id"] for row in response_json["results"]] == [
        green_1.id,
        green_2.id,
    ]
    assert red.id not in [row["id"] for row in response_json["results"]]
