import uuid

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.builder.elements.models import LinkElement, NavigationElementMixin
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE


@pytest.mark.django_db
def test_can_get_a_table_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": table_element.page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    [column_element_returned] = response.json()
    assert response.status_code == HTTP_200_OK
    assert column_element_returned["id"] == table_element.id
    assert column_element_returned["type"] == "table"


@pytest.mark.django_db
def test_can_create_a_table_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})

    response = api_client.post(
        url,
        {
            "type": "table",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["type"] == "table"


@pytest.mark.django_db
def test_can_update_a_table_element_fields(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:item", kwargs={"element_id": table_element.id})
    uuids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]

    response = api_client.patch(
        url,
        {
            "fields": [
                {
                    "name": "Name",
                    "type": "text",
                    "value": "get('test1')",
                    "uid": uuids[0],
                },
                {
                    "name": "Color",
                    "type": "link",
                    "navigate_to_url": "get('test2')",
                    "link_name": "get('test3')",
                    "target": "self",
                    "variant": LinkElement.VARIANTS.BUTTON,
                    "uid": uuids[1],
                },
                {
                    "name": "Question",
                    "type": "text",
                    "value": "get('test3')",
                    "uid": uuids[2],
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert [
        {key: value for key, value in f.items() if key not in ["id"]}
        for f in response.json()["fields"]
    ] == [
        {
            "name": "Name",
            "type": "text",
            "value": BaserowFormulaObject(
                formula="get('test1')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "uid": uuids[0],
            "styles": {},
        },
        {
            "name": "Color",
            "type": "link",
            "navigate_to_page_id": None,
            "navigation_type": NavigationElementMixin.NAVIGATION_TYPES.PAGE,
            "navigate_to_url": BaserowFormulaObject(
                formula="get('test2')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "link_name": BaserowFormulaObject(
                formula="get('test3')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "target": "self",
            "page_parameters": [],
            "query_parameters": [],
            "variant": LinkElement.VARIANTS.BUTTON,
            "styles": {},
            "uid": uuids[1],
        },
        {
            "name": "Question",
            "type": "text",
            "value": BaserowFormulaObject(
                formula="get('test3')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "uid": uuids[2],
            "styles": {},
        },
    ]


@pytest.mark.django_db
def test_cant_update_a_table_element_fields_with_wrong_field_type(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:item", kwargs={"element_id": table_element.id})

    response = api_client.patch(
        url,
        {
            "fields": [
                {"name": "Name", "type": "missing", "value": "get('test1')"},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"]["fields"][0][0]["code"] == "INVALID_FIELD_TYPE"


@pytest.mark.django_db
def test_cant_update_a_table_element_fields_with_wrong_field_property(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:item", kwargs={"element_id": table_element.id})

    response = api_client.patch(
        url,
        {
            "fields": [
                {"name": "Name", "type": "text", "missing": "get('test1')"},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"]["fields"][0][0]["code"] == "INVALID_FIELD_PROPERTY"
