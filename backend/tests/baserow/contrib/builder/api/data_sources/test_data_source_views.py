import json
from unittest.mock import ANY, MagicMock, patch

from django.db import transaction
from django.test import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.models import SORT_ORDER_ASC
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_RAW,
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormulaObject,
)
from baserow.core.services.models import Service
from baserow.core.user_sources.user_source_user import UserSourceUser
from baserow.test_utils.helpers import AnyInt, AnyStr, setup_interesting_test_table


@pytest.fixture
def data_source_fixture(data_fixture):
    """A fixture to help test views that rely on a data source."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
    )
    builder = data_fixture.create_builder_application(workspace=workspace, user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    user_source, _ = data_fixture.create_user_table_and_role(
        user,
        builder,
        "foo_user_role",
        integration=integration,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role="foo_user_role"
    )
    user_source_user_token = user_source_user.get_refresh_token().access_token

    return {
        "user": user,
        "token": token,
        "user_source_user": user_source_user,
        "user_source_user_token": user_source_user_token,
        "page": page,
        "integration": integration,
        "table": table,
        "rows": rows,
        "fields": fields,
    }


@pytest.mark.django_db
def test_get_data_sources(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    url = reverse("api:builder:data_source:list", kwargs={"page_id": page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    assert response_json[0]["id"] == data_source1.id
    assert response_json[0]["type"] == "local_baserow_get_row"
    assert "row_id" in response_json[0]
    assert response_json[1]["id"] == data_source2.id
    assert response_json[1]["type"] == "local_baserow_get_row"
    assert response_json[2]["id"] == data_source3.id
    assert response_json[2]["type"] == "local_baserow_list_rows"
    assert "row_id" not in response_json[2]


@pytest.mark.django_db
def test_create_data_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:data_source:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": "local_baserow_get_row"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "local_baserow_get_row"
    assert response_json["view_id"] is None
    assert response_json["table_id"] is None

    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        url,
        {
            "type": "local_baserow_get_row",
            "table_id": table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["table_id"] == table.id
    assert response_json["view_id"] is None


@pytest.mark.django_db
def test_create_data_source_bad_request(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:data_source:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": "local_baserow_get_row", "table_id": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_data_source_with_with_name_conflict(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, name="Blog posts"
    )

    url = reverse("api:builder:data_source:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "name": data_source.name,
            "type": "local_baserow_list_rows",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_DATA_SOURCE_NAME_NOT_UNIQUE",
        "detail": f"The data source name '{data_source.name}' already exists.",
    }


@pytest.mark.django_db
def test_create_data_source_permission_denied(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:data_source:list", kwargs={"page_id": page.id})
    with stub_check_permissions(raise_permission_denied=True):
        response = api_client.post(
            url,
            {"type": "local_baserow_get_row"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_create_data_source_page_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:data_source:list", kwargs={"page_id": 0})
    response = api_client.post(
        url,
        {"type": "local_baserow_get_row"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_PAGE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_data_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user, table=table)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )

    response = api_client.patch(
        url,
        {
            "table_id": table.id,
            "view_id": view.id,
            "row_id": '"test"',
            "name": "name test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["view_id"] == view.id
    assert response.json()["table_id"] == table.id
    assert response.json()["row_id"]["formula"] == '"test"'
    assert response.json()["name"] == "name test"


@pytest.mark.django_db
def test_update_data_source_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(user=user, builder=page.builder)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, name="name"
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )

    response = api_client.patch(
        url,
        {"page_id": page2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["page_id"] == page2.id
    assert response.json()["name"] == "name"


@pytest.mark.django_db
def test_update_data_source_with_with_name_conflict_is_disallowed_on_same_pages(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, name="Blog posts"
    )
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, name="Posts"
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source_2.id}
    )

    response = api_client.patch(
        url,
        {"name": data_source_1.name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_DATA_SOURCE_NAME_NOT_UNIQUE",
        "detail": f"The data source name '{data_source_1.name}' already exists.",
    }


@pytest.mark.django_db
def test_update_data_source_with_with_name_conflict(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(user=user, builder=page.builder)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, name="Conflict"
    )
    data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page2, name="Conflict"
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )

    response = api_client.patch(
        url,
        {"page_id": page2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["page_id"] == page2.id
    assert response.json()["name"] == "Conflict 2"


@pytest.mark.django_db
def test_update_data_source_with_filters(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    formula_field = data_fixture.create_text_field(table=table)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )

    # No existing filters, add one.
    response = api_client.patch(
        url,
        {
            "filters": [
                {
                    "field": text_field.id,
                    "type": "equals",
                    "value": BaserowFormulaObject(
                        formula="foobar",
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                        mode=BASEROW_FORMULA_MODE_RAW,
                    ),
                    "value_is_formula": False,
                },
                {
                    "field": formula_field.id,
                    "type": "equals",
                    "value": BaserowFormulaObject(
                        formula="get('page_parameter.id')",
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                        mode=BASEROW_FORMULA_MODE_SIMPLE,
                    ),
                    "value_is_formula": True,
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    service_filters = data_source1.service.service_filters.order_by("id")
    assert response.json()["filters"] == [
        {
            "id": service_filters[0].id,
            "order": service_filters[0].order,
            "field": text_field.id,
            "type": "equals",
            "value": BaserowFormulaObject(
                formula="foobar",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_RAW,
            ),
            "trashed": False,
            "value_is_formula": False,
        },
        {
            "id": service_filters[1].id,
            "order": service_filters[1].order,
            "field": formula_field.id,
            "type": "equals",
            "trashed": False,
            "value": BaserowFormulaObject(
                formula="get('page_parameter.id')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "value_is_formula": True,
        },
    ]

    # Reset the filters to nothing.
    response = api_client.patch(
        url,
        {"filters": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["filters"] == []

    # Given an existing filter, we delete it if it's not in the payload.
    data_fixture.create_local_baserow_table_service_filter(
        service=data_source1.service, field=text_field, value="baz", order=0
    )
    response = api_client.patch(
        url,
        {
            "filters": [
                {
                    "service": data_source1.service_id,
                    "field": text_field.id,
                    "type": "equals",
                    "value": BaserowFormulaObject(
                        formula="foobar",
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                        mode=BASEROW_FORMULA_MODE_RAW,
                    ),
                    "value_is_formula": False,
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    service_filter = data_source1.service.service_filters.get()
    assert response.json()["filters"] == [
        {
            "id": service_filter.id,
            "order": 0,
            "field": text_field.id,
            "type": "equals",
            "value": BaserowFormulaObject(
                formula="foobar",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_RAW,
            ),
            "trashed": False,
            "value_is_formula": False,
        }
    ]


@pytest.mark.django_db
def test_update_data_source_change_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    service = data_fixture.create_local_baserow_aggregate_rows_service(
        table_id=table.id,
    )
    data_source1 = data_fixture.create_builder_data_source(service=service, page=page)

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )

    response = api_client.patch(
        url,
        {"type": "local_baserow_list_rows", "field_id": None, "table_id": table.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_update_data_source_with_service_type_for_different_dispatch_type(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source.id}
    )

    response = api_client.patch(
        url,
        {"type": "local_baserow_upsert_row"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE"


@pytest.mark.django_db
def test_update_data_source_compatible_integration_is_persisted(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )

    response = api_client.patch(
        url,
        {"type": "local_baserow_list_rows"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["integration_id"] == data_source1.service.integration_id


@pytest.mark.django_db
def test_update_data_source_bad_request(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )
    response = api_client.patch(
        url,
        {"table_id": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_update_data_source_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:data_source:item", kwargs={"data_source_id": 0})
    response = api_client.patch(
        url,
        {"table_id": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DATA_SOURCE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_move_data_source_empty_payload(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:move", kwargs={"data_source_id": data_source1.id}
    )
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    assert DataSource.objects.last().id == data_source1.id


@pytest.mark.django_db
def test_move_data_source_null_before_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:move", kwargs={"data_source_id": data_source1.id}
    )
    response = api_client.patch(
        url,
        {"before_id": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    assert DataSource.objects.last().id == data_source1.id


@pytest.mark.django_db
def test_move_data_source_before(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:move", kwargs={"data_source_id": data_source3.id}
    )
    response = api_client.patch(
        url,
        {"before_id": data_source2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == data_source3.id

    assert list(DataSource.objects.all())[1].id == data_source3.id


@pytest.mark.django_db
def test_move_data_source_before_not_in_same_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page2
    )

    url = reverse(
        "api:builder:data_source:move", kwargs={"data_source_id": data_source3.id}
    )
    response = api_client.patch(
        url,
        {"before_id": data_source2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_DATA_SOURCE_NOT_IN_SAME_PAGE"


@pytest.mark.django_db
def test_create_data_source_with_service_type_for_different_dispatch_type(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:data_source:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": "local_baserow_upsert_row"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE"


@pytest.mark.django_db
def test_move_data_source_bad_before_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:move", kwargs={"data_source_id": data_source1.id}
    )
    response = api_client.patch(
        url,
        {"before_id": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_data_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    assert Service.objects.count() == 1
    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # Ensure the service also is deleted
    assert Service.objects.count() == 0


@pytest.mark.django_db
def test_delete_data_source_permission_denied(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source1.id}
    )

    with stub_check_permissions(raise_permission_denied=True):
        response = api_client.delete(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_delete_data_source_data_source_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:data_source:item", kwargs={"data_source_id": 0})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DATA_SOURCE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_dispatch_data_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="2",
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": 2,
        "order": AnyStr(),
        fields[0].name: "Audi",
        fields[1].name: "Orange",
    }


@pytest.mark.django_db
def test_dispatch_data_source_with_refinements_referencing_trashed_field(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    trashed_field = data_fixture.create_text_field(table=table, trashed=True)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )
    service_filter = data_fixture.create_local_baserow_table_service_filter(
        service=data_source.service, field=trashed_field, value="abc", order=0
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_SERVICE_FILTER_PROPERTY_DOES_NOT_EXIST",
        "detail": "A data source filter is misconfigured: "
        "One or more filtered properties no longer exist.",
    }

    service_filter.delete()

    data_fixture.create_local_baserow_table_service_sort(
        service=data_source.service,
        field=trashed_field,
        order_by=SORT_ORDER_ASC,
        order=0,
    )

    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_SERVICE_SORT_PROPERTY_DOES_NOT_EXIST",
        "detail": "A data source sort is misconfigured: "
        "One or more sorted properties no longer exist.",
    }


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
# pytest -k "test_dispatch_data_sources_perf" -s --run-disabled-in-ci
@override_settings(TESTS=False)
def test_dispatch_data_sources_perf(api_client, data_fixture, profiler):
    user, token = data_fixture.create_user_and_token()
    table1, _, _, _, _ = setup_interesting_test_table(data_fixture, user)
    table2, _, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            [["2CV", "Green"]] * 40,
        ],
    )
    table3, _, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            [["Twingo", "White"]] * 40,
        ],
    )

    view = data_fixture.create_grid_view(user, table=table1)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table1,
    )
    data_source2 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table2,
    )
    data_source3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table3,
    )

    url = reverse("api:builder:data_source:dispatch-all", kwargs={"page_id": page.id})

    with profiler(html_report_name="data_sources_dispatch_perf"):
        for _ in range(30):
            api_client.post(
                url,
                {},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )


@pytest.mark.django_db
def test_dispatch_data_source_with_adhoc_filters(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("SSN", "text"),
        ],
        rows=[
            ["Peter", "111"],
            ["Afonso", "222"],
            ["Tsering", "333"],
            ["Jérémie", "444"],
        ],
    )
    filterable_field = table.field_set.get(name="Name")
    private_field = table.field_set.get(name="SSN")
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
    )
    element = data_fixture.create_builder_table_element(
        page=page, data_source=data_source
    )
    element.property_options.create(
        schema_property=filterable_field.db_column, filterable=True
    )
    element.property_options.create(
        schema_property=private_field.db_column, filterable=False
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )

    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": filterable_field.id,
                "type": "equal",
                "value": "Peter",
            },
            {
                "field": filterable_field.id,
                "type": "equal",
                "value": "Jérémie",
            },
        ],
    }

    response = api_client.post(
        f"{url}?filters={json.dumps(advanced_filters)}",
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "results": [
            {
                "id": 1,
                "order": AnyStr(),
                filterable_field.name: "Peter",
                private_field.name: "111",
            },
            {
                "id": 4,
                "order": AnyStr(),
                filterable_field.name: "Jérémie",
                private_field.name: "444",
            },
        ],
        "has_next_page": False,
    }

    advanced_filters["filters"] = [
        {
            "field": private_field.id,
            "type": "equal",
            "value": "123",
        }
    ]

    response = api_client.post(
        f"{url}?filters={json.dumps(advanced_filters)}",
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN",
        "detail": "Data source filter, search and/or sort fields error: "
        f"{private_field.db_column} is not a filterable field.",
    }


@pytest.mark.django_db
def test_dispatch_data_source_with_adhoc_sortings(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("SSN", "text"),
        ],
        rows=[
            ["Peter", "111"],
            ["Afonso", "222"],
            ["Tsering", "333"],
            ["Jérémie", "444"],
        ],
    )
    sortable_field = table.field_set.get(name="Name")
    private_field = table.field_set.get(name="SSN")
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
    )
    element = data_fixture.create_builder_table_element(
        page=page, data_source=data_source
    )
    element.property_options.create(
        schema_property=sortable_field.db_column, sortable=True
    )
    element.property_options.create(
        schema_property=private_field.db_column, sortable=False
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )

    advanced_filters = {
        "filter_type": "OR",
        "filters": [],
    }

    response = api_client.post(
        f"{url}?filters={json.dumps(advanced_filters)}&order_by=-{sortable_field.db_column}",
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "results": [
            {
                "id": 3,
                "order": AnyStr(),
                sortable_field.name: "Tsering",
                private_field.name: AnyStr(),
            },
            {
                "id": 1,
                "order": AnyStr(),
                sortable_field.name: "Peter",
                private_field.name: AnyStr(),
            },
            {
                "id": 4,
                "order": AnyStr(),
                sortable_field.name: "Jérémie",
                private_field.name: AnyStr(),
            },
            {
                "id": 2,
                "order": AnyStr(),
                sortable_field.name: "Afonso",
                private_field.name: AnyStr(),
            },
        ],
        "has_next_page": False,
    }

    response = api_client.post(
        f"{url}?filters={json.dumps(advanced_filters)}&order_by=-{private_field.db_column}",
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN",
        "detail": "Data source filter, search and/or sort fields error: "
        f"{private_field.db_column} is not a sortable field.",
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)
def test_dispatch_data_source_with_adhoc_search(api_client, data_fixture):
    with transaction.atomic():
        user, token = data_fixture.create_user_and_token()
        table, fields, rows = data_fixture.build_table(
            user=user,
            columns=[
                ("Name", "text"),
                ("SSN", "text"),
            ],
            rows=[
                ["Peter", "111"],
                ["Afonso", "222"],
                ["Tsering", "333"],
                ["Jérémie", "444"],
            ],
        )
    searchable_field = table.field_set.get(name="Name")
    private_field = table.field_set.get(name="SSN")
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
    )
    element = data_fixture.create_builder_table_element(
        page=page, data_source=data_source
    )
    element.property_options.create(
        schema_property=searchable_field.db_column, searchable=True
    )
    element.property_options.create(
        schema_property=private_field.db_column, searchable=False
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )

    response = api_client.post(
        f"{url}?search_query=Peter",
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "results": [
            {
                "id": 1,
                "order": AnyStr(),
                searchable_field.name: "Peter",
                private_field.name: AnyStr(),
            }
        ],
        "has_next_page": False,
    }

    response = api_client.post(
        f"{url}?search_query=111",
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "results": [],
        "has_next_page": False,
    }

    # If there are no property options flagged as searchable,
    # then we need to ensure that no results are returned.
    element.property_options.update(searchable=False)

    response = api_client.post(
        f"{url}?search_query=Peter",
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "results": [],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_dispatch_data_source_with_element_from_different_page(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page_with_element = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_table_element(page=page_with_element)
    page_with_data_source = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page_with_data_source
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.post(
        url,
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["data_source"]["non_field_errors"] == [
        "The data source is not available for the dispatched element."
    ]


@pytest.mark.django_db
def test_dispatch_data_source_with_element_from_shared_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    page_with_element = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
        ],
    )

    page_with_element = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=page_with_element.builder
    )

    element = data_fixture.create_builder_table_element(page=page_with_element)

    shared_page = page_with_element.builder.shared_page
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=shared_page,
        integration=integration,
        table=table,
    )
    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.post(
        url,
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_dispatch_data_source_with_non_collection_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(builder=builder)
    element = data_fixture.create_builder_heading_element(page=page)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, primary=True)
    row = RowHandler().create_row(user, table, values={field.db_column: "a"})

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, integration=integration
    )
    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.post(
        url,
        {"metadata": {"data_source": {"element": element.id}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "results": [{"id": row.id, "order": AnyStr(), field.name: "a"}],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_dispatch_data_source_permission_denied(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="2",
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_dispatch_data_source_using_formula(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id='get("page_parameter.id")',
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )

    payload = {
        "metadata": json.dumps(
            {"page_parameter": {"id": 2}, "data_source": {"page_id": page.id}}
        )
    }

    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": 2,
        "order": AnyStr(),
        fields[0].name: "Audi",
        fields[1].name: "Orange",
    }


@pytest.mark.django_db
def test_dispatch_data_source_raises_service_improperly_configured(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "2"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source0 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="1",
        name="Working",
    )

    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        row_id='get("page_parameter.id")',
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        view=view,
        table=table,
        integration=None,
        row_id='get("page_parameter.id")',
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id='get("page_parameter.id")',
    )
    data_source4 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id='get("data_source.Working.My Color")',
    )

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source1.id}
    )

    payload = {
        "metadata": json.dumps(
            {
                "page_parameter": {"id": 2},
            }
        )
    }

    # The given dispatch query context is wrong
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SERVICE_IMPROPERLY_CONFIGURED"
    assert response.json()["detail"] == "No table selected"

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source2.id}
    )

    # The given dispatch query context is wrong
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SERVICE_IMPROPERLY_CONFIGURED"
    assert response.json()["detail"] == "No integration selected"

    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source3.id}
    )
    payload = {
        "metadata": json.dumps(
            {
                "page_parameter": {"id": "test"},
            }
        )
    }
    # The given dispatch query context is wrong
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT"
    assert (
        response.json()["detail"] == 'Value error for "row_id": '
        "The value must be an integer or convertible to an integer."
    )


@pytest.mark.django_db
def test_dispatch_data_sources(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["2Cv", "Green"],
            ["Tesla", "Dark"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="2",
    )
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="3",
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="4",
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="bad",
    )
    data_source4 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user, integration=integration, view=view, table=table, row_id="4"
    )

    url = reverse("api:builder:data_source:dispatch-all", kwargs={"page_id": page.id})

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            fields[1].name: "Orange",
            fields[0].name: "Audi",
            "id": rows[1].id,
            "order": AnyStr(),
        },
        str(data_source1.id): {
            fields[1].name: "Green",
            fields[0].name: "2Cv",
            "id": rows[2].id,
            "order": AnyStr(),
        },
        str(data_source2.id): {
            fields[1].name: "Dark",
            fields[0].name: "Tesla",
            "id": rows[3].id,
            "order": AnyStr(),
        },
        str(data_source3.id): {
            "_error": "ERROR_SERVICE_IMPROPERLY_CONFIGURED",
            "detail": 'Error in formula for "row_id": Invalid syntax at '
            "line 1, col 3: mismatched input 'the end of the formula' expecting '('",
        },
    }


@pytest.mark.django_db
def test_dispatch_data_sources_with_formula_using_datasource_calling_an_other(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["42"],
            [f"{rows[1].id}"],
            ["44"],
            ["45"],
        ],
    )
    view2 = data_fixture.create_grid_view(user, table=table2)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view2,
        table=table2,
        row_id=f"'{rows2[1].id}'",
        name="Id source",
    )

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id=f"get('data_source.{data_source2.id}.{fields2[0].db_column}')",
        name="Item",
    )

    url = reverse("api:builder:data_source:dispatch-all", kwargs={"page_id": page.id})
    payload = {
        "metadata": json.dumps(
            {
                "data_source": {},
                "page_parameter": {},
            }
        )
    }
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.json() == {
        str(data_source2.id): {
            "id": 2,
            "order": "2.00000000000000000000",
            fields2[0].name: "2",
        },
        str(data_source.id): {
            "id": 2,
            "order": "2.00000000000000000000",
            fields[0].name: "Audi",
            fields[1].name: "Orange",
        },
    }


@pytest.mark.django_db
def test_dispatch_data_sources_with_formula_using_datasource_calling_a_shared_data_source(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["42"],
            [f"{rows[1].id}"],
            ["44"],
            ["45"],
        ],
    )
    view2 = data_fixture.create_grid_view(user, table=table2)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    shared_page = builder.shared_page
    page = data_fixture.create_builder_page(user=user, builder=builder)

    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=shared_page,
        integration=integration,
        view=view2,
        table=table2,
        row_id=f"'{rows2[1].id}'",
        name="Id source",
    )

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id=f"get('data_source.{data_source2.id}.{fields2[0].db_column}')",
        name="Item",
    )

    url = reverse("api:builder:data_source:dispatch-all", kwargs={"page_id": page.id})
    payload = {
        "metadata": json.dumps(
            {
                "data_source": {},
                "page_parameter": {},
            }
        )
    }
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.json() == {
        str(data_source.id): {
            "id": rows[1].id,
            "order": "2.00000000000000000000",
            fields[0].name: "Audi",
            fields[1].name: "Orange",
        },
    }


@pytest.mark.django_db
def test_dispatch_only_shared_data_sources(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    shared_page = builder.shared_page
    page = data_fixture.create_builder_page(user=user, builder=builder)

    shared_data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=shared_page,
        integration=integration,
        view=view,
        table=table,
        row_id=f"'{rows[1].id}'",
        name="Item",
    )

    url = reverse("api:builder:data_source:dispatch-all", kwargs={"page_id": page.id})
    payload = {
        "metadata": json.dumps(
            {
                "page_parameter": {},
            }
        )
    }
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.json() == {}

    url = reverse(
        "api:builder:data_source:dispatch-all", kwargs={"page_id": shared_page.id}
    )

    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.json() == {
        str(shared_data_source.id): {
            "id": rows[1].id,
            "order": "2.00000000000000000000",
            fields[0].name: "Audi",
            fields[1].name: "Orange",
        },
    }


@pytest.mark.django_db
def test_get_record_names(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )

    # There must exist one database with a primary column for the record name
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    model = table.get_model(attribute_names=True)
    rows = {
        str(model.objects.create(name="BMW").id): "BMW",
        str(model.objects.create(name="Audi").id): "Audi",
        str(model.objects.create(name="2Cv").id): "2Cv",
        str(model.objects.create(name="Tesla").id): "Tesla",
    }

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        table=table,
        integration=integration,
    )

    view_name = "api:builder:data_source:record-names"
    base_url = reverse(view_name, kwargs={"data_source_id": data_source.id})

    # If no `row_ids` query param is passed then it should return an empty result
    url = f"{base_url}?record_ids="
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert response.json() == {}

    # If the row ids are present, then it should return a mapping with the record names
    url = f"{base_url}?record_ids={','.join(rows.keys())}"
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert response.json() == rows

    # If `row_ids` are invalid, then it should raise an error
    url = f"{base_url}?record_ids=INVALID_1,INVALID_2"
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["record_ids"] == ["The provided record ids are not valid."]

    # If the data source is not a list data source, it should raise an error
    non_list_data_source = (
        data_fixture.create_builder_local_baserow_get_row_data_source(
            user=user,
            table=table,
            integration=integration,
        )
    )
    base_url = reverse(view_name, kwargs={"data_source_id": non_list_data_source.id})
    url = f"{base_url}?record_ids={','.join(rows.keys())}"
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SERVICE_IMPROPERLY_CONFIGURED"
    assert (
        response.json()["detail"] == "This data source does not provide a list service"
    )


@pytest.mark.django_db
def test_dispatch_data_sources_list_rows_with_elements(
    api_client, data_fixture, data_source_fixture
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of List Rows.

    The API response should only contain field data when the field is
    referenced in an element via a formula.
    """

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_fixture["user"],
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
    )

    field = data_source_fixture["fields"][0]
    field_id = field.id

    # Create an element that uses a formula referencing the data source
    data_fixture.create_builder_table_element(
        page=data_source_fixture["page"],
        data_source=data_source,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {"value": f"get('current_record.field_{field_id}')"},
            },
        ],
    )

    data_source_fixture["page"].builder.workspace = None
    data_source_fixture["page"].builder.save()
    data_fixture.create_builder_custom_domain(
        published_to=data_source_fixture["page"].builder
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": data_source_fixture["page"].id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_source_fixture['user_source_user_token']}",
    )

    expected_results = []
    rows = data_source_fixture["rows"]
    for row in rows:
        expected_results.append(
            {
                # Although this Data Source has 2 Fields/Columns, only one is
                # returned since only one field_id is used by the Table.
                field.name: getattr(row, f"field_{field_id}"),
                "id": row.id,
            }
        )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            "has_next_page": False,
            "results": expected_results,
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    # table_row_id is 1-indexed to reflect the row ID in formulas
    # db_row_id is 0-indexed to reflect the row ID in the database
    "table_row_id,db_row_id,",
    [
        (1, 0),
        (2, 1),
        (3, 2),
    ],
)
def test_dispatch_data_sources_get_row_with_elements(
    api_client, data_fixture, data_source_fixture, table_row_id, db_row_id
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of Get Row.

    The API response should only contain field data when the field is
    referenced in an element via a formula.
    """

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_fixture["user"],
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
        row_id=table_row_id,
    )

    field = data_source_fixture["fields"][0]
    field_id = field.id

    # Create an element that uses a formula referencing the data source
    data_fixture.create_builder_table_element(
        page=data_source_fixture["page"],
        data_source=data_source,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {
                    "value": f"get('data_source.{data_source.id}.field_{field_id}')"
                },
            },
        ],
    )

    data_source_fixture["page"].builder.workspace = None
    data_source_fixture["page"].builder.save()
    data_fixture.create_builder_custom_domain(
        published_to=data_source_fixture["page"].builder
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": data_source_fixture["page"].id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_source_fixture['user_source_user_token']}",
    )

    rows = data_source_fixture["rows"]
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            field.name: getattr(rows[db_row_id], f"field_{field_id}"),
            "id": rows[db_row_id].id,
        }
    }


@pytest.mark.django_db
def test_dispatch_data_sources_get_and_list_rows_with_elements(
    api_client,
    data_fixture,
    data_source_fixture,
):
    """
    Test the DispatchDataSourcesView endpoint when using a mix of Data Source
    types, i.e. Get Row and List Rows.

    The API response should only contain field data when the field is
    referenced in an element via a formula.
    """

    user = data_source_fixture["user"]
    table_1, fields_1, rows_1 = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
        ],
        rows=[
            ["Palak Paneer", "Paneer Pakora"],
        ],
    )
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_fixture["user"],
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=table_1,
        row_id=1,
    )

    table_2, fields_2, rows_2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Fruits", "text"),
        ],
        rows=[
            ["Kiwi", "Cherry"],
        ],
    )
    data_source_2 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=table_2,
    )

    # Create an element that uses a concatenation of two "get" formulas; one
    # using the Get Row and the other using List Row data sources.
    formula = (
        f"concat(get('current_record.field_{fields_1[0].id}'),"
        f"get('data_source.{data_source_1.id}.field_{fields_1[0].id}'))"
    )
    data_fixture.create_builder_table_element(
        page=data_source_fixture["page"],
        data_source=data_source_1,
        fields=[
            {
                "name": "My Dishes",
                "type": "text",
                "config": {"value": formula},
            },
        ],
    )

    # Create another table, this time using the List Row data source
    data_fixture.create_builder_table_element(
        page=data_source_fixture["page"],
        data_source=data_source_2,
        fields=[
            {
                "name": "My Fruits",
                "type": "text",
                "config": {"value": f"get('current_record.field_{fields_2[0].id}')"},
            },
        ],
    )

    data_source_fixture["page"].builder.workspace = None
    data_source_fixture["page"].builder.save()
    data_fixture.create_builder_custom_domain(
        published_to=data_source_fixture["page"].builder
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": data_source_fixture["page"].id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_source_fixture['user_source_user_token']}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source_1.id): {
            fields_1[0].name: getattr(rows_1[0], f"field_{fields_1[0].id}"),
            "id": rows_1[0].id,
        },
        # Although this Data Source has 2 Fields/Columns, only one is returned
        # since only one field_id is used by the Table.
        str(data_source_2.id): {
            "has_next_page": False,
            "results": [
                {
                    fields_2[0].name: getattr(rows_2[0], f"field_{fields_2[0].id}"),
                    "id": rows_2[0].id,
                },
            ],
        },
    }


@pytest.mark.django_db
@patch(
    "baserow.contrib.builder.api.data_sources.views.DataSourceService.dispatch_data_source"
)
@patch("baserow.contrib.builder.api.data_sources.views.BuilderDispatchContext")
@patch(
    "baserow.contrib.builder.api.data_sources.views.DataSourceHandler.get_data_source"
)
def test_dispatch_data_source_view(
    mock_get_data_source,
    mock_builder_dispatch_context,
    mock_dispatch_data_source,
    api_client,
):
    """
    Test the DispatchDataSourceView endpoint.

    Ensure that the field_names are not computed, because we don't want to
    filter any fields in the Editor.
    """

    mock_data_source = MagicMock()
    mock_get_data_source.return_value = mock_data_source

    mock_dispatch_context = MagicMock()
    mock_builder_dispatch_context.return_value = mock_dispatch_context

    mock_response = {}
    mock_dispatch_data_source.return_value = mock_response

    mock_data_source_id = 100
    url = reverse(
        "api:builder:data_source:dispatch",
        kwargs={"data_source_id": mock_data_source_id},
    )
    response = api_client.post(url)

    assert response.status_code == 200
    assert response.json() == mock_response
    mock_get_data_source.assert_called_once_with(str(mock_data_source_id))
    mock_builder_dispatch_context.assert_called_once_with(
        ANY,
        mock_data_source.page,
        only_expose_public_allowed_properties=False,
    )
    mock_dispatch_data_source.assert_called_once_with(
        ANY, mock_data_source, mock_dispatch_context
    )


@pytest.mark.django_db
def test_private_dispatch_data_source_view_returns_all_fields(api_client, data_fixture):
    """
    Test the DispatchDataSourceView endpoint.

    This integration test ensures that all field_names are returned in the
    private view, even if it isn't used by a visible element. This is because
    the editor needs access to all fields.
    """

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Spiciness", "number"),
        ],
        rows=[
            ["Paneer Tikka", 5],
            ["Gobi Manchurian", 8],
        ],
    )
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )
    # Create a heading element that only uses the first field
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.*.field_{fields[0].id}')",
    )

    url = reverse(
        "api:builder:data_source:dispatch",
        kwargs={"data_source_id": data_source.id},
    )
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == 200
    assert response.json() == {
        "has_next_page": False,
        "results": [
            {
                fields[0].name: "Paneer Tikka",
                # Although only field_1 is explicitly used by an element in this
                # page, field_2 is still returned because the Editor page needs
                # access to all data source fields.
                fields[1].name: 5,
                "id": AnyInt(),
                "order": AnyStr(),
            },
            {
                fields[0].name: "Gobi Manchurian",
                fields[1].name: 8,
                "id": AnyInt(),
                "order": AnyStr(),
            },
        ],
    }


@pytest.mark.django_db
@patch(
    "baserow.contrib.builder.api.data_sources.views.DataSourceService.dispatch_page_data_sources"
)
@patch("baserow.contrib.builder.api.data_sources.views.BuilderDispatchContext")
@patch("baserow.contrib.builder.api.data_sources.views.PageHandler.get_page")
def test_dispatch_data_sources_view(
    mock_get_page,
    mock_builder_dispatch_context,
    mock_dispatch_page_data_sources,
    api_client,
):
    """
    Test the DispatchDataSourcesView
    endpoint.mock_builder_dispatch_context.assert_called_once_with

    Ensure that the field_names are not computed, because we don't want to
    filter any fields in the Editor.
    """

    mock_page = MagicMock()
    mock_get_page.return_value = mock_page

    mock_dispatch_context = MagicMock()
    mock_builder_dispatch_context.return_value = mock_dispatch_context

    mock_service_contents = {"101": "mock_content"}
    mock_dispatch_page_data_sources.return_value = mock_service_contents

    mock_page_id = 100
    url = reverse(
        "api:builder:data_source:dispatch-all", kwargs={"page_id": mock_page_id}
    )
    response = api_client.post(url)

    assert response.status_code == 200
    assert response.json() == mock_service_contents
    mock_get_page.assert_called_once_with(str(mock_page_id))
    mock_builder_dispatch_context.assert_called_once_with(
        ANY, mock_page, only_expose_public_allowed_properties=False
    )
    mock_dispatch_page_data_sources.assert_called_once_with(
        ANY, mock_page, mock_dispatch_context
    )
