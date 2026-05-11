import json

from django.db.models import Q
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.api.views.grid.collapsed_groups import (
    build_collapsed_groups_exclusion_q,
    parse_collapsed_groups,
)
from baserow.contrib.database.views.handler import ViewHandler


def test_parse_collapsed_groups_valid_json():
    raw = '[{"field_1": "Alice"}, {"field_1": "Bob", "field_2": 42}]'
    assert parse_collapsed_groups(raw) == [
        {"field_1": "Alice"},
        {"field_1": "Bob", "field_2": 42},
    ]


@pytest.mark.parametrize("raw", ["", None, "not json", '{"field_1": "Alice"}'])
def test_parse_collapsed_groups_invalid_payloads(raw):
    assert parse_collapsed_groups(raw) == []


def test_parse_collapsed_groups_list_with_non_dict():
    assert parse_collapsed_groups("[1, 2, 3]") == []


def test_parse_collapsed_groups_mixed_valid_and_invalid():
    raw = '[{"field_1": "Alice"}, "bad", {"field_2": 42}]'
    assert parse_collapsed_groups(raw) == [{"field_1": "Alice"}, {"field_2": 42}]


@pytest.mark.django_db
def test_build_exclusion_q_single_group(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    row_red = model.objects.create(**{f"field_{text_field.id}": "Red"})
    row_blue = model.objects.create(**{f"field_{text_field.id}": "Blue"})

    base_qs = model.objects.all()
    q = build_collapsed_groups_exclusion_q(
        [text_field], [{f"field_{text_field.id}": "Green"}], base_qs
    )

    assert list(base_qs.exclude(q).values_list("id", flat=True)) == [
        row_red.id,
        row_blue.id,
    ]


@pytest.mark.django_db
def test_build_exclusion_q_nested_groups(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    number_field = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)
    data_fixture.create_view_group_by(view=grid, field=number_field)

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
    q = build_collapsed_groups_exclusion_q(
        [text_field, number_field],
        [{f"field_{text_field.id}": "Green"}],
        base_qs,
    )
    assert list(base_qs.exclude(q).values_list("id", flat=True)) == [row_r10.id]

    q = build_collapsed_groups_exclusion_q(
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
def test_build_exclusion_q_empty_collapsed(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})

    q = build_collapsed_groups_exclusion_q([text_field], [], model.objects.all())

    assert q == Q()
    assert model.objects.exclude(q).count() == 1


@pytest.mark.django_db
def test_metadata_includes_collapsed_group_counts(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Red"})

    result = ViewHandler().get_group_by_metadata_in_rows(
        [text_field],
        list(model.objects.filter(**{f"field_{text_field.id}": "Red"})),
        model.objects.all(),
        collapsed_group_values=[{f"field_{text_field.id}": "Green"}],
    )

    values = {
        entry[f"field_{text_field.id}"]: entry["count"] for entry in result[text_field]
    }
    assert values == {"Green": 2, "Red": 1}


@pytest.mark.django_db
def test_grid_view_list_rows_with_collapsed_groups(api_client, data_fixture):
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
    collapsed = json.dumps([{f"field_{text_field.id}": "Green"}])
    response = api_client.get(
        url, {"collapsed_groups": collapsed}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0][f"field_{text_field.id}"] == "Red"
    # The row endpoint no longer ships group_by_metadata — header rendering
    # is driven by the /group-tree/ endpoint.
    assert "group_by_metadata" not in response_json


@pytest.mark.django_db
def test_public_grid_view_rows_with_collapsed_groups(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table, public=True)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Red"})

    url = reverse("api:database:views:grid:public_rows", kwargs={"slug": grid.slug})
    collapsed = json.dumps([{f"field_{text_field.id}": "Green"}])
    response = api_client.get(
        url,
        {
            "group_by": f"field_{text_field.id}",
            "collapsed_groups": collapsed,
        },
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert "group_by_metadata" not in response_json
