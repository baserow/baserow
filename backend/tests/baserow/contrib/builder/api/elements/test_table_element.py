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
                    "value": "get('data_source.123')",
                    "format": "markdown",
                    "uid": uuids[0],
                },
                {
                    "name": "Color",
                    "type": "link",
                    "navigate_to_url": "get('data_source.124')",
                    "link_name": "get('data_source.125')",
                    "target": "self",
                    "variant": LinkElement.VARIANTS.BUTTON,
                    "uid": uuids[1],
                },
                {
                    "name": "Question",
                    "type": "text",
                    "value": "get('data_source.126')",
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
                formula="get('data_source.123')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "format": "markdown",
            "uid": uuids[0],
            "styles": {},
        },
        {
            "name": "Color",
            "type": "link",
            "navigate_to_page_id": None,
            "navigation_type": NavigationElementMixin.NAVIGATION_TYPES.PAGE,
            "navigate_to_url": BaserowFormulaObject(
                formula="get('data_source.124')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "link_name": BaserowFormulaObject(
                formula="get('data_source.125')",
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
                formula="get('data_source.126')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "format": "plain",
            "uid": uuids[2],
            "styles": {},
        },
    ]

    text_fields = [f for f in table_element.fields.all() if f.type == "text"]
    assert text_fields[0].config["format"] == "markdown"
    # The `plain` default is stored when `format` is omitted from the payload.
    assert text_fields[1].config["format"] == "plain"


@pytest.mark.django_db
def test_text_field_format_defaults_to_plain(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:item", kwargs={"element_id": table_element.id})

    response = api_client.patch(
        url,
        {
            "fields": [
                {
                    "name": "Name",
                    "type": "text",
                    "value": "get('data_source.123')",
                    "uid": str(uuid.uuid4()),
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    [field] = response.json()["fields"]
    assert field["format"] == "plain"


@pytest.mark.django_db
def test_cant_update_text_field_with_invalid_format(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:item", kwargs={"element_id": table_element.id})

    response = api_client.patch(
        url,
        {
            "fields": [
                {
                    "name": "Name",
                    "type": "text",
                    "value": "get('data_source.123')",
                    "format": "html",
                    "uid": str(uuid.uuid4()),
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["fields"][0]["format"][0]["code"] == (
        "invalid_choice"
    )


@pytest.mark.django_db
def test_get_text_field_without_stored_format_returns_plain(api_client, data_fixture):
    """
    Text collection fields created before the `format` option existed have no
    `format` key in their stored config. They must be returned as `plain`
    without any migration.
    """

    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(
        user=user,
        fields=[{"name": "Name", "type": "text", "config": {"value": "'x'"}}],
    )
    assert "format" not in table_element.fields.get().config

    url = reverse("api:builder:element:list", kwargs={"page_id": table_element.page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    [table_element_returned] = response.json()
    [field] = table_element_returned["fields"]
    assert field["format"] == "plain"


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


@pytest.mark.django_db
def test_can_update_a_table_element_field_name_format(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:item", kwargs={"element_id": table_element.id})

    response = api_client.patch(
        url,
        {
            "fields": [
                {
                    "name": "**Bold**",
                    "name_format": "markdown",
                    "type": "text",
                    "value": "get('data_source.123')",
                    "uid": str(uuid.uuid4()),
                },
                {
                    "name": "Plain",
                    "type": "text",
                    "value": "get('data_source.123')",
                    "uid": str(uuid.uuid4()),
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    markdown_field, plain_field = response.json()["fields"]
    assert markdown_field["name_format"] == "markdown"
    # The `plain` default applies when `name_format` is omitted from the payload.
    assert plain_field["name_format"] == "plain"

    markdown_field, plain_field = table_element.fields.all()
    assert markdown_field.name_format == "markdown"
    assert plain_field.name_format == "plain"


@pytest.mark.django_db
def test_cant_update_a_table_element_field_with_invalid_name_format(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:item", kwargs={"element_id": table_element.id})

    response = api_client.patch(
        url,
        {
            "fields": [
                {
                    "name": "Name",
                    "name_format": "html",
                    "type": "text",
                    "value": "get('data_source.123')",
                    "uid": str(uuid.uuid4()),
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["fields"][0]["name_format"][0]["code"] == (
        "invalid_choice"
    )


@pytest.mark.django_db
def test_tags_field_format(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_element = data_fixture.create_builder_table_element(user=user)

    url = reverse("api:builder:element:item", kwargs={"element_id": table_element.id})

    response = api_client.patch(
        url,
        {
            "fields": [
                {
                    "name": "Markdown tags",
                    "type": "tags",
                    "values": "get('data_source.123')",
                    "format": "markdown",
                    "uid": str(uuid.uuid4()),
                },
                {
                    "name": "Plain tags",
                    "type": "tags",
                    "values": "get('data_source.123')",
                    "uid": str(uuid.uuid4()),
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    markdown_field, plain_field = response.json()["fields"]
    assert markdown_field["format"] == "markdown"
    assert plain_field["format"] == "plain"

    markdown_field, plain_field = table_element.fields.all()
    assert markdown_field.config["format"] == "markdown"
    assert plain_field.config["format"] == "plain"

    response = api_client.patch(
        url,
        {
            "fields": [
                {
                    "name": "Invalid tags",
                    "type": "tags",
                    "values": "get('data_source.123')",
                    "format": "html",
                    "uid": str(uuid.uuid4()),
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"]["fields"][0]["format"][0]["code"] == (
        "invalid_choice"
    )
