from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import Q
from django.shortcuts import reverse
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler, ViewIndexingHandler
from baserow.contrib.database.views.models import (
    GalleryViewFieldOptions,
    GridView,
    GridViewFieldOptions,
    View,
)
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.views.view_types import GridViewType
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import AnyStr, setup_interesting_test_table


@pytest.fixture(autouse=True)
def clean_registry_cache():
    """
    Ensure no patched version stays in cache.
    """

    view_type_registry.get_for_class.cache_clear()
    yield


@pytest.mark.django_db
def test_list_views(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    view_1 = data_fixture.create_grid_view(table=table_1, order=1)
    view_2 = data_fixture.create_grid_view(table=table_1, order=3)
    view_3 = data_fixture.create_grid_view(
        table=table_1, order=2, filter_type="OR", filters_disabled=True
    )
    data_fixture.create_grid_view(table=table_2, order=1)

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table_1.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json) == 3

    assert response_json[0]["id"] == view_1.id
    assert response_json[0]["type"] == "grid"
    assert response_json[0]["filter_type"] == "AND"
    assert response_json[0]["filters_disabled"] is False

    assert response_json[1]["id"] == view_3.id
    assert response_json[1]["type"] == "grid"
    assert response_json[1]["filter_type"] == "OR"
    assert response_json[1]["filters_disabled"] is True

    assert response_json[2]["id"] == view_2.id
    assert response_json[2]["type"] == "grid"
    assert response_json[2]["filter_type"] == "AND"
    assert response_json[2]["filters_disabled"] is False

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table_2.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": 999999}),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    url = reverse("api:database:views:list", kwargs={"table_id": table_1.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    data_fixture.create_template(workspace=table_1.database.workspace)
    table_1.database.workspace.has_template.cache_clear()
    url = reverse("api:database:views:list", kwargs={"table_id": table_1.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK

    response = api_client.delete(
        reverse(
            "api:workspaces:item",
            kwargs={"workspace_id": table_1.database.workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse("api:database:views:list", kwargs={"table_id": table_1.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@override_settings(PERMISSION_MANAGERS=["basic"])
@pytest.mark.django_db
def test_list_views_ownership_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    view_1 = data_fixture.create_grid_view(
        table=table_1, order=1, ownership_type="collaborative"
    )
    view_2 = data_fixture.create_grid_view(
        table=table_1, order=3, ownership_type="personal"
    )

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table_1.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 2


@pytest.mark.django_db
def test_list_views_with_limit(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    view_1 = data_fixture.create_grid_view(table=table_1, order=1)
    data_fixture.create_grid_view(table=table_1, order=3)

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table_1.id}),
        {"limit": 1},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == view_1.id


@pytest.mark.django_db
def test_list_views_with_type_filter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table_1, order=1)
    gallery = data_fixture.create_gallery_view(table=table_1, order=2)

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table_1.id}),
        {"type": "grid"},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == grid.id

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table_1.id}),
        {"type": "gallery"},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == gallery.id


@pytest.mark.django_db
def test_list_views_doesnt_do_n_queries(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    view_1 = data_fixture.create_grid_view(table=table_1, order=1)
    view_2 = data_fixture.create_grid_view(table=table_1, order=3)
    view_3 = data_fixture.create_grid_view(
        table=table_1, order=2, filter_type="OR", filters_disabled=True
    )
    data_fixture.create_grid_view(table=table_2, order=1)

    with CaptureQueriesContext(connection) as query_for_n:
        response = api_client.get(
            reverse("api:database:views:list", kwargs={"table_id": table_1.id}),
            **{"HTTP_AUTHORIZATION": f"JWT {token}"},
        )
        assert response.status_code == HTTP_200_OK
        response.json()

    view_4 = data_fixture.create_grid_view(table=table_1, order=3)

    with CaptureQueriesContext(connection) as query_for_n_plus_one:
        response = api_client.get(
            reverse("api:database:views:list", kwargs={"table_id": table_1.id}),
            **{"HTTP_AUTHORIZATION": f"JWT {token}"},
        )
        assert response.status_code == HTTP_200_OK
        response.json()

    assert len(query_for_n.captured_queries) >= len(
        query_for_n_plus_one.captured_queries
    )


@pytest.mark.django_db
def test_get_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user_2)
    view = data_fixture.create_grid_view(table=table)
    view_2 = data_fixture.create_grid_view(table=table_2)
    view_filter = data_fixture.create_view_filter(view=view)

    url = reverse("api:database:views:item", kwargs={"view_id": view_2.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:item", kwargs={"view_id": 99999})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == view.id
    assert response_json["table_id"] == view.table_id
    assert response_json["type"] == "grid"
    assert response_json["table"]["id"] == table.id
    assert response_json["filter_type"] == "AND"
    assert not response_json["filters_disabled"]
    assert "filters" not in response_json
    assert "sortings" not in response_json
    assert "group_bys" not in response_json
    assert "decorations" not in response_json

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.get(
        "{}?include=filters,sortings,group_bys,decorations".format(url),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == view.id
    assert len(response_json["filters"]) == 1
    assert response_json["filters"][0]["id"] == view_filter.id
    assert response_json["filters"][0]["view"] == view_filter.view_id
    assert response_json["filters"][0]["field"] == view_filter.field_id
    assert response_json["filters"][0]["type"] == view_filter.type
    assert response_json["filters"][0]["value"] == view_filter.value
    assert response_json["sortings"] == []
    assert response_json["decorations"] == []
    assert response_json["group_bys"] == []

    response = api_client.delete(
        reverse(
            "api:workspaces:item",
            kwargs={"workspace_id": view.table.database.workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_view_default_row_values(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)

    ViewHandler().update_view_default_values(
        user=user,
        view=view,
        items=[{"field": text_field.id, "enabled": True, "value": "test default"}],
    )

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})

    # Without include param - should NOT have default_row_values.
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert "default_row_values" not in response.json()

    # With include param - should have default_row_values.
    response = api_client.get(
        f"{url}?include=default_row_values",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert "default_row_values" in data
    assert isinstance(data["default_row_values"], list)
    assert len(data["default_row_values"]) == 1
    assert data["default_row_values"][0]["field"] == text_field.id
    assert data["default_row_values"][0]["value"] == "test default"


@pytest.mark.django_db
def test_delete_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user_2)
    view = data_fixture.create_grid_view(table=table)
    view_2 = data_fixture.create_grid_view(table=table_2)

    url = reverse("api:database:views:item", kwargs={"view_id": view_2.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:item", kwargs={"view_id": 99999})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 204

    assert GridView.objects.all().count() == 1


@pytest.mark.django_db
def test_duplicate_views(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table_1)
    table_2 = data_fixture.create_database_table()
    view_1 = data_fixture.create_grid_view(table=table_1, order=1)
    view_2 = data_fixture.create_grid_view(table=table_2, order=2)
    view_3 = data_fixture.create_grid_view(table=table_1, order=3)

    field_option = data_fixture.create_grid_view_field_option(
        grid_view=view_1,
        field=field,
        aggregation_type="whatever",
        aggregation_raw_type="empty",
    )
    view_filter_group = data_fixture.create_view_filter_group(view=view_1)
    view_filter = data_fixture.create_view_filter(
        view=view_1,
        field=field,
        value="test",
        type="equal",
        group=view_filter_group,
    )
    view_sort = data_fixture.create_view_sort(view=view_1, field=field, order="ASC")
    view_group_by = data_fixture.create_view_group_by(
        view=view_1, field=field, order="ASC"
    )

    view_decoration = data_fixture.create_view_decoration(
        view=view_1,
        value_provider_conf={"config": 12},
    )

    response = api_client.post(
        reverse("api:database:views:duplicate", kwargs={"view_id": view_2.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse("api:database:views:duplicate", kwargs={"view_id": 999999}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    assert View.objects.count() == 3

    response = api_client.post(
        reverse("api:database:views:duplicate", kwargs={"view_id": view_1.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert View.objects.count() == 4

    assert response_json["id"] != view_1.id
    assert response_json["order"] == view_1.order + 1
    assert len(response_json["sortings"]) == 1
    assert len(response_json["filters"]) == 1
    assert len(response_json["filter_groups"]) == 1
    assert len(response_json["decorations"]) == 1
    assert len(response_json["group_bys"]) == 1


@pytest.mark.django_db
def test_order_views(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    view_1 = data_fixture.create_grid_view(table=table_1, order=1)
    view_2 = data_fixture.create_grid_view(table=table_1, order=2)
    view_3 = data_fixture.create_grid_view(table=table_1, order=3)

    response = api_client.post(
        reverse("api:database:views:order", kwargs={"table_id": table_2.id}),
        {"view_ids": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:database:views:order", kwargs={"table_id": 999999}),
        {"view_ids": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:database:views:order", kwargs={"table_id": table_1.id}),
        {"view_ids": [0]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_VIEW_NOT_IN_TABLE"

    response = api_client.post(
        reverse("api:database:views:order", kwargs={"table_id": table_1.id}),
        {"view_ids": ["test"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:database:views:order", kwargs={"table_id": table_1.id}),
        {
            "view_ids": [view_3.id, view_2.id, view_1.id],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    view_1.refresh_from_db()
    view_2.refresh_from_db()
    view_3.refresh_from_db()
    assert view_1.order == 3
    assert view_2.order == 2
    assert view_3.order == 1


@pytest.mark.django_db
def test_get_view_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table)
    grid_2 = data_fixture.create_grid_view()

    class GridViewWithNormalViewModel(GridViewType):
        field_options_serializer_class = None

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 0

    url = reverse("api:database:views:field_options", kwargs={"view_id": 999999})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid_2.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    with patch.dict(
        view_type_registry.registry, {"grid": GridViewWithNormalViewModel()}
    ):
        view_type_registry.get_for_class.cache_clear()
        url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
        response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS"


@pytest.mark.django_db
def test_get_view_field_options_as_template(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    data_fixture.create_template(workspace=grid.table.database.workspace)
    grid.table.database.workspace.has_template.cache_clear()
    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_patch_view_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table)
    grid_2 = data_fixture.create_grid_view()

    class GridViewWithoutFieldOptions(GridViewType):
        model_class = View

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {"field_options": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 0

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
        {"field_options": {99999: {}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_UNRELATED_FIELD"

    url = reverse("api:database:views:field_options", kwargs={"view_id": 999999})
    response = api_client.patch(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid_2.id})
    response = api_client.patch(
        url,
        {"field_options": {}},
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    # This test should be last because we change the content type of the grid view.
    with patch.dict(
        view_type_registry.registry, {"grid": GridViewWithoutFieldOptions()}
    ):
        grid.content_type = ContentType.objects.get(app_label="database", model="view")
        grid.save()
        url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
        response = api_client.patch(
            url,
            {"field_options": {}},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS"


@pytest.mark.django_db
def test_patch_view_field_options_as_template(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    data_fixture.create_template(workspace=grid.table.database.workspace)
    url = reverse("api:database:views:field_options", kwargs={"view_id": grid.id})
    response = api_client.patch(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED


@override_settings(PERMISSION_MANAGERS=["basic"])
@pytest.mark.django_db
def test_patch_view_validate_ownership_type_invalid_type(api_client, data_fixture):
    """A test to make sure that if an invalid `ownership_type` string is passed
    when updating the view, the `ownership_type` is not updated and this results
    in status 400 error with an error message.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(
        user=user,
        table=table,
    )

    previous_ownership_type = view.ownership_type
    data = {"ownership_type": "NON_EXISTENT"}
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": view.id}),
        data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_data = response.json()

    assert response.status_code == HTTP_400_BAD_REQUEST
    view.refresh_from_db()
    assert view.ownership_type == previous_ownership_type
    assert (
        response_data["detail"]["ownership_type"][0]["error"]
        == "Ownership type must be one of the above: 'collaborative','personal'"
        ",'restricted'."
    )


@pytest.mark.django_db
def test_rotate_slug(api_client, data_fixture):
    class UnShareableViewType(GridViewType):
        can_share = False

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_form_view(table=table)
    view_2 = data_fixture.create_form_view(public=True)
    grid_view = data_fixture.create_grid_view(user=user, table=table)
    old_slug = str(view.slug)

    url = reverse("api:database:views:rotate_slug", kwargs={"view_id": view_2.id})
    response = api_client.post(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    with patch.dict(view_type_registry.registry, {"grid": UnShareableViewType()}):
        url = reverse(
            "api:database:views:rotate_slug", kwargs={"view_id": grid_view.id}
        )
        response = api_client.post(
            url, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_CANNOT_SHARE_VIEW_TYPE"

    url = reverse("api:database:views:rotate_slug", kwargs={"view_id": 99999})
    response = api_client.post(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND

    url = reverse("api:database:views:rotate_slug", kwargs={"view_id": view.id})
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["slug"] != old_slug
    assert len(response_json["slug"]) == 43


@pytest.mark.django_db
def test_anon_user_cant_get_info_about_a_non_public_view(api_client, data_fixture):
    user = data_fixture.create_user()
    grid_view = data_fixture.create_grid_view(user=user, public=False)

    # Get access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug})
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json == {
        "detail": "The requested view does not exist.",
        "error": "ERROR_VIEW_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_user_in_wrong_workspace_cant_get_info_about_a_non_public_view(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    other_user, other_user_token = data_fixture.create_user_and_token()
    grid_view = data_fixture.create_grid_view(user=user, public=False)

    response = api_client.get(
        reverse(
            "api:database:views:public_info",
            kwargs={"slug": grid_view.slug},
        ),
        HTTP_AUTHORIZATION=f"JWT {other_user_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json == {
        "detail": "The requested view does not exist.",
        "error": "ERROR_VIEW_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_user_in_same_workspace_can_get_info_about_a_non_public_view(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    grid_view = data_fixture.create_grid_view(user=user, public=False)

    response = api_client.get(
        reverse(
            "api:database:views:public_info",
            kwargs={"slug": grid_view.slug},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert "fields" in response_json
    assert "view" in response_json


@pytest.mark.django_db
def test_cannot_get_info_about_not_eligibile_view_type(api_client, data_fixture):
    user = data_fixture.create_user()
    form_view = data_fixture.create_form_view(user=user, public=True)

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:public_info",
            kwargs={"slug": form_view.slug},
        ),
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json == {
        "detail": "The requested view does not exist.",
        "error": "ERROR_VIEW_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_cannot_get_info_about_trashed_view(api_client, data_fixture):
    user = data_fixture.create_user()
    grid_view = data_fixture.create_grid_view(user=user, public=True)

    TrashHandler.trash(
        user,
        grid_view.table.database.workspace,
        None,
        grid_view.table.database.workspace,
    )

    response = api_client.get(
        reverse(
            "api:database:views:public_info",
            kwargs={"slug": grid_view.slug},
        ),
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json == {
        "detail": "The requested view does not exist.",
        "error": "ERROR_VIEW_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_anon_user_cant_get_info_about_a_public_password_protected_view(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    grid_view = data_fixture.create_grid_view(user=user, public=True)

    # set password for the current view using the API
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": grid_view.id}),
        {"public_view_password": "12345678"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # Get access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug})
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    response_json = response.json()
    public_view_token = response_json.get("access_token", None)
    assert public_view_token is None


@pytest.mark.django_db
def test_public_view_password_validation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    grid_view = data_fixture.create_grid_view(user=user, public=True)

    # set password for the current view with 8 characters
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": grid_view.id}),
        {"public_view_password": "12345678"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # set password for the current view with 256 characters
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": grid_view.id}),
        {"public_view_password": "1" * 256},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # remove password for the current view
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": grid_view.id}),
        {"public_view_password": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # attempt setting password with less than 8 characters
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": grid_view.id}),
        {"public_view_password": "1234567"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["public_view_password"] == [
        {"code": "min_length", "error": "Ensure this field has at least 8 characters."}
    ]
    # attempt setting password more than 256 characters
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": grid_view.id}),
        {"public_view_password": "1" * 256},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # attempt setting password with more than 256 characters
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": grid_view.id}),
        {"public_view_password": "1" * 257},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["public_view_password"] == [
        {
            "code": "max_length",
            "error": "Ensure this field has no more than 256 characters.",
        }
    ]


@pytest.mark.django_db
def test_user_with_invalid_token_cant_get_info_about_a_public_password_protected_view(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    grid_view = data_fixture.create_public_password_protected_grid_view(
        user=user, password="12345678"
    )

    # can't get info about the view
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug}),
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT token",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_user_with_password_can_get_info_about_a_public_password_protected_view(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    password = "12345678"
    grid_view = data_fixture.create_public_password_protected_grid_view(
        user=user, password=password
    )

    # The body of the request must contains a password field
    response = api_client.post(
        reverse("api:database:views:public_auth", kwargs={"slug": grid_view.slug}),
        {"wrong_body_param": password},
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    # Get the authorization token
    response = api_client.post(
        reverse("api:database:views:public_auth", kwargs={"slug": grid_view.slug}),
        {"password": password},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    public_view_token = response_json.get("access_token", None)
    assert public_view_token is not None

    # Get access as with the authorization token
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug}),
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "fields": [],
        "view": {
            "id": grid_view.slug,
            "name": grid_view.name,
            "order": 0,
            "public": True,
            "slug": grid_view.slug,
            "sortings": [],
            "group_bys": [],
            "table": {
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "id": PUBLIC_PLACEHOLDER_ENTITY_ID,
            },
            "type": "grid",
            "row_identifier_type": grid_view.row_identifier_type,
            "row_height_size": grid_view.row_height_size,
            "frozen_column_count": 1,
            "show_logo": grid_view.show_logo,
            "allow_public_export": grid_view.allow_public_export,
            "ownership_type": "collaborative",
        },
    }

    # The original user can still access data
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "fields": [],
        "view": {
            "id": grid_view.slug,
            "name": grid_view.name,
            "order": 0,
            "public": True,
            "slug": grid_view.slug,
            "sortings": [],
            "group_bys": [],
            "table": {
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "id": PUBLIC_PLACEHOLDER_ENTITY_ID,
            },
            "type": "grid",
            "row_identifier_type": grid_view.row_identifier_type,
            "row_height_size": grid_view.row_height_size,
            "frozen_column_count": 1,
            "show_logo": grid_view.show_logo,
            "allow_public_export": grid_view.allow_public_export,
            "ownership_type": "collaborative",
        },
    }


@pytest.mark.django_db
def test_rotating_slug_of_a_public_password_protected_view_invalidate_previous_tokens(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    (
        grid_view,
        public_view_token,
    ) = data_fixture.create_public_password_protected_grid_view_with_token(
        user=user, password="12345678"
    )

    # rotating slug invalidate previous tokens
    response = api_client.post(
        reverse("api:database:views:rotate_slug", kwargs={"view_id": grid_view.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == grid_view.id
    new_slug = response_json["slug"]
    assert new_slug != grid_view.slug

    # Cannot access data anymore with the initial token
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": new_slug}),
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_view_creator_can_always_get_data_of_a_public_password_protected(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    password = "12345678"
    grid_view = data_fixture.create_public_password_protected_grid_view(
        user=user, password=password
    )

    # anon user cannot access
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug}),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    # user in a valid workspace can access data, event without password
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_user_in_wrong_workspace_need_the_password_to_access_password_protected_view(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    _, other_user_token = data_fixture.create_user_and_token()

    (
        grid_view,
        public_view_token,
    ) = data_fixture.create_public_password_protected_grid_view_with_token(
        user=user, password="12345678"
    )

    # user2 cannot access data
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_user_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    # Get access as with the authorization token
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug}),
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
        HTTP_AUTHORIZATION=f"JWT {other_user_token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_public_gallery_view_fields_include_cover_image(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    file_field = data_fixture.create_file_field(user=user, table=table)
    gallery_view = data_fixture.create_gallery_view(
        user=user, table=table, public=True, card_cover_image_field=file_field
    )
    data_fixture.create_gallery_view_field_option(gallery_view, file_field, hidden=True)

    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": gallery_view.slug}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["fields"]) == 1


@pytest.mark.django_db
def test_view_cant_update_show_logo(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user=user, table=table, show_logo=True)
    data = {"show_logo": False}

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": view.id}),
        data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    view.refresh_from_db()
    assert view.show_logo is True

    response_data = response.json()
    assert response_data["show_logo"] is True


@pytest.mark.django_db
def test_view_cant_update_allow_public_export(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(
        user=user, table=table, allow_public_export=False
    )
    data = {"allow_public_export": True}

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": view.id}),
        data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    view.refresh_from_db()
    assert view.allow_public_export is False

    response_data = response.json()
    assert response_data["allow_public_export"] is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.views.tasks.update_view_index.delay"
)
def test_loading_a_sortable_view_will_create_an_index(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)
    grid_view = data_fixture.create_grid_view(user=user, table=table)
    data_fixture.create_view_sort(view=grid_view, field=text_field, order="ASC")

    table_model = table.get_model()
    index = ViewIndexingHandler.get_index(grid_view, table_model)
    assert ViewIndexingHandler.does_index_exist(index.name) is False

    with override_settings(AUTO_INDEX_VIEW_ENABLED=True):
        response = api_client.get(
            reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id}),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    assert ViewIndexingHandler.does_index_exist(index.name) is True


@pytest.mark.django_db
def test_can_limit_linked_items_in_views(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)

    rows_b = RowHandler().force_create_rows(user, table_b, [{}] * 3).created_rows
    RowHandler().force_create_rows(
        user, table_a, [{link_a_to_b.db_column: [row.id for row in rows_b]}]
    )

    grid = data_fixture.create_grid_view(user=user, table=table_a)
    grid_url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    resp = api_client.get(grid_url, HTTP_AUTHORIZATION=f"JWT {token}", format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 3

    # Limit the linked items to 2
    resp = api_client.get(
        f"{grid_url}?limit_linked_items=2",
        HTTP_AUTHORIZATION=f"JWT {token}",
        format="json",
    )
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 2

    gallery = data_fixture.create_gallery_view(user=user, table=table_a)
    gallery_url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery.id}
    )
    resp = api_client.get(gallery_url, HTTP_AUTHORIZATION=f"JWT {token}", format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 3

    # Limit the linked items to 2
    resp = api_client.get(
        f"{gallery_url}?limit_linked_items=2",
        HTTP_AUTHORIZATION=f"JWT {token}",
        format="json",
    )
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 2


@pytest.mark.django_db
def test_can_limit_linked_items_in_public_views(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)

    rows_b = RowHandler().force_create_rows(user, table_b, [{}] * 3).created_rows
    RowHandler().force_create_rows(
        user, table_a, [{link_a_to_b.db_column: [row.id for row in rows_b]}]
    )

    grid = data_fixture.create_grid_view(user=user, table=table_a, public=True)
    GridViewFieldOptions.objects.update(hidden=False)
    grid_url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid.slug}
    )
    resp = api_client.get(grid_url, format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 3

    # Limit the linked items to 2
    resp = api_client.get(f"{grid_url}?limit_linked_items=2", format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 2

    gallery = data_fixture.create_gallery_view(user=user, table=table_a, public=True)
    GalleryViewFieldOptions.objects.update(hidden=False)

    gallery_url = reverse(
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery.slug}
    )
    resp = api_client.get(gallery_url, format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 3

    # Limit the linked items to 2
    resp = api_client.get(f"{gallery_url}?limit_linked_items=2", format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 2


@pytest.mark.django_db
def test_get_public_row(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    boolean_field = data_fixture.create_boolean_field(table=table)

    row_1, row_2, row_3, row_4 = (
        RowHandler()
        .force_create_rows(
            user,
            table,
            [
                {},
                {
                    f"field_{text_field.id}": "Green",
                    f"field_{number_field.id}": 10,
                    f"field_{boolean_field.id}": False,
                },
                {
                    f"field_{text_field.id}": "Orange",
                    f"field_{number_field.id}": 100,
                    f"field_{boolean_field.id}": True,
                },
                {
                    f"field_{text_field.id}": "Purple",
                    f"field_{number_field.id}": 1000,
                    f"field_{boolean_field.id}": False,
                },
            ],
        )
        .created_rows
    )

    # Non-existent view
    url = reverse(
        "api:database:views:public_row", kwargs={"slug": 999, "row_id": row_1.id}
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # Not allow access to rows of a private view
    private_view = data_fixture.create_grid_view(table=table)
    url = reverse(
        "api:database:views:public_row",
        kwargs={"slug": private_view.slug, "row_id": row_1.id},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # Not allow acces rows via a form view
    form_view = data_fixture.create_form_view(table=table, public=True)
    for row_id in [row_1.id, row_2.id, row_3.id, row_4.id]:
        url = reverse(
            "api:database:views:public_row",
            kwargs={"slug": form_view.slug, "row_id": row_1.id},
        )
        response = api_client.get(url)
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_SUPPORT_LISTING_ROWS"

    # Public view, non-existent row
    public_view = data_fixture.create_grid_view(table=table, public=True)
    url = reverse(
        "api:database:views:public_row",
        kwargs={"slug": public_view.slug, "row_id": 999},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    # Public view, existing row, but not available in the view due to filters
    public_view_without_row_1 = data_fixture.create_grid_view(table=table, public=True)
    data_fixture.create_view_filter(
        view=public_view_without_row_1, user=user, field=text_field, type="not_empty"
    )
    url = reverse(
        "api:database:views:public_row",
        kwargs={"slug": public_view_without_row_1.slug, "row_id": row_1.id},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    # Row 2 is available in the view, so it should return the row data
    url = reverse(
        "api:database:views:public_row",
        kwargs={"slug": public_view_without_row_1.slug, "row_id": row_2.id},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": row_2.id,
        "order": AnyStr(),
        f"field_{text_field.id}": "Green",
        f"field_{number_field.id}": "10",
        f"field_{boolean_field.id}": False,
    }

    # Public, password protected view, without proper password header
    password_protected_view = data_fixture.create_grid_view(
        table=table, public=True, public_view_password="password"
    )

    url = reverse(
        "api:database:views:public_row",
        kwargs={"slug": password_protected_view.slug, "row_id": 1},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"

    # public, password protected view, with proper password header
    public_view_token = ViewHandler().encode_public_view_token(password_protected_view)
    url = reverse(
        "api:database:views:public_row",
        kwargs={"slug": password_protected_view.slug, "row_id": row_2.id},
    )
    response = api_client.get(
        url, HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}"
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "id": row_2.id,
        "order": AnyStr(),
        f"field_{text_field.id}": "Green",
        f"field_{number_field.id}": "10",
        f"field_{boolean_field.id}": False,
    }

    # only the visible fields are returned (show only the text field)
    GridViewFieldOptions.objects.filter(
        Q(field=number_field) | Q(field=boolean_field), grid_view=public_view
    ).update(hidden=True)

    url = reverse(
        "api:database:views:public_row",
        kwargs={"slug": public_view.slug, "row_id": row_2.id},
    )
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "id": row_2.id,
        "order": AnyStr(),
        f"field_{text_field.id}": "Green",
    }


@pytest.mark.django_db
def test_patch_default_values(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)

    response = api_client.patch(
        reverse("api:database:views:default_values", kwargs={"view_id": view.id}),
        [{"field": text_field.id, "enabled": True, "value": "new default"}],
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["field"] == text_field.id
    assert data[0]["value"] == "new default"
    assert data[0]["enabled"] is True


@pytest.mark.django_db
def test_patch_default_values_with_now_function(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    date_field = data_fixture.create_date_field(table=table, date_include_time=True)
    view = data_fixture.create_grid_view(user=user, table=table)

    response = api_client.patch(
        reverse("api:database:views:default_values", kwargs={"view_id": view.id}),
        [{"field": date_field.id, "enabled": True, "function": "now"}],
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["field"] == date_field.id
    assert data[0]["function"] == "now"


@pytest.mark.django_db
def test_default_values_included_in_view_listing(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)

    ViewHandler().update_view_default_values(
        user=user,
        view=view,
        items=[{"field": text_field.id, "enabled": True, "value": "listing default"}],
    )

    # Without include param - should NOT have default_row_values.
    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert "default_row_values" not in response.json()[0]

    # With include param - should have default_row_values.
    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=default_row_values",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()[0]
    assert "default_row_values" in data
    assert isinstance(data["default_row_values"], list)
    assert len(data["default_row_values"]) == 1
    assert data["default_row_values"][0]["field"] == text_field.id
    assert data["default_row_values"][0]["value"] == "listing default"


@pytest.mark.django_db
def test_patch_default_values_empty(api_client, data_fixture):
    """
    Sending an empty PATCH (no values, no enabled fields) should succeed
    and return empty defaults. Reproduces the real scenario where the user
    opens the modal and saves without enabling any field.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)

    response = api_client.patch(
        reverse("api:database:views:default_values", kwargs={"view_id": view.id}),
        [],
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.django_db
def test_patch_default_values_empty_succeeds(api_client, data_fixture):
    """
    Sending an empty PATCH on a fresh table should succeed and return empty
    defaults without any errors.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)

    response = api_client.patch(
        reverse("api:database:views:default_values", kwargs={"view_id": view.id}),
        [],
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.django_db
def test_patch_default_values_with_interesting_table(api_client, data_fixture):
    """
    Sets default values for every writable field in the interesting test table
    via the API endpoint. This covers all field types and ensures the
    serialization / deserialization round-trip works for each one.
    """

    table, user, row, _, context = setup_interesting_test_table(data_fixture)
    token = data_fixture.generate_token(user)
    view = data_fixture.create_grid_view(user=user, table=table)

    model = table.get_model()
    row = model.objects.all().enhance_by_fields().get(id=row.id)

    # Serialize the row in response format, then convert to request format
    # for fields where the two differ (link_row, single_select, etc.).
    response_serializer = get_row_serializer_class(
        model, RowSerializer, is_response=True
    )
    row_data = response_serializer(row).data

    items = []
    for field_object in model.get_field_objects():
        field = field_object["field"]
        field_type = field_object["type"]
        field_name = f"field_{field.id}"

        if field.read_only or field_type.read_only:
            continue

        if field_name not in row_data:
            continue

        value = row_data[field_name]

        # Convert response format → request format for specific field types.
        # Single select: {"id": 1, "value": "A", "color": "blue"} → 1
        if isinstance(value, dict) and "id" in value and "value" in value:
            value = value["id"]
        # Link row / multiple select / multiple collaborators:
        # [{"id": 1, ...}, ...] → [1, 2, ...]
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            if "id" in value[0]:
                value = [item["id"] for item in value]

        items.append({"field": field.id, "enabled": True, "value": value})

    assert len(items) > 0, "Expected at least some writable fields"

    response = api_client.patch(
        reverse("api:database:views:default_values", kwargs={"view_id": view.id}),
        items,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    data = response.json()
    assert isinstance(data, list)
    returned_field_ids = {item["field"] for item in data}
    expected_field_ids = {item["field"] for item in items}
    assert returned_field_ids == expected_field_ids

    # Verify that a second update (editing existing records) also works.
    response = api_client.patch(
        reverse("api:database:views:default_values", kwargs={"view_id": view.id}),
        items,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()


@pytest.mark.django_db
def test_default_values_stored_in_request_format(api_client, data_fixture):
    """
    Sets default values from the interesting test table's existing row, then
    verifies that the stored default values are returned in the same request
    format that was sent to the API.
    """

    table, user, row, _, context = setup_interesting_test_table(data_fixture)
    token = data_fixture.generate_token(user)
    view = data_fixture.create_grid_view(user=user, table=table)

    model = table.get_model()
    row = model.objects.all().enhance_by_fields().get(id=row.id)

    # Serialize the existing row to get the response format, then convert to
    # request format (input) so we can set them as default values.
    response_serializer = get_row_serializer_class(
        model, RowSerializer, is_response=True
    )
    row_data = response_serializer(row).data

    # Field types whose response serialization cannot be round-tripped
    # (e.g. password returns True/False/None, AI returns generated text).
    non_roundtrip_types = {"password", "ai", "ai_choice"}

    items = []
    comparable_field_ids = []
    input_values_by_field_id = {}
    for field_object in model.get_field_objects():
        field = field_object["field"]
        field_type = field_object["type"]
        field_name = f"field_{field.id}"

        if field.read_only or field_type.read_only:
            continue

        if field_name not in row_data:
            continue

        value = row_data[field_name]

        # Convert response format → request format for specific field types.
        if isinstance(value, dict) and "id" in value and "value" in value:
            value = value["id"]
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            if "id" in value[0]:
                value = [item["id"] for item in value]

        items.append({"field": field.id, "enabled": True, "value": value})
        input_values_by_field_id[field.id] = value
        if field_type.type not in non_roundtrip_types:
            comparable_field_ids.append(field.id)

    # Set the default values via the API.
    patch_response = api_client.patch(
        reverse("api:database:views:default_values", kwargs={"view_id": view.id}),
        items,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert patch_response.status_code == HTTP_200_OK, patch_response.json()

    # Fetch the views list with default_row_values included.
    views_response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=default_row_values",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert views_response.status_code == HTTP_200_OK
    views_data = views_response.json()
    target_view = next(v for v in views_data if v["id"] == view.id)
    default_row_values = target_view["default_row_values"]

    # Build a lookup by field ID from the returned list.
    stored_by_field_id = {item["field"]: item["value"] for item in default_row_values}

    # Values are stored and returned in request format (the same format
    # that was sent to the PATCH endpoint).
    for field_id in comparable_field_ids:
        sent_value = input_values_by_field_id[field_id]
        stored_value = stored_by_field_id[field_id]
        assert stored_value == sent_value, (
            f"field_{field_id}: stored value {stored_value!r} != sent value {sent_value!r}"
        )


@pytest.mark.django_db
def test_patch_default_values_invalid_single_select_option(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(table=table)
    data_fixture.create_select_option(field=single_select_field, value="Valid")
    view = data_fixture.create_grid_view(user=user, table=table)

    response = api_client.patch(
        reverse("api:database:views:default_values", kwargs={"view_id": view.id}),
        [
            {
                "field": single_select_field.id,
                "enabled": True,
                "value": 999999,
            }
        ],
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
