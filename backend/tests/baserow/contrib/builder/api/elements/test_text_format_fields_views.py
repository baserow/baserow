"""
Tests for the Plain/Markdown `*_format` settings of the form element labels and
of the choice element option names.
"""

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

# (element type, format field)
ELEMENT_FORMAT_FIELDS = [
    ("input_text", "label_format"),
    ("choice", "label_format"),
    ("choice", "option_format"),
    ("checkbox", "label_format"),
    ("rating_input", "label_format"),
    ("datetime_picker", "label_format"),
    ("record_selector", "label_format"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("element_type,field_name", ELEMENT_FORMAT_FIELDS)
def test_create_element_with_markdown_format(
    api_client, data_fixture, element_type, field_name
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": element_type, field_name: "markdown"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()[field_name] == "markdown"


@pytest.mark.django_db
@pytest.mark.parametrize("element_type,field_name", ELEMENT_FORMAT_FIELDS)
def test_element_format_defaults_to_plain(
    api_client, data_fixture, element_type, field_name
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": element_type},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()[field_name] == "plain"


@pytest.mark.django_db
@pytest.mark.parametrize("element_type,field_name", ELEMENT_FORMAT_FIELDS)
def test_cant_create_element_with_invalid_format(
    api_client, data_fixture, element_type, field_name
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": element_type, field_name: "html"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"][field_name][0]["code"] == "invalid_choice"


@pytest.mark.django_db
@pytest.mark.parametrize("element_type,field_name", ELEMENT_FORMAT_FIELDS)
def test_update_element_format(api_client, data_fixture, element_type, field_name):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": element_type},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    element_id = response.json()["id"]

    url = reverse("api:builder:element:item", kwargs={"element_id": element_id})
    response = api_client.patch(
        url,
        {field_name: "markdown"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()[field_name] == "markdown"

    response = api_client.patch(
        url,
        {field_name: "html"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"][field_name][0]["code"] == "invalid_choice"
