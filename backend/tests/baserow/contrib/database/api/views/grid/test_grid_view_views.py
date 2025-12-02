import json
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import patch

from django.core.cache import cache
from django.shortcuts import reverse

import pytest
from pytest_unordered import unordered
from rest_framework import serializers
from rest_framework.fields import Field
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.registries import (
    RowMetadataType,
    row_metadata_registry,
)
from baserow.contrib.database.search.handler import ALL_SEARCH_MODES
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import TableModelQuerySet
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import GridView
from baserow.contrib.database.views.registries import view_aggregation_type_registry
from baserow.test_utils.helpers import register_instance_temporarily


@pytest.mark.django_db
def test_list_rows(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    grid = data_fixture.create_grid_view(table=table)
    grid_2 = data_fixture.create_grid_view()

    model = grid.table.get_model()
    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": False,
        }
    )
    row_2 = model.objects.create()
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{number_field.id}": 100,
            f"field_{boolean_field.id}": True,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{text_field.id}": "Purple",
            f"field_{number_field.id}": 1000,
            f"field_{boolean_field.id}": False,
        }
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": 999})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GRID_DOES_NOT_EXIST"

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_2.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert not response_json["previous"]
    assert not response_json["next"]
    assert len(response_json["results"]) == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][0][f"field_{text_field.id}"] == "Green"
    assert response_json["results"][0][f"field_{number_field.id}"] == "10"
    assert not response_json["results"][0][f"field_{boolean_field.id}"]
    assert response_json["results"][1]["id"] == row_2.id
    assert response_json["results"][2]["id"] == row_3.id
    assert response_json["results"][3]["id"] == row_4.id

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"size": 2}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert not response_json["previous"]
    assert response_json["next"]
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_2.id

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"size": 2, "page": 2}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["previous"]
    assert not response_json["next"]
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_3.id
    assert response_json["results"][1]["id"] == row_4.id

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"size": 2, "page": 999}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["results"] == []

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"limit": 2}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_2.id
    assert "field_options" not in response_json

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"limit": 1, "offset": 2}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_3.id

    sort = data_fixture.create_view_sort(view=grid, field=text_field, order="ASC")
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_3.id
    assert response_json["results"][2]["id"] == row_4.id
    assert response_json["results"][3]["id"] == row_2.id
    sort.delete()

    view_filter = data_fixture.create_view_filter(
        view=grid, field=text_field, value="Green"
    )
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_1.id
    view_filter.delete()

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, data={"count": ""}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response_json["count"] == 4
    assert len(response_json.keys()) == 1

    row_1.delete()
    row_2.delete()
    row_3.delete()
    row_4.delete()

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 0
    assert not response_json["previous"]
    assert not response_json["next"]
    assert len(response_json["results"]) == 0

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    data_fixture.create_template(workspace=grid.table.database.workspace)
    grid.table.database.workspace.has_template.cache_clear()
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_list_rows_with_group_by(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower", number_decimal_places=1
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)
    data_fixture.create_view_group_by(view=grid, field=number_field)
    data_fixture.create_view_group_by(view=grid, field=boolean_field)

    model = grid.table.get_model()
    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": False,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": False,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": True,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 20,
            f"field_{boolean_field.id}": True,
        }
    )
    row_5 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 20,
            f"field_{boolean_field.id}": True,
        }
    )
    row_6 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 20,
            f"field_{boolean_field.id}": True,
        }
    )
    row_7 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": True,
        }
    )
    row_8 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{number_field.id}": 30,
            f"field_{boolean_field.id}": True,
        }
    )
    row_9 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{number_field.id}": 40,
            f"field_{boolean_field.id}": True,
        }
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()

    assert response_json["group_by_metadata"] == {
        f"field_{text_field.id}": unordered(
            [
                {f"field_{text_field.id}": "Green", "count": 6},
                {f"field_{text_field.id}": "Orange", "count": 3},
            ]
        ),
        f"field_{number_field.id}": unordered(
            [
                {
                    f"field_{text_field.id}": "Green",
                    f"field_{number_field.id}": "10.0",
                    f"count": 3,
                },
                {
                    f"field_{text_field.id}": "Green",
                    f"field_{number_field.id}": "20.0",
                    f"count": 3,
                },
                {
                    f"field_{text_field.id}": "Orange",
                    f"field_{number_field.id}": "10.0",
                    f"count": 1,
                },
                {
                    f"field_{text_field.id}": "Orange",
                    f"field_{number_field.id}": "30.0",
                    f"count": 1,
                },
                {
                    f"field_{text_field.id}": "Orange",
                    f"field_{number_field.id}": "40.0",
                    f"count": 1,
                },
            ]
        ),
        f"field_{boolean_field.id}": unordered(
            [
                {
                    f"field_{text_field.id}": "Orange",
                    f"field_{number_field.id}": "10.0",
                    f"field_{boolean_field.id}": True,
                    f"count": 1,
                },
                {
                    f"field_{text_field.id}": "Green",
                    f"field_{number_field.id}": "10.0",
                    f"field_{boolean_field.id}": True,
                    f"count": 1,
                },
                {
                    f"field_{text_field.id}": "Green",
                    f"field_{number_field.id}": "20.0",
                    f"field_{boolean_field.id}": True,
                    f"count": 3,
                },
                {
                    f"field_{text_field.id}": "Green",
                    f"field_{number_field.id}": "10.0",
                    f"field_{boolean_field.id}": False,
                    f"count": 2,
                },
                {
                    f"field_{text_field.id}": "Orange",
                    f"field_{number_field.id}": "30.0",
                    f"field_{boolean_field.id}": True,
                    f"count": 1,
                },
                {
                    f"field_{text_field.id}": "Orange",
                    f"field_{number_field.id}": "40.0",
                    f"field_{boolean_field.id}": True,
                    f"count": 1,
                },
            ]
        ),
    }


@pytest.mark.django_db
def test_list_rows_with_group_by_with_filter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)
    data_fixture.create_view_filter(
        view=grid, field=boolean_field, type="boolean", value="false"
    )

    model = grid.table.get_model()
    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{boolean_field.id}": False,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{boolean_field.id}": False,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{boolean_field.id}": True,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{boolean_field.id}": True,
        }
    )
    row_5 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{boolean_field.id}": True,
        }
    )
    row_6 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{boolean_field.id}": True,
        }
    )
    row_7 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{boolean_field.id}": False,
        }
    )
    row_8 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{boolean_field.id}": True,
        }
    )
    row_9 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{boolean_field.id}": True,
        }
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()

    assert response_json["group_by_metadata"] == {
        f"field_{text_field.id}": unordered(
            [
                {f"field_{text_field.id}": "Green", "count": 2},
                {f"field_{text_field.id}": "Orange", "count": 1},
            ]
        )
    }


@pytest.mark.django_db
def test_list_rows_include_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    grid = data_fixture.create_grid_view(table=table)

    # The second field is deliberately created after the creation of the grid field
    # so that the GridViewFieldOptions entry is not created. This should
    # automatically be created when the page is fetched.
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "field_options" not in response_json

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url, {"include": "field_options"}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 2
    assert response_json["field_options"][str(text_field.id)]["width"] == 200
    assert response_json["field_options"][str(text_field.id)]["hidden"] is False
    assert response_json["field_options"][str(text_field.id)]["order"] == 32767
    assert response_json["field_options"][str(number_field.id)]["width"] == 200
    assert response_json["field_options"][str(number_field.id)]["hidden"] is False
    assert response_json["field_options"][str(number_field.id)]["order"] == 32767
    assert "filters_disabled" not in response_json


@pytest.mark.django_db
def test_list_rows_include_row_metadata(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(
        name="test", table=table, order=0, text_default="white"
    )
    grid = data_fixture.create_grid_view(table=table)
    model = table.get_model(attribute_names=True)
    row = model.objects.create(test="test")

    class ExampleRowMetadata(RowMetadataType):
        type = "test_example_row_metadata"

        def generate_metadata_for_rows(
            self, user, table, row_ids: List[int]
        ) -> Dict[int, Any]:
            return {row_id: row_id for row_id in row_ids}

        def get_example_serializer_field(self) -> Field:
            return serializers.CharField()

    with register_instance_temporarily(row_metadata_registry, ExampleRowMetadata()):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
        response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert "row_metadata" not in response_json

        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
        response = api_client.get(
            url, {"include": "row_metadata"}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert response_json["row_metadata"] == {
            str(row.id): {"test_example_row_metadata": row.id}
        }


@pytest.mark.django_db
def test_list_filtered_rows(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    grid = data_fixture.create_grid_view(table=table)
    grid_2 = data_fixture.create_grid_view()

    url = reverse("api:database:views:grid:list", kwargs={"view_id": 999})
    response = api_client.post(
        url,
        {"field_ids": [1], "row_ids": [1]},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GRID_DOES_NOT_EXIST"

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_2.id})
    response = api_client.post(
        url,
        {"field_ids": [1], "row_ids": [1]},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.post(url, {}, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.post(
        url,
        {"field_ids": ["a", "b"], "row_ids": ["a", "b"]},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]["field_ids"]) == 2
    assert len(response_json["detail"]["row_ids"]) == 2

    model = grid.table.get_model()
    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": False,
        }
    )
    row_2 = model.objects.create()
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{number_field.id}": 100,
            f"field_{boolean_field.id}": True,
        }
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "Purple",
            f"field_{number_field.id}": 1000,
            f"field_{boolean_field.id}": False,
        }
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.post(
        url,
        {"field_ids": [text_field.id], "row_ids": [row_1.id, row_2.id]},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert len(response_json) == 2
    assert response_json[0]["id"] == row_1.id
    assert f"field_{text_field.id}" in response_json[0]
    assert response_json[1]["id"] == row_2.id
    assert f"field_{text_field.id}" in response_json[1]

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.post(
        url,
        {"field_ids": [number_field.id, boolean_field.id], "row_ids": [row_3.id]},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert len(response_json) == 1
    assert response_json[0]["id"] == row_3.id
    assert f"field_{number_field.id}" in response_json[0]
    assert f"field_{boolean_field.id}" in response_json[0]

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.post(
        url, {"row_ids": [row_3.id]}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert len(response_json) == 1
    assert response_json[0]["id"] == row_3.id
    assert f"field_{text_field.id}" in response_json[0]
    assert f"field_{number_field.id}" in response_json[0]
    assert f"field_{boolean_field.id}" in response_json[0]


@pytest.mark.django_db
def test_field_aggregation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    grid = data_fixture.create_grid_view(table=table)
    grid_2 = data_fixture.create_grid_view()

    table2 = data_fixture.create_database_table(user=user)
    text_field2 = data_fixture.create_text_field(
        table=table2, order=0, name="Color", text_default="white"
    )

    # Test missing grid view
    url = reverse(
        "api:database:views:grid:field-aggregation",
        kwargs={"view_id": 9999, "field_id": text_field.id},
    )
    response = api_client.get(
        url + f"?type=empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GRID_DOES_NOT_EXIST"

    # Test aggregation on missing field
    url = reverse(
        "api:database:views:grid:field-aggregation",
        kwargs={"view_id": grid.id, "field_id": 9999},
    )
    response = api_client.get(
        url + f"?type=empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # Test user not authorized
    url = reverse(
        "api:database:views:grid:field-aggregation",
        kwargs={"view_id": grid_2.id, "field_id": text_field.id},
    )
    response = api_client.get(
        url + f"?type=empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    # Test field not in table
    url = reverse(
        "api:database:views:grid:field-aggregation",
        kwargs={"view_id": grid.id, "field_id": text_field2.id},
    )
    response = api_client.get(
        url + f"?type=empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_FIELD_NOT_IN_TABLE"

    # Test missing auth token
    url = reverse(
        "api:database:views:grid:field-aggregation",
        kwargs={"view_id": grid.id, "field_id": text_field.id},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse(
        "api:database:views:grid:field-aggregation",
        kwargs={"view_id": grid.id, "field_id": text_field.id},
    )

    # Test bad aggregation type
    response = api_client.get(
        url + f"?type=bad_aggregation_type",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AGGREGATION_TYPE_DOES_NOT_EXIST"

    # Test normal response with no data
    response = api_client.get(
        url + f"?type=empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {f"value": 0}

    # Add more data
    model = grid.table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": False,
        }
    )
    model.objects.create()
    model.objects.create(
        **{
            f"field_{text_field.id}": "",
            f"field_{number_field.id}": 0,
            f"field_{boolean_field.id}": False,
        }
    )

    model.objects.create(
        **{
            f"field_{text_field.id}": None,
            f"field_{number_field.id}": 1200,
            f"field_{boolean_field.id}": True,
        }
    )

    # Count empty boolean field
    response = api_client.get(
        url + f"?type=empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json == {f"value": 2}

    url = reverse(
        "api:database:views:grid:field-aggregation",
        kwargs={"view_id": grid.id, "field_id": boolean_field.id},
    )

    # Count not empty "For sale" field
    response = api_client.get(
        url + f"?type=not_empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json == {
        "value": 1,
    }

    # Count with total
    response = api_client.get(
        url + f"?type=not_empty_count&include=total",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json == {"value": 1, "total": 4}

    # Does it work with filter
    data_fixture.create_view_filter(
        view=grid, field=number_field, type="higher_than", value="10"
    )

    # Count with total
    response = api_client.get(
        url + f"?type=not_empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json == {"value": 1}


@pytest.mark.django_db
def test_view_aggregations(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    grid = data_fixture.create_grid_view(table=table)
    grid_2 = data_fixture.create_grid_view()

    # Test missing grid view
    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": 9999},
    )
    response = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GRID_DOES_NOT_EXIST"

    # Test user not authorized
    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid_2.id},
    )
    response = api_client.get(
        url + f"?type=empty_count",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    # Test missing auth token
    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid.id},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid.id},
    )

    # Test normal response with no data and no aggregation
    response = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {}

    field_option1 = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=text_field,
        aggregation_type="",
        aggregation_raw_type="",
    )

    field_option2 = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=number_field,
        aggregation_type="whatever",
        aggregation_raw_type="sum",
    )

    field_option3 = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=boolean_field,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") is None
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") is None
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") is None
    assert (
        cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") is None
    )

    # Test normal response with no data and no cache
    response = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {number_field.db_column: None, boolean_field.db_column: 0}

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": None,
        "version": 1,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") is None
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": 0,
        "version": 1,
    }
    assert (
        cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") is None
    )

    # Test normal response that use cache
    cache.set(
        f"aggregation_value__{grid.id}_{number_field.db_column}",
        {"value": "sentinel", "version": 1},
    )
    cache.set(
        f"aggregation_value__{grid.id}_{boolean_field.db_column}",
        {"value": "sentinel", "version": 1},
    )

    response = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {
        number_field.db_column: "sentinel",
        boolean_field.db_column: "sentinel",
    }

    cache.set(
        f"aggregation_value__{grid.id}_{number_field.db_column}",
        {"value": "sentinel", "version": 1},
    )
    cache.set(
        f"aggregation_value__{grid.id}_{boolean_field.db_column}",
        {"value": "sentinel", "version": 3},
    )
    cache.set(
        f"aggregation_version__{grid.id}_{boolean_field.db_column}",
        3,
    )

    # Add data through the API to trigger cache update
    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": "sentinel",
        "version": 1,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 2
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": "sentinel",
        "version": 3,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 4

    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": "",
            f"field_{number_field.id}": 0,
            f"field_{boolean_field.id}": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": None,
            f"field_{number_field.id}": 1200,
            f"field_{boolean_field.id}": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Test normal response with data
    response = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {number_field.db_column: 1210.0, boolean_field.db_column: 2}

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": 1210.0,
        "version": 4,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 4
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": 2,
        "version": 6,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 6

    # with total
    response = api_client.get(
        url + f"?include=total",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json == {
        number_field.db_column: 1210.0,
        boolean_field.db_column: 2,
        "total": 3,
    }

    # Does it work with filter
    response = api_client.get(
        url + f"?include=total&search=GREE",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    assert response_json == {
        number_field.db_column: 10.0,
        boolean_field.db_column: 0,
        "total": 1,
    }

    # But cache shouldn't be modified after a search as we don't use the cache
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 4
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 6

    # Does it work with filter (use API to trigger cache update)
    response = api_client.post(
        reverse("api:database:views:list_filters", kwargs={"view_id": grid.id}),
        {"field": number_field.id, "type": "higher_than", "value": "10"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    filter_id = response.json()["id"]

    # Cache should be invalidated on filter creation
    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1210),
        "version": 4,
    }
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": 2,
        "version": 6,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 5
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 7

    response = api_client.get(
        url + f"?include=total",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    assert response_json == {
        number_field.db_column: 1200.0,
        boolean_field.db_column: 1,
        "total": 1,
    }

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1200),
        "version": 5,
    }
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": 1,
        "version": 7,
    }

    # Let's update the filter
    api_client.patch(
        reverse("api:database:views:filter_item", kwargs={"view_filter_id": filter_id}),
        {"value": 5},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 6
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 8

    response = api_client.get(
        url + f"?include=total",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    assert response_json == {
        number_field.db_column: 1210.0,
        boolean_field.db_column: 1,
        "total": 2,
    }

    # Cache should also be invalidated on filter deletion
    api_client.delete(
        reverse("api:database:views:filter_item", kwargs={"view_filter_id": filter_id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 7
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 9

    response = api_client.get(
        url + f"?include=total",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    assert response_json == {
        number_field.db_column: 1210.0,
        boolean_field.db_column: 2,
        "total": 3,
    }


@pytest.mark.django_db
def test_view_aggregations_no_adhoc_filtering_uses_view_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    # this filter would filters out all rows
    equal_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="equal", value="y"
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )
    view_handler = ViewHandler()
    view_handler.update_field_options(
        view=grid_view,
        field_options={
            text_field.id: {
                "hidden": False,
                "aggregation_type": "unique_count",
                "aggregation_raw_type": "unique_count",
            }
        },
    )

    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid_view.id},
    )

    # without ad hoc filters the view filter is applied
    response = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {text_field.db_column: 0}


@pytest.mark.django_db
def test_view_aggregations_adhoc_filtering_overrides_existing_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    # in usual scenario this filter would filtered out all rows
    equal_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="equal", value="y"
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )
    view_handler = ViewHandler()
    view_handler.update_field_options(
        view=grid_view,
        field_options={
            text_field.id: {
                "hidden": False,
                "aggregation_type": "unique_count",
                "aggregation_raw_type": "unique_count",
            }
        },
    )

    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid_view.id},
    )

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
        ],
    }
    get_params = [f"filters={json.dumps(advanced_filters)}"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {text_field.db_column: 1}


@pytest.mark.django_db
def test_view_aggregations_adhoc_filtering_advanced_filters_are_preferred_to_other_filter_query_params(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )
    view_handler = ViewHandler()
    view_handler.update_field_options(
        view=grid_view,
        field_options={
            text_field.id: {
                "hidden": False,
                "aggregation_type": "unique_count",
                "aggregation_raw_type": "unique_count",
            }
        },
    )

    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid_view.id},
    )
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": text_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }
    get_params = [
        "filters=" + json.dumps(advanced_filters),
        f"filter__field_{text_field.id}__equal=z",
        f"filter_type=AND",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {text_field.db_column: 2}


@pytest.mark.django_db
def test_view_aggregations_adhoc_filtering_invalid_advanced_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    view_handler = ViewHandler()
    view_handler.update_field_options(
        view=grid_view,
        field_options={
            text_field.id: {
                "hidden": False,
                "aggregation_type": "unique_count",
                "aggregation_raw_type": "unique_count",
            }
        },
    )

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid_view.id},
    )

    expected_errors = [
        (
            "invalid_json",
            {
                "error": "The provided filters are not valid JSON.",
                "code": "invalid_json",
            },
        ),
        (
            json.dumps({"filter_type": "invalid"}),
            {
                "filter_type": [
                    {
                        "error": '"invalid" is not a valid choice.',
                        "code": "invalid_choice",
                    }
                ]
            },
        ),
        (
            json.dumps(
                {"filter_type": "OR", "filters": "invalid", "groups": "invalid"}
            ),
            {
                "filters": [
                    {
                        "error": 'Expected a list of items but got type "str".',
                        "code": "not_a_list",
                    }
                ],
                "groups": {
                    "non_field_errors": [
                        {
                            "error": 'Expected a list of items but got type "str".',
                            "code": "not_a_list",
                        }
                    ],
                },
            },
        ),
    ]

    for filters, error_detail in expected_errors:
        get_params = [f"filters={filters}"]
        response = api_client.get(
            f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"
        assert response_json["detail"] == error_detail


@pytest.mark.django_db
def test_view_aggregations_cache_invalidation_with_dependant_fields(
    api_client, data_fixture
):
    """
    Here we want a complex situation where we need to invalidate the cache of a
    dependant field in another table. Should be the more extreme scenario.
    We create two tables with a link row field from table2 to table1, a lookup field on
    table 2 to the number field on table 1 and a formula that sum the values of
    table 2's lookup field.
    """

    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    grid = data_fixture.create_grid_view(table=table)
    grid2 = data_fixture.create_grid_view(table=table2)

    linkrowfield = FieldHandler().create_field(
        user,
        table2,
        "link_row",
        name="linkrowfield",
        link_row_table=table,
    )

    lookup_field = FieldHandler().create_field(
        user,
        table2,
        "lookup",
        name="lookup_field",
        through_field_id=linkrowfield.id,
        target_field_id=number_field.id,
    )

    sum_formula_on_lookup_field = FieldHandler().create_field(
        user,
        table2,
        "formula",
        name="sum",
        formula='sum(field("lookup_field"))',
    )

    # Create some aggregations
    data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=number_field,
        aggregation_type="whatever",
        aggregation_raw_type="sum",
    )

    data_fixture.create_grid_view_field_option(
        grid_view=grid2,
        field=sum_formula_on_lookup_field,
        aggregation_type="whatever",
        aggregation_raw_type="sum",
    )

    # Define some utilities functions
    def add_value_to_table1(value):
        # Add data through the API to trigger cache update
        response = api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table.id}),
            {
                f"field_{number_field.id}": value,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        return response.json()

    def update_value_of_table1(row, value):
        api_client.patch(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row["id"]},
            ),
            {f"field_{number_field.id}": value},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    def delete_row_of_table1(row):
        api_client.delete(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row["id"]},
            ),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    def add_link_to_table2(links):
        # Add data through the API to trigger cache update
        response = api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table2.id}),
            {
                f"field_{linkrowfield.id}": [link["id"] for link in links],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        return response.json()

    def check_table_2_aggregation_values(value_to_check, ident):
        response = api_client.get(
            url2,
            **{"HTTP_AUTHORIZATION": f"JWT {token}"},
        )
        response_json = response.json()

        assert response_json == value_to_check, ident

    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid.id},
    )
    url2 = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid2.id},
    )

    row1 = add_value_to_table1(1)
    row2 = add_value_to_table1(10)
    row3 = add_value_to_table1(100)
    row4 = add_value_to_table1(1000)

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") is None
    assert (
        cache.get(
            f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        is None
    )

    api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1111),
        "version": 5,
    }
    assert (
        cache.get(
            f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        is None
    )

    check_table_2_aggregation_values(
        {sum_formula_on_lookup_field.db_column: None}, "with no link"
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1111),
        "version": 5,
    }
    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {"value": None, "version": 5}

    cache.set(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}",
        {"value": "sentinel", "version": 0},
    )

    # Add few links
    add_link_to_table2([row1, row2])

    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {"value": "sentinel", "version": 0}

    add_link_to_table2([row2, row3])
    add_link_to_table2([row3, row4])
    add_link_to_table2([row4])

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1111),
        "version": 5,
    }

    check_table_2_aggregation_values(
        {sum_formula_on_lookup_field.db_column: 2221}, "after link addition"
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1111),
        "version": 5,
    }
    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {
        "value": Decimal(2221),
        "version": 9,
    }

    update_value_of_table1(row2, 10000)

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1111),
        "version": 5,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 6
    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {
        "value": Decimal(2221),
        "version": 9,
    }
    assert (
        cache.get(
            f"aggregation_version__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        == 10
    )

    check_table_2_aggregation_values(
        {sum_formula_on_lookup_field.db_column: 22201}, "after table 1 value update"
    )

    # Delete row3 from table1
    api_client.delete(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row3["id"]},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal("1111"),
        "version": 5,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 7

    # Should increment cache version
    assert (
        cache.get(
            f"aggregation_version__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        == 11
    )

    check_table_2_aggregation_values(
        {sum_formula_on_lookup_field.db_column: 22001}, "after row deletion"
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal("1111"),
        "version": 5,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 7
    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {
        "value": Decimal(22001),
        "version": 11,
    }

    # Restore delete row
    api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "row",
            "trash_item_id": row3["id"],
            "parent_trash_item_id": table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert (
        cache.get(
            f"aggregation_version__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        == 12
    )

    check_table_2_aggregation_values(
        {sum_formula_on_lookup_field.db_column: 22201}, "after row restoration"
    )

    # Should store the new value/version in cache
    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {
        "value": Decimal(22201),
        "version": 12,
    }

    # Update number field
    api_client.patch(
        reverse(
            "api:database:fields:item",
            kwargs={"field_id": number_field.id},
        ),
        {"number_decimal_places": 1},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Cache version should not increment because the number field didn't change type.
    assert (
        cache.get(
            f"aggregation_version__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        == 12
    )

    check_table_2_aggregation_values(
        {sum_formula_on_lookup_field.db_column: 22201}, "after field modification"
    )

    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {
        "value": Decimal(22201),
        "version": 12,
    }

    # Delete number field
    api_client.delete(
        reverse(
            "api:database:fields:item",
            kwargs={"field_id": number_field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {
        "value": Decimal(22201),
        "version": 12,
    }
    assert (
        cache.get(
            f"aggregation_version__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        == 13
    )

    check_table_2_aggregation_values({}, "after field deletion")

    # No modification as the field and the aggregation don't exist
    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {
        "value": Decimal(22201),
        "version": 12,
    }
    assert (
        cache.get(
            f"aggregation_version__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        == 13
    )

    # Restore deleted field
    resp = api_client.patch(
        reverse(
            "api:trash:restore",
        ),
        {
            "trash_item_type": "field",
            "trash_item_id": number_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.json() == {number_field.db_column: 11101}

    # The field aggregation has been automatically deleted so no aggregations anymore
    check_table_2_aggregation_values({}, "after field restoration")

    # Still no modifications
    assert cache.get(
        f"aggregation_value__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
    ) == {
        "value": Decimal(22201),
        "version": 12,
    }
    assert (
        cache.get(
            f"aggregation_version__{grid2.id}_{sum_formula_on_lookup_field.db_column}"
        )
        == 13
    )


@pytest.mark.django_db
def test_can_get_aggregation_if_result_is_nan(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)

    # This formula will resolve  as NaN for every row
    formula_field = data_fixture.create_formula_field(table=table, formula="1 / 0")

    RowHandler().create_row(user, table)

    ViewHandler().update_field_options(
        view=grid_view,
        field_options={
            formula_field.id: {
                "aggregation_type": "sum",
                "aggregation_raw_type": "sum",
            }
        },
    )

    url = reverse(
        "api:database:views:grid:field-aggregations",
        kwargs={"view_id": grid_view.id},
    )

    response = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {f"field_{formula_field.id}": "NaN"}


@pytest.mark.django_db
def test_public_view_aggregations_view_doesnt_exist(api_client):
    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": "doesnt-exist"},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GRID_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_public_view_aggregations_view_not_publicly_shared(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table, public=False)
    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid.slug},
    )

    response = api_client.get(
        url,
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GRID_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_public_view_aggregations_accessed_with_password(api_client, data_fixture):
    user = data_fixture.create_user()
    grid_view = data_fixture.create_public_password_protected_grid_view(
        user=user, password="12345678"
    )

    # wrong password
    response = api_client.get(
        reverse(
            "api:database:views:grid:public-field-aggregations",
            kwargs={"slug": grid_view.slug},
        ),
        {"password": "wrong_password"},
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"

    # correct password
    response = api_client.get(
        reverse(
            "api:database:views:grid:public-field-aggregations",
            kwargs={"slug": grid_view.slug},
        ),
        {"password": "12345678"},
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"


@pytest.mark.django_db
def test_public_view_aggregations_trashed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table, public=True)
    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid.slug},
    )

    ViewHandler().delete_view(user, grid)

    response = api_client.get(
        url,
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GRID_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_public_view_aggregations_trashed_parent(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table, public=True)
    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid.slug},
    )
    TableHandler().delete_table(user, table)

    response = api_client.get(
        url,
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GRID_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_public_view_aggregations_hidden_fields(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    public_field_option = data_fixture.create_grid_view_field_option(
        grid, public_field, hidden=False
    )
    data_fixture.create_grid_view_field_option(grid, hidden_field, hidden=True)
    RowHandler().create_row(user, table, values={})
    aggregation_public_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=public_field,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )
    aggregation_hidden_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=hidden_field,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )

    response = api_client.get(
        reverse(
            "api:database:views:grid:public-field-aggregations",
            kwargs={"slug": grid.slug},
        )
    )

    assert response.json() == {f"field_{public_field.id}": 1}


@pytest.mark.django_db
def test_public_view_aggregations(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    grid = data_fixture.create_grid_view(table=table, public=True)
    grid_2 = data_fixture.create_grid_view()

    # Test normal response with no data and no aggregation
    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid.slug},
    )

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {}

    field_option1 = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=text_field,
        aggregation_type="",
        aggregation_raw_type="",
    )

    field_option2 = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=number_field,
        aggregation_type="whatever",
        aggregation_raw_type="sum",
    )

    field_option3 = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=boolean_field,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") is None
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") is None
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") is None
    assert (
        cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") is None
    )

    # Test normal response with no data and no cache
    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {number_field.db_column: None, boolean_field.db_column: 0}

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": None,
        "version": 1,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") is None
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": 0,
        "version": 1,
    }
    assert (
        cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") is None
    )

    # Test normal response that use cache
    cache.set(
        f"aggregation_value__{grid.id}_{number_field.db_column}",
        {"value": "sentinel", "version": 1},
    )
    cache.set(
        f"aggregation_value__{grid.id}_{boolean_field.db_column}",
        {"value": "sentinel", "version": 1},
    )

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {
        number_field.db_column: "sentinel",
        boolean_field.db_column: "sentinel",
    }

    cache.set(
        f"aggregation_value__{grid.id}_{number_field.db_column}",
        {"value": "sentinel", "version": 1},
    )
    cache.set(
        f"aggregation_value__{grid.id}_{boolean_field.db_column}",
        {"value": "sentinel", "version": 3},
    )
    cache.set(
        f"aggregation_version__{grid.id}_{boolean_field.db_column}",
        3,
    )

    # Add data through the API to trigger cache update
    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": "sentinel",
        "version": 1,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 2
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": "sentinel",
        "version": 3,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 4

    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": "",
            f"field_{number_field.id}": 0,
            f"field_{boolean_field.id}": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": None,
            f"field_{number_field.id}": 1200,
            f"field_{boolean_field.id}": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Test normal response with data
    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {number_field.db_column: 1210.0, boolean_field.db_column: 2}

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": 1210.0,
        "version": 4,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 4
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": 2,
        "version": 6,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 6

    # with total
    response = api_client.get(
        url + f"?include=total",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json == {
        number_field.db_column: 1210.0,
        boolean_field.db_column: 2,
        "total": 3,
    }

    # Does it work with filter
    response = api_client.get(
        url + f"?include=total&search=GREE",
    )
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    assert response_json == {
        number_field.db_column: 10.0,
        boolean_field.db_column: 0,
        "total": 1,
    }

    # But cache shouldn't be modified after a search as we don't use the cache
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 4
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 6

    # Does it work with filter (use API to trigger cache update)
    response = api_client.post(
        reverse("api:database:views:list_filters", kwargs={"view_id": grid.id}),
        {"field": number_field.id, "type": "higher_than", "value": "10"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    filter_id = response.json()["id"]

    # Cache should be invalidated on filter creation
    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1210),
        "version": 4,
    }
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": 2,
        "version": 6,
    }
    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 5
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 7

    response = api_client.get(
        url + f"?include=total",
    )
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    assert response_json == {
        number_field.db_column: 1200.0,
        boolean_field.db_column: 1,
        "total": 1,
    }

    assert cache.get(f"aggregation_value__{grid.id}_{number_field.db_column}") == {
        "value": Decimal(1200),
        "version": 5,
    }
    assert cache.get(f"aggregation_value__{grid.id}_{boolean_field.db_column}") == {
        "value": 1,
        "version": 7,
    }

    # Let's update the filter
    api_client.patch(
        reverse("api:database:views:filter_item", kwargs={"view_filter_id": filter_id}),
        {"value": 5},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 6
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 8

    response = api_client.get(
        url + f"?include=total",
    )
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    assert response_json == {
        number_field.db_column: 1210.0,
        boolean_field.db_column: 1,
        "total": 2,
    }

    # Cache should also be invalidated on filter deletion
    api_client.delete(
        reverse("api:database:views:filter_item", kwargs={"view_filter_id": filter_id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert cache.get(f"aggregation_version__{grid.id}_{number_field.db_column}") == 7
    assert cache.get(f"aggregation_version__{grid.id}_{boolean_field.db_column}") == 9

    response = api_client.get(
        url + f"?include=total",
    )
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    assert response_json == {
        number_field.db_column: 1210.0,
        boolean_field.db_column: 2,
        "total": 3,
    }


@pytest.mark.django_db
def test_public_view_aggregations_hidden_field_query_filter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    public_field_option = data_fixture.create_grid_view_field_option(
        grid, public_field, hidden=False
    )
    data_fixture.create_grid_view_field_option(grid, hidden_field, hidden=True)
    aggregation_public_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=public_field,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )
    aggregation_hidden_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=hidden_field,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )

    response = api_client.get(
        reverse(
            "api:database:views:grid:public-field-aggregations",
            kwargs={"slug": grid.slug},
        )
        + f"?filter__field_{hidden_field.id}__contains=a"
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"


@pytest.mark.django_db
def test_public_view_aggregations_hidden_field_advanced_filter(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    public_field_option = data_fixture.create_grid_view_field_option(
        grid, public_field, hidden=False
    )
    data_fixture.create_grid_view_field_option(grid, hidden_field, hidden=True)
    aggregation_public_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=public_field,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )
    aggregation_hidden_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=hidden_field,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": public_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": hidden_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }

    get_params = [f"filters={json.dumps(advanced_filters)}"]
    response = api_client.get(
        reverse(
            "api:database:views:grid:public-field-aggregations",
            kwargs={"slug": grid.slug},
        )
        + f"?{'&'.join(get_params)}"
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"


@pytest.mark.django_db
def test_public_view_aggregations_hidden_field_search(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    public_field_option = data_fixture.create_grid_view_field_option(
        grid, public_field, hidden=False
    )
    data_fixture.create_grid_view_field_option(grid, hidden_field, hidden=True)
    aggregation_public_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=public_field,
        aggregation_type="whatever",
        aggregation_raw_type="unique_count",
    )
    aggregation_hidden_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=hidden_field,
        aggregation_type="whatever",
        aggregation_raw_type="unique_count",
    )
    # will be counted
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "a"})
    # should not get counted because the field is hidden
    RowHandler().create_row(
        user,
        table,
        values={f"field_{public_field.id}": "b", f"field_{hidden_field.id}": "a"},
    )
    # won't get counted because there is no match
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "c"})

    response = api_client.get(
        (
            reverse(
                "api:database:views:grid:public-field-aggregations",
                kwargs={"slug": grid.slug},
            )
            + "?search=a"
        )
    )

    assert response.json() == {f"field_{public_field.id}": 1}


@pytest.mark.django_db
def test_public_view_aggregations_hidden_field_search_logged_in_user(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    public_field_option = data_fixture.create_grid_view_field_option(
        grid, public_field, hidden=False
    )
    data_fixture.create_grid_view_field_option(grid, hidden_field, hidden=True)
    aggregation_public_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=public_field,
        aggregation_type="whatever",
        aggregation_raw_type="unique_count",
    )
    aggregation_hidden_field = data_fixture.create_grid_view_field_option(
        grid_view=grid,
        field=hidden_field,
        aggregation_type="whatever",
        aggregation_raw_type="unique_count",
    )
    # will be counted
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "a"})
    # should not get counted because the field is hidden
    RowHandler().create_row(
        user,
        table,
        values={f"field_{public_field.id}": "b", f"field_{hidden_field.id}": "a"},
    )
    # won't get counted because there is no match
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "c"})

    response = api_client.get(
        (
            reverse(
                "api:database:views:grid:public-field-aggregations",
                kwargs={"slug": grid.slug},
            )
            + "?search=a"
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.json() == {f"field_{public_field.id}": 1}


@pytest.mark.django_db
def test_public_view_aggregations_no_adhoc_filtering_uses_view_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    # this filter would filters out all rows
    equal_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="equal", value="y"
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )
    view_handler = ViewHandler()
    view_handler.update_field_options(
        view=grid_view,
        field_options={
            text_field.id: {
                "hidden": False,
                "aggregation_type": "unique_count",
                "aggregation_raw_type": "unique_count",
            }
        },
    )

    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid_view.slug},
    )

    # without ad hoc filters the view filter is applied
    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {text_field.db_column: 0}


@pytest.mark.django_db
def test_public_view_aggregations_adhoc_filtering_combineswith_existing_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field_for_view_filter = data_fixture.create_text_field(
        table=table, name="text_field"
    )
    text_field_for_adhoc_filter = data_fixture.create_text_field(
        table=table, name="text_field_adhoc"
    )
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(
        grid_view, text_field_for_view_filter, hidden=False
    )
    data_fixture.create_grid_view_field_option(
        grid_view, text_field_for_adhoc_filter, hidden=False
    )
    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field_for_view_filter, type="not_equal", value="y"
    )
    # visible
    RowHandler().create_row(
        user,
        table,
        values={"text_field": "a", "text_field_adhoc": "a"},
        user_field_names=True,
    )
    # hidden by adhoc filter
    RowHandler().create_row(
        user,
        table,
        values={"text_field": "b", "text_field_adhoc": "b"},
        user_field_names=True,
    )
    # hidden by view filter
    RowHandler().create_row(
        user,
        table,
        values={"text_field": "y", "text_field_adhoc": "a"},
        user_field_names=True,
    )
    # hidden by view filter
    RowHandler().create_row(
        user,
        table,
        values={"text_field": "y", "text_field_adhoc": "a"},
        user_field_names=True,
    )
    view_handler = ViewHandler()
    view_handler.update_field_options(
        view=grid_view,
        field_options={
            text_field_for_view_filter.id: {
                "hidden": False,
                "aggregation_type": "unique_count",
                "aggregation_raw_type": "unique_count",
            }
        },
    )

    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid_view.slug},
    )

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": text_field_for_adhoc_filter.id,
                "type": "equal",
                "value": "a",
            },
        ],
    }

    get_params = [f"filters={json.dumps(advanced_filters)}"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json == {text_field_for_view_filter.db_column: 1}


@pytest.mark.django_db
def test_public_view_aggregations_adhoc_filtering_advanced_filters_are_preferred_to_other_filter_query_params(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )
    view_handler = ViewHandler()
    view_handler.update_field_options(
        view=grid_view,
        field_options={
            text_field.id: {
                "hidden": False,
                "aggregation_type": "unique_count",
                "aggregation_raw_type": "unique_count",
            }
        },
    )

    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid_view.slug},
    )
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": text_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }
    get_params = [
        "filters=" + json.dumps(advanced_filters),
        f"filter__field_{text_field.id}__equal=z",
        f"filter_type=AND",
    ]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {text_field.db_column: 2}


@pytest.mark.django_db
def test_public_view_aggregations_adhoc_filtering_invalid_advanced_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    view_handler = ViewHandler()
    view_handler.update_field_options(
        view=grid_view,
        field_options={
            text_field.id: {
                "aggregation_type": "unique_count",
                "aggregation_raw_type": "unique_count",
            }
        },
    )

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid_view.slug},
    )

    expected_errors = [
        (
            "invalid_json",
            {
                "error": "The provided filters are not valid JSON.",
                "code": "invalid_json",
            },
        ),
        (
            json.dumps({"filter_type": "invalid"}),
            {
                "filter_type": [
                    {
                        "error": '"invalid" is not a valid choice.',
                        "code": "invalid_choice",
                    }
                ]
            },
        ),
        (
            json.dumps(
                {"filter_type": "OR", "filters": "invalid", "groups": "invalid"}
            ),
            {
                "filters": [
                    {
                        "error": 'Expected a list of items but got type "str".',
                        "code": "not_a_list",
                    }
                ],
                "groups": {
                    "non_field_errors": [
                        {
                            "error": 'Expected a list of items but got type "str".',
                            "code": "not_a_list",
                        }
                    ],
                },
            },
        ),
    ]

    for filters, error_detail in expected_errors:
        get_params = [f"filters={filters}"]
        response = api_client.get(f'{url}?{"&".join(get_params)}')
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"
        assert response_json["detail"] == error_detail


@pytest.mark.django_db
def test_can_get_public_aggregation_if_result_is_nan(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table, public=True, slug="abc")

    # This formula will resolve  as NaN for every row
    formula_field = data_fixture.create_formula_field(table=table, formula="1 / 0")

    RowHandler().create_row(user=user, table=table, values={})

    ViewHandler().update_field_options(
        view=grid_view,
        field_options={
            formula_field.id: {
                "hidden": False,
                "aggregation_type": "sum",
                "aggregation_raw_type": "sum",
            }
        },
    )

    url = reverse(
        "api:database:views:grid:public-field-aggregations",
        kwargs={"slug": grid_view.slug},
    )

    response = api_client.get(url)

    assert response.json() == {f"field_{formula_field.id}": "NaN"}
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_patch_grid_view_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    data_fixture.create_text_field()
    grid = data_fixture.create_grid_view(table=table)
    # The second field is deliberately created after the creation of the grid field
    # so that the GridViewFieldOptions entry is not created. This should
    # automatically be created when the page is fetched.
    number_field = data_fixture.create_number_field(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {"field_options": {text_field.id: {"width": 300, "hidden": True}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 2
    assert response_json["field_options"][str(text_field.id)]["width"] == 300
    assert response_json["field_options"][str(text_field.id)]["hidden"] is True
    assert response_json["field_options"][str(text_field.id)]["order"] == 32767
    assert response_json["field_options"][str(text_field.id)]["aggregation_type"] == ""
    assert (
        response_json["field_options"][str(text_field.id)]["aggregation_raw_type"] == ""
    )
    assert response_json["field_options"][str(number_field.id)]["width"] == 200
    assert response_json["field_options"][str(number_field.id)]["hidden"] is False
    assert response_json["field_options"][str(number_field.id)]["order"] == 32767
    assert (
        response_json["field_options"][str(number_field.id)]["aggregation_type"] == ""
    )
    assert (
        response_json["field_options"][str(number_field.id)]["aggregation_raw_type"]
        == ""
    )
    options = grid.get_field_options()
    assert len(options) == 2
    assert options[0].field_id == text_field.id
    assert options[0].width == 300
    assert options[0].hidden is True
    assert options[0].order == 32767
    assert options[0].aggregation_type == ""
    assert options[0].aggregation_raw_type == ""
    assert options[1].field_id == number_field.id
    assert options[1].width == 200
    assert options[1].hidden is False
    assert options[1].order == 32767
    assert options[1].aggregation_type == ""
    assert options[1].aggregation_raw_type == ""

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                text_field.id: {"width": 100, "hidden": False},
                number_field.id: {"width": 500, "hidden": True},
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 2
    assert response_json["field_options"][str(text_field.id)]["width"] == 100
    assert response_json["field_options"][str(text_field.id)]["hidden"] is False
    assert response_json["field_options"][str(number_field.id)]["width"] == 500
    assert response_json["field_options"][str(number_field.id)]["hidden"] is True
    options = grid.get_field_options()
    assert len(options) == 2
    assert options[0].field_id == text_field.id
    assert options[0].width == 100
    assert options[0].hidden is False
    assert options[1].field_id == number_field.id
    assert options[1].hidden is True

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                text_field.id: {
                    "width": 200,
                },
                number_field.id: {
                    "hidden": False,
                },
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 2
    assert response_json["field_options"][str(text_field.id)]["width"] == 200
    assert response_json["field_options"][str(text_field.id)]["hidden"] is False
    assert response_json["field_options"][str(number_field.id)]["width"] == 500
    assert response_json["field_options"][str(number_field.id)]["hidden"] is False
    options = grid.get_field_options()
    assert len(options) == 2
    assert options[0].field_id == text_field.id
    assert options[0].width == 200
    assert options[0].hidden is False
    assert options[1].field_id == number_field.id
    assert options[1].hidden is False

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url, {"field_options": {}}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {"field_options": {"RANDOM_FIELD": "TEST"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["field_options"][0]["code"] == "invalid_key"

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {"field_options": {text_field.id: {"width": "abc"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["field_options"][0]["code"] == "invalid_value"

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {"field_options": {text_field.id: {"hidden": "abc"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["field_options"][0]["code"] == "invalid_value"

    # Test unregistered aggregation type
    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {"field_options": {text_field.id: {"aggregation_raw_type": "foo"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["field_options"][0]["code"] == "invalid_value"

    # Test aggregation type that doesn't support the field
    # Fake incompatible field
    empty_count = view_aggregation_type_registry.get("empty_count")
    empty_count.field_is_compatible = lambda _: False

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {"field_options": {text_field.id: {"aggregation_raw_type": "empty_count"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_AGGREGATION_DOES_NOT_SUPPORTED_FIELD"
    assert (
        response_json["detail"]
        == "The aggregation type does not support the given field."
    )

    empty_count.field_is_compatible = lambda _: True


@pytest.mark.django_db
def test_create_grid_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "NOT_EXISTING"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["type"][0]["code"] == "invalid_choice"

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": 99999}),
        {"name": "Test 1", "type": "grid"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table_2.id}),
        {"name": "Test 1", "type": "grid"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:list", kwargs={"table_id": table_2.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "grid"
    assert response_json["filter_type"] == "OR"
    assert response_json["filters_disabled"] is True

    grid = GridView.objects.filter()[0]
    assert response_json["id"] == grid.id
    assert response_json["name"] == grid.name
    assert response_json["order"] == grid.order
    assert response_json["filter_type"] == grid.filter_type
    assert response_json["filters_disabled"] == grid.filters_disabled
    assert "filters" not in response_json
    assert "sortings" not in response_json
    assert "decorations" not in response_json

    response = api_client.post(
        "{}?include=filters,sortings,decorations,group_bys".format(
            reverse("api:database:views:list", kwargs={"table_id": table.id})
        ),
        {
            "name": "Test 2",
            "type": "grid",
            "filter_type": "AND",
            "filters_disabled": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 2"
    assert response_json["type"] == "grid"
    assert response_json["filter_type"] == "AND"
    assert response_json["filters_disabled"] is False
    assert response_json["filters"] == []
    assert response_json["sortings"] == []
    assert response_json["decorations"] == []
    assert response_json["group_bys"] == []

    response = api_client.post(
        "{}".format(reverse("api:database:views:list", kwargs={"table_id": table.id})),
        {"name": "Test 3", "type": "grid"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 3"
    assert response_json["type"] == "grid"
    assert response_json["filter_type"] == "AND"
    assert response_json["filters_disabled"] is False
    assert "filters" not in response_json
    assert "sortings" not in response_json
    assert "decorations" not in response_json
    assert "group_bys" not in response_json


@pytest.mark.django_db
def test_update_grid_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user_2)
    view = data_fixture.create_grid_view(table=table)
    view_2 = data_fixture.create_grid_view(table=table_2)
    not_sharable_view = data_fixture.create_gallery_view(table=table)

    url = reverse("api:database:views:item", kwargs={"view_id": view_2.id})
    response = api_client.patch(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:item", kwargs={"view_id": 999999})
    response = api_client.patch(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.patch(
        url,
        {"UNKNOWN_FIELD": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.patch(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == view.id
    assert response_json["name"] == "Test 1"
    assert response_json["filter_type"] == "AND"
    assert not response_json["filters_disabled"]

    view.refresh_from_db()
    assert view.name == "Test 1"
    assert view.filter_type == "AND"
    assert not view.filters_disabled

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.patch(
        url,
        {
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == view.id
    assert response_json["filter_type"] == "OR"
    assert response_json["filters_disabled"]
    assert "filters" not in response_json
    assert "sortings" not in response_json
    assert "decorations" not in response_json
    assert "group_bys" not in response_json

    view.refresh_from_db()
    assert view.filter_type == "OR"
    assert view.filters_disabled

    filter_1 = data_fixture.create_view_filter(view=view)
    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.patch(
        "{}?include=filters,sortings,decorations,group_bys".format(url),
        {"filter_type": "AND"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == view.id
    assert response_json["filter_type"] == "AND"
    assert response_json["filters_disabled"] is True
    assert response_json["filters"][0]["id"] == filter_1.id
    assert response_json["sortings"] == []
    assert response_json["decorations"] == []
    assert response_json["group_bys"] == []


@pytest.mark.django_db
def test_get_public_grid_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")

    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )

    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    # This view sort shouldn't be exposed as it is for a hidden field
    data_fixture.create_view_sort(view=grid_view, field=hidden_field, order="ASC")
    visible_sort = data_fixture.create_view_sort(
        view=grid_view, field=public_field, order="DESC"
    )

    # This group by shouldn't be exposed as it is for a hidden field
    data_fixture.create_view_group_by(view=grid_view, field=hidden_field, order="ASC")
    visible_group_by = data_fixture.create_view_group_by(
        view=grid_view, field=public_field, order="DESC"
    )

    # View filters should not be returned at all for any and all fields regardless of
    # if they are hidden.
    data_fixture.create_view_filter(
        view=grid_view, field=hidden_field, type="contains", value="hidden"
    )
    data_fixture.create_view_filter(
        view=grid_view, field=public_field, type="contains", value="public"
    )

    # Can access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug})
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "fields": [
            {
                "id": public_field.id,
                "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "name": "public",
                "order": 0,
                "primary": False,
                "text_default": "",
                "type": "text",
                "read_only": False,
                "description": None,
                "immutable_properties": False,
                "immutable_type": False,
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "db_index": False,
                "field_constraints": [],
            }
        ],
        "view": {
            "id": grid_view.slug,
            "name": grid_view.name,
            "order": 0,
            "public": True,
            "slug": grid_view.slug,
            "sortings": [
                # Note the sorting for the hidden field is not returned
                {
                    "field": visible_sort.field.id,
                    "id": visible_sort.id,
                    "order": "DESC",
                    "type": "default",
                    "view": grid_view.slug,
                }
            ],
            "group_bys": [
                # Note the group by for the hidden field is not returned
                {
                    "field": visible_group_by.field.id,
                    "id": visible_group_by.id,
                    "order": "DESC",
                    "view": grid_view.slug,
                    "width": 200,
                    "type": "default",
                }
            ],
            "table": {
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "id": PUBLIC_PLACEHOLDER_ENTITY_ID,
            },
            "type": "grid",
            "row_identifier_type": grid_view.row_identifier_type,
            "row_height_size": grid_view.row_height_size,
            "show_logo": True,
            "allow_public_export": False,
        },
    }


@pytest.mark.django_db
def test_list_rows_public_doesnt_show_hidden_columns(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")

    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )

    public_field_option = data_fixture.create_grid_view_field_option(
        grid_view, public_field, hidden=False
    )
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    RowHandler().create_row(user, table, values={})

    # Get access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug})
        + "?include=field_options"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                f"field_{public_field.id}": None,
                "id": 1,
                "order": "1.00000000000000000000",
            }
        ],
        "field_options": {
            f"{public_field.id}": {
                "hidden": False,
                "order": public_field_option.order,
                "width": public_field_option.width,
                "aggregation_type": "",
                "aggregation_raw_type": "",
            },
        },
    }


@pytest.mark.django_db
def test_list_rows_public_with_query_param_filter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__contains=a"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    get_params = [
        f"filter__field_{public_field.id}__contains=a",
        f"filter__field_{public_field.id}__contains=b",
        f"filter_type=OR",
    ]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    get_params = [f"filter__field_{hidden_field.id}__contains=y"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__random=y"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__higher_than=1"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"


@pytest.mark.django_db
def test_list_rows_public_with_invalid_advanced_filters(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )

    expected_errors = [
        (
            "invalid_json",
            {
                "error": "The provided filters are not valid JSON.",
                "code": "invalid_json",
            },
        ),
        (
            json.dumps({"filter_type": "invalid"}),
            {
                "filter_type": [
                    {
                        "error": '"invalid" is not a valid choice.',
                        "code": "invalid_choice",
                    }
                ]
            },
        ),
        (
            json.dumps(
                {"filter_type": "OR", "filters": "invalid", "groups": "invalid"}
            ),
            {
                "filters": [
                    {
                        "error": 'Expected a list of items but got type "str".',
                        "code": "not_a_list",
                    }
                ],
                "groups": {
                    "non_field_errors": [
                        {
                            "error": 'Expected a list of items but got type "str".',
                            "code": "not_a_list",
                        }
                    ],
                },
            },
        ),
    ]

    for filters, error_detail in expected_errors:
        get_params = [f"filters={filters}"]
        response = api_client.get(f'{url}?{"&".join(get_params)}')
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"
        assert response_json["detail"] == error_detail


@pytest.mark.django_db
def test_list_rows_public_with_query_param_advanced_filters(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "contains",
                "value": "a",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "OR",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "a",
                    },
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "b",
                    },
                ],
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    # groups can be arbitrarily nested
    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "AND",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "",
                    },
                ],
                "groups": [
                    {
                        "filter_type": "OR",
                        "filters": [
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "a",
                            },
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "b",
                            },
                        ],
                    },
                ],
            },
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": hidden_field.id,
                "type": "contains",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "random",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "higher_than",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"

    for filters in [
        "invalid_json",
        json.dumps({"filter_type": "invalid"}),
        json.dumps({"filter_type": "OR", "filters": "invalid"}),
    ]:
        get_params = [f"filters={filters}"]
        response = api_client.get(f'{url}?{"&".join(get_params)}')
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"


@pytest.mark.django_db
def test_list_rows_with_query_param_order(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    password_field = data_fixture.create_password_field(table=table, name="password")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, text_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)
    data_fixture.create_grid_view_field_option(grid_view, password_field, hidden=False)
    first_row = RowHandler().create_row(
        user, table, values={"text": "a", "hidden": "a"}, user_field_names=True
    )
    second_row = RowHandler().create_row(
        user, table, values={"text": "b", "hidden": "b"}, user_field_names=True
    )
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})

    # adhoc sorting
    response = api_client.get(
        f"{url}?order_by=-field_{text_field.id}",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == second_row.id
    assert response_json["results"][1]["id"] == first_row.id

    # adhoc sorting on hidden field
    response = api_client.get(
        f"{url}?order_by=field_{hidden_field.id}",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == first_row.id
    assert response_json["results"][1]["id"] == second_row.id

    # sorting on unsupported field
    response = api_client.get(
        f"{url}?order_by=field_{password_field.id}",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"


@pytest.mark.django_db
def test_list_rows_public_with_query_param_order(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    password_field = data_fixture.create_password_field(table=table, name="password")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)
    data_fixture.create_grid_view_field_option(grid_view, password_field, hidden=False)

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    second_row = RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?order_by=-field_{public_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == second_row.id
    assert response_json["results"][1]["id"] == first_row.id

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?order_by=field_{hidden_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?order_by=field_{password_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"


@pytest.mark.django_db
def test_list_rows_public_with_query_param_group_by(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    public_field_2 = data_fixture.create_text_field(table=table, name="public2")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    password_field = data_fixture.create_password_field(table=table, name="password")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, public_field_2, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)
    data_fixture.create_grid_view_field_option(grid_view, password_field, hidden=False)

    first_row = RowHandler().create_row(
        user,
        table,
        values={"public": "b", "public2": "2", "hidden": "y"},
        user_field_names=True,
    )
    second_row = RowHandler().create_row(
        user,
        table,
        values={"public": "a", "public2": "2", "hidden": "y"},
        user_field_names=True,
    )
    third_row = RowHandler().create_row(
        user,
        table,
        values={"public": "b", "public2": "1", "hidden": "z"},
        user_field_names=True,
    )

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?group_by=field_{public_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 3
    assert response_json["results"][0]["id"] == second_row.id
    assert response_json["results"][1]["id"] == first_row.id
    assert response_json["results"][2]["id"] == third_row.id
    assert response_json["group_by_metadata"] == {
        f"field_{public_field.id}": unordered(
            [
                {"count": 1, f"field_{public_field.id}": "a"},
                {"count": 2, f"field_{public_field.id}": "b"},
            ]
        )
    }

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?group_by=-field_{public_field.id}&sort_by=field{public_field_2.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 3
    assert response_json["results"][0]["id"] == first_row.id
    assert response_json["results"][1]["id"] == third_row.id
    assert response_json["results"][2]["id"] == second_row.id

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?group_by=field_{hidden_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?group_by=field_{password_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"


@pytest.mark.django_db
def test_list_rows_public_with_query_param_group_by_and_empty_order_by(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(database=table.database)
    public_field = data_fixture.create_text_field(table=table, name="public")
    public_field_2 = data_fixture.create_text_field(table=table, name="public2")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Link",
        link_row_table=table_2,
    )
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, public_field_2, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)
    data_fixture.create_grid_view_field_option(grid_view, link_row_field, hidden=False)

    first_row = RowHandler().create_row(
        user,
        table,
        values={"public": "b", "public2": "2", "hidden": "y"},
        user_field_names=True,
    )
    second_row = RowHandler().create_row(
        user,
        table,
        values={"public": "a", "public2": "2", "hidden": "y"},
        user_field_names=True,
    )

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?group_by=field_{public_field.id}&order_by=",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == second_row.id
    assert response_json["results"][1]["id"] == first_row.id
    assert response_json["group_by_metadata"] == {
        f"field_{public_field.id}": unordered(
            [
                {"count": 1, f"field_{public_field.id}": "a"},
                {"count": 1, f"field_{public_field.id}": "b"},
            ]
        )
    }


@pytest.mark.django_db
def test_list_rows_public_with_query_param_group_by_and_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    select_1 = data_fixture.create_single_select_field(name="Select", table=table)
    option_1 = data_fixture.create_select_option(field=select_1, value="A", order=3)
    option_2 = data_fixture.create_select_option(field=select_1, value="B", order=1)
    option_3 = data_fixture.create_select_option(field=select_1, value="C", order=2)
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, field_1, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, select_1, hidden=False)

    model = table.get_model(attribute_names=True)
    row_1 = model.objects.create(name="Product 1", select_id=option_1.id)
    row_2 = model.objects.create(name="Product 2", select_id=option_2.id)
    row_3 = model.objects.create(name="Product 3", select_id=option_3.id)

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    response = api_client.get(
        f"{url}?group_by=field_{select_1.id}[unknown]",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"

    response = api_client.get(
        f"{url}?group_by=field_{select_1.id}[order]",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"][0]["id"] == row_2.id
    assert response_json["results"][1]["id"] == row_3.id
    assert response_json["results"][2]["id"] == row_1.id


@pytest.mark.django_db
def test_list_rows_public_filters_by_visible_and_hidden_columns(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")

    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )

    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    data_fixture.create_view_filter(
        view=grid_view, field=hidden_field, type="equal", value="y"
    )
    data_fixture.create_view_filter(
        view=grid_view, field=public_field, type="equal", value="a"
    )
    # A row whose hidden column doesn't match the first filter
    RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "not y"}, user_field_names=True
    )
    # A row whose public column doesn't match the second filter
    RowHandler().create_row(
        user, table, values={"public": "not a", "hidden": "y"}, user_field_names=True
    )
    # A row which matches all filters
    visible_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )

    # Get access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug})
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["results"]) == 1
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == visible_row.id


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("search_mode", ALL_SEARCH_MODES)
@pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)
def test_list_rows_public_only_searches_by_visible_columns(
    api_client, data_fixture, search_mode
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")

    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )

    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    search_term = "search_term"
    RowHandler().create_row(
        user,
        table,
        values={"public": "other", "hidden": search_term},
        user_field_names=True,
    )
    RowHandler().create_row(
        user,
        table,
        values={"public": "other", "hidden": "other"},
        user_field_names=True,
    )
    visible_row = RowHandler().create_row(
        user,
        table,
        values={"public": search_term, "hidden": "other"},
        user_field_names=True,
    )

    # Get access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug})
        + f"?search={search_term}&search_mode={search_mode}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["results"]) == 1
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == visible_row.id


@pytest.mark.django_db
def test_grid_view_link_row_lookup_view(api_client, data_fixture):
    field_handler = FieldHandler()
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    lookup_table = data_fixture.create_database_table(database=database)
    grid = data_fixture.create_grid_view(table=table)
    grid_2 = data_fixture.create_grid_view()
    text_field = data_fixture.create_text_field(table=table)
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        link_row_table=lookup_table,
        name="Link row 1",
    )
    disabled_link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        link_row_table=lookup_table,
        name="Link row 2",
    )
    unrelated_link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        link_row_table=lookup_table,
        name="Link row 3",
    )
    primary_related_field = data_fixture.create_text_field(
        table=lookup_table, primary=True
    )
    data_fixture.create_text_field(table=lookup_table)
    data_fixture.create_grid_view_field_option(grid, text_field, hidden=False, order=1)
    data_fixture.create_grid_view_field_option(
        grid, link_row_field, hidden=False, order=2
    )
    data_fixture.create_grid_view_field_option(
        grid, disabled_link_row_field, hidden=True, order=3
    )
    data_fixture.create_grid_view_field_option(
        grid, unrelated_link_row_field, hidden=True, order=4
    )
    data_fixture.create_grid_view_field_option(
        grid_2, unrelated_link_row_field, hidden=False, order=1
    )

    lookup_model = lookup_table.get_model()
    i1 = lookup_model.objects.create(**{f"field_{primary_related_field.id}": "Test 1"})
    i2 = lookup_model.objects.create(**{f"field_{primary_related_field.id}": "Test 2"})
    i3 = lookup_model.objects.create(**{f"field_{primary_related_field.id}": "Test 3"})
    i4 = lookup_model.objects.create(**{f"field_{primary_related_field.id}": "Test 4"})

    # Because the `restrict_link_row_public_view_sharing` property is True for the
    # grid view type, only related values that have relationship with the table and
    # are visible in the view will be exposed via the endpoint. By adding the first
    # three to the row that matches the filters, the fourth one, should never be
    # visible via this endpoint.
    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "match"})
    getattr(row, f"field_{link_row_field.id}").add(i1.id, i2.id, i3.id)
    row_2 = model.objects.create(**{f"field_{text_field.id}": "no match"})
    getattr(row_2, f"field_{link_row_field.id}").add(i4.id)

    # Anonymous, not existing slug.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": "NOT_EXISTING", "field_id": link_row_field.id},
    )
    response = api_client.get(url, {})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # Anonymous, existing slug, but form is not public.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # user that doesn't have access to the workspace, existing slug,
    # but form is not public.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token_2}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # valid user, existing slug, but invalid wrong field type.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": text_field.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # valid user, existing slug, but invalid wrong field type.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": 0},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # valid user, existing slug, but disabled link row field.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": disabled_link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # valid user, existing slug, but unrelated link row field.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": unrelated_link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    grid.public = True
    grid.save()

    # anonymous, existing slug, public form, correct link row field without any
    # filters applied to the view.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 4
    assert len(response_json["results"]) == 4

    # anonymous, existing slug, public form, correct link row field after applying a
    # filter.
    data_fixture.create_view_filter(user, view=grid, field=text_field, value="match")
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 3
    assert len(response_json["results"]) == 3
    assert response_json["results"][0]["id"] == i1.id
    assert response_json["results"][0]["value"] == "Test 1"
    assert response_json["results"][1]["id"] == i2.id
    assert response_json["results"][2]["id"] == i3.id

    # same as before only now with search.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        f"{url}?search=Test 2",
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == i2.id
    assert response_json["results"][0]["value"] == "Test 2"

    # same as before only now with pagination
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": grid.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        f"{url}?size=1&page=2",
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 3
    assert response_json["next"] is not None
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == i2.id
    assert response_json["results"][0]["value"] == "Test 2"


@pytest.mark.django_db
def test_list_rows_include_fields(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(database=table.database)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Link",
        link_row_table=table_2,
    )
    primary_field = data_fixture.create_text_field(table=table_2, primary=True)
    lookup_model = table_2.get_model()
    i1 = lookup_model.objects.create(**{f"field_{primary_field.id}": "Test 1"})
    i2 = lookup_model.objects.create(**{f"field_{primary_field.id}": "Test 2"})
    i3 = lookup_model.objects.create(**{f"field_{primary_field.id}": "Test 3"})

    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_grid_view_field_option(grid, link_row_field, hidden=False)

    model = grid.table.get_model()
    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
            f"field_{boolean_field.id}": False,
        }
    )
    getattr(row_1, f"field_{link_row_field.id}").add(i1.id)
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{number_field.id}": 100,
            f"field_{boolean_field.id}": True,
        }
    )
    getattr(row_2, f"field_{link_row_field.id}").add(i2.id)
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "Purple",
            f"field_{number_field.id}": 1000,
            f"field_{boolean_field.id}": False,
        }
    )
    getattr(row_3, f"field_{link_row_field.id}").add(i3.id)

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        {
            "include_fields": f"\
                field_{text_field.id},\
                field_{number_field.id},\
                field_{link_row_field.id}",
            "exclude_fields": f"field_{number_field.id}",
        },
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    # Confirm that text_field is included
    assert response_json["results"][0][f"field_{text_field.id}"] == "Green"
    assert response_json["results"][1][f"field_{text_field.id}"] == "Orange"
    assert response_json["results"][2][f"field_{text_field.id}"] == "Purple"

    # Confirm that number_field is excluded
    assert f"field_{number_field.id}" not in response_json["results"][0]
    assert f"field_{number_field.id}" not in response_json["results"][1]
    assert f"field_{number_field.id}" not in response_json["results"][2]

    # Confirm that boolean_field is not returned
    assert f"field_{boolean_field.id}" not in response_json["results"][0]
    assert f"field_{boolean_field.id}" not in response_json["results"][1]
    assert f"field_{boolean_field.id}" not in response_json["results"][2]

    # Confirm that link_row_field is included
    assert (
        response_json["results"][0][f"field_{link_row_field.id}"][0]["value"]
        == "Test 1"
    )
    assert (
        response_json["results"][1][f"field_{link_row_field.id}"][0]["value"]
        == "Test 2"
    )
    assert (
        response_json["results"][2][f"field_{link_row_field.id}"][0]["value"]
        == "Test 3"
    )

    # Confirm that id and order are still returned
    assert "id" in response_json["results"][0]
    assert "id" in response_json["results"][1]
    assert "id" in response_json["results"][2]
    assert "order" in response_json["results"][0]
    assert "order" in response_json["results"][1]
    assert "order" in response_json["results"][2]

    # include_fields is empty
    response = api_client.get(
        url,
        {"include_fields": ""},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    # Should return response with no fields
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "id" in response_json["results"][0]
    assert "order" in response_json["results"][0]
    assert f"field_{text_field.id}" not in response_json["results"][0]
    assert f"field_{number_field.id}" not in response_json["results"][0]
    assert f"field_{boolean_field.id}" not in response_json["results"][0]

    # Test invalid fields
    response = api_client.get(
        url,
        {"include_fields": "field_9999"},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    # Should also return response with no fields
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "id" in response_json["results"][0]
    assert "id" in response_json["results"][0]
    assert "order" in response_json["results"][0]
    assert f"field_{text_field.id}" not in response_json["results"][0]
    assert f"field_{number_field.id}" not in response_json["results"][0]
    assert f"field_{boolean_field.id}" not in response_json["results"][0]


@pytest.mark.django_db
def test_user_with_wrong_password_cant_get_info_about_a_public_password_protected_grid_view(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    grid_view = data_fixture.create_public_password_protected_grid_view(
        user=user, password="12345678"
    )

    response = api_client.post(
        reverse("api:database:views:public_auth", kwargs={"slug": grid_view.slug}),
        {"password": "wrong_password"},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_invalid_search_mode_raises(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    grid_view = data_fixture.create_grid_view(
        table=table,
        user=user,
    )

    response = api_client.get(
        reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        + f"?search=test&search_mode=invalid"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json == {
        "detail": {
            "search_mode": [
                {"code": "invalid_choice", "error": '"invalid" is not a valid choice.'}
            ]
        },
        "error": "ERROR_QUERY_PARAMETER_VALIDATION",
    }


@pytest.mark.django_db
def test_list_rows_public_advanced_filters_are_preferred_to_other_filter_query_params(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug}
    )
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": public_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": public_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }
    get_params = [
        "filters=" + json.dumps(advanced_filters),
        f"filter__field_{public_field.id}__equal=z",
        f"filter_type=AND",
    ]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2


@pytest.mark.django_db
def test_list_grid_rows_adhoc_filtering_query_param_filter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="normal")
    # hidden field should behave the same as normal one
    text_field_hidden = data_fixture.create_text_field(table=table, name="hidden")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, text_field, hidden=False)
    data_fixture.create_grid_view_field_option(
        grid_view, text_field_hidden, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"normal": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"normal": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    get_params = [f"filter__field_{text_field.id}__contains=a"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    get_params = [
        f"filter__field_{text_field.id}__contains=a",
        f"filter__field_{text_field.id}__contains=b",
        f"filter_type=OR",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    get_params = [f"filter__field_{text_field_hidden.id}__contains=y"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    get_params = [f"filter__field_{text_field.id}__random=y"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    get_params = [f"filter__field_{text_field.id}__higher_than=1"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"


@pytest.mark.django_db
def test_list_grid_rows_adhoc_filtering_query_param_null_character(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="normal")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, create_options=False
    )
    first_row = RowHandler().create_row(
        user, table, values={"normal": "a"}, user_field_names=True
    )
    RowHandler().create_row(user, table, values={"normal": "b"}, user_field_names=True)

    str_with_null_character = "a\0"
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    get_params = [f"filter__field_{text_field.id}__contains={str_with_null_character}"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id


@pytest.mark.django_db
def test_list_grid_rows_adhoc_filtering_invalid_advanced_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, text_field, hidden=False)

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})

    expected_errors = [
        (
            "invalid_json",
            {
                "error": "The provided filters are not valid JSON.",
                "code": "invalid_json",
            },
        ),
        (
            json.dumps({"filter_type": "invalid"}),
            {
                "filter_type": [
                    {
                        "error": '"invalid" is not a valid choice.',
                        "code": "invalid_choice",
                    }
                ]
            },
        ),
        (
            json.dumps(
                {"filter_type": "OR", "filters": "invalid", "groups": "invalid"}
            ),
            {
                "filters": [
                    {
                        "error": 'Expected a list of items but got type "str".',
                        "code": "not_a_list",
                    }
                ],
                "groups": {
                    "non_field_errors": [
                        {
                            "error": 'Expected a list of items but got type "str".',
                            "code": "not_a_list",
                        }
                    ],
                },
            },
        ),
    ]

    for filters, error_detail in expected_errors:
        get_params = [f"filters={filters}"]
        response = api_client.get(
            f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"
        assert response_json["detail"] == error_detail


@pytest.mark.django_db
def test_list_grid_rows_adhoc_filtering_advanced_filters_are_preferred_to_other_filter_query_params(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, text_field)

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": text_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }
    get_params = [
        "filters=" + json.dumps(advanced_filters),
        f"filter__field_{text_field.id}__equal=z",
        f"filter_type=AND",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2


@pytest.mark.django_db
def test_list_grid_rows_adhoc_filtering_overrides_existing_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    # in usual scenario this filter would filtered out all rows
    equal_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="equal", value="y"
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": text_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }

    get_params = [
        "filters=" + json.dumps(advanced_filters),
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2


@pytest.mark.django_db
def test_list_grid_rows_adhoc_filtering_advanced_filters(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    # hidden fields should behave like normal ones
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, public_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, hidden_field, hidden=True)

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "contains",
                "value": "a",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "OR",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "a",
                    },
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "b",
                    },
                ],
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    # groups can be arbitrarily nested
    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "AND",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "",
                    },
                ],
                "groups": [
                    {
                        "filter_type": "OR",
                        "filters": [
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "a",
                            },
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "b",
                            },
                        ],
                    },
                ],
            },
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": hidden_field.id,
                "type": "contains",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "random",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "higher_than",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"

    for filters in [
        "invalid_json",
        json.dumps({"filter_type": "invalid"}),
        json.dumps({"filter_type": "OR", "filters": "invalid"}),
    ]:
        get_params = [f"filters={filters}"]
        response = api_client.get(
            f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"


@pytest.mark.django_db
def test_list_rows_with_limit_without_count(api_client, data_fixture):
    """
    Test that count is not called when exclude_count=true is passed in the
    query params together with limit.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    rows = RowHandler().force_create_rows(
        user, table, rows_values=[{} for i in range(5)]
    )

    count_calls = 0

    def reset_count():
        nonlocal count_calls
        count_calls = 0

    class MockTableModelQuerySet(TableModelQuerySet):
        def count(self):
            nonlocal count_calls

            count_calls += 1
            return super().count()

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?limit=10&offset=0", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 5
        assert response_json["count"] == 5
        assert count_calls == 1

    reset_count()

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?limit=10&offset=0&exclude_count=true",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 5
        assert "count" not in response_json
        assert count_calls == 0  # count is not called

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?exclude_count=true&limit=10&offset=100",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 0
        assert "count" not in response_json
        assert count_calls == 0  # count is not called


@pytest.mark.django_db
def test_list_rows_with_limit_and_invalid_numbers(api_client, data_fixture):
    """
    If invalid values are provided, the first page and the first 100 results should be
    returned.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    rows = RowHandler().force_create_rows(
        user,
        table,
        rows_values=[
            {
                text_field.db_column: f"{i}",
            }
            for i in range(101)
        ],
    )

    count_calls = 0

    def reset_count():
        nonlocal count_calls
        count_calls = 0

    class MockTableModelQuerySet(TableModelQuerySet):
        def count(self):
            nonlocal count_calls

            count_calls += 1
            return super().count()

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?limit=-1&offset=-2", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 100  # 100 is the default limit
        assert response_json["count"] == 101
        # return the first 100 rows
        assert response_json["results"][0][f"field_{text_field.id}"] == "0"
        assert response_json["results"][99][f"field_{text_field.id}"] == "99"
        assert count_calls == 1

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?limit=a&offset=b", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 100  # 100 is the default limit
        assert response_json["count"] == 101
        # return the first 100 rows
        assert response_json["results"][0][f"field_{text_field.id}"] == "0"
        assert response_json["results"][99][f"field_{text_field.id}"] == "99"
        assert count_calls == 2

    reset_count()

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?limit=-1&offset=-2&exclude_count=true",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 100  # 100 is the default limit
        assert response_json["count"] == 101
        # return the first 100 rows
        assert response_json["results"][0][f"field_{text_field.id}"] == "0"
        assert response_json["results"][99][f"field_{text_field.id}"] == "99"
        assert count_calls == 0

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?limit=a&offset=b&exclude_count=true",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 100  # 100 is the default limit
        assert response_json["count"] == 101
        # return the first 100 rows
        assert response_json["results"][0][f"field_{text_field.id}"] == "0"
        assert response_json["results"][99][f"field_{text_field.id}"] == "99"
        assert count_calls == 0


@pytest.mark.django_db
def test_list_rows_with_page_without_count(api_client, data_fixture):
    """
    Test that count is not called when exclude_count=true is passed in the
    query params together with limit.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    rows = RowHandler().force_create_rows(
        user, table, rows_values=[{} for i in range(5)]
    )

    count_calls = 0

    def reset_count():
        nonlocal count_calls
        count_calls = 0

    class MockTableModelQuerySet(TableModelQuerySet):
        def count(self):
            nonlocal count_calls

            count_calls += 1
            return super().count()

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(f"{url}?page=1", HTTP_AUTHORIZATION=f"JWT {token}")
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 5
        assert response_json["count"] == 5
        assert count_calls == 1

    reset_count()

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?page=1&exclude_count=true", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 5
        assert "count" not in response_json
        assert count_calls == 0  # count is not called again

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?page=10&exclude_count=true", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 0
        assert "count" not in response_json
        assert count_calls == 0  # count is not called again


@pytest.mark.django_db
def test_list_rows_with_page_and_invalid_numbers(api_client, data_fixture):
    """
    If invalid values are provided, the first page and the first 100 results should be
    returned.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    rows = RowHandler().force_create_rows(
        user,
        table,
        rows_values=[
            {
                text_field.db_column: f"{i}",
            }
            for i in range(101)
        ],
    )

    count_calls = 0

    def reset_count():
        nonlocal count_calls
        count_calls = 0

    class MockTableModelQuerySet(TableModelQuerySet):
        def count(self):
            nonlocal count_calls

            count_calls += 1
            return super().count()

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?page=-1&size=-1", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 100  # 100 is the default size
        assert response_json["count"] == 101
        # return the first 100 rows
        assert response_json["results"][0][f"field_{text_field.id}"] == "0"
        assert response_json["results"][99][f"field_{text_field.id}"] == "99"
        assert count_calls == 1

    reset_count()

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?page=-1&size=-1&exclude_count=true",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert "count" not in response_json
        assert len(response_json["results"]) == 100
        # return the first 100 rows
        assert response_json["results"][0][f"field_{text_field.id}"] == "0"
        assert response_json["results"][99][f"field_{text_field.id}"] == "99"
        assert count_calls == 0  # count is not called again

    with patch(
        "baserow.contrib.database.table.models.TableModelQuerySet",
        MockTableModelQuerySet,
    ):
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(
            f"{url}?page=a&size=b&exclude_count=true", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json["results"]) == 100
        assert "count" not in response_json
        assert response_json["results"][0][f"field_{text_field.id}"] == "0"
        assert response_json["results"][99][f"field_{text_field.id}"] == "99"
        assert count_calls == 0  # count is not called again
