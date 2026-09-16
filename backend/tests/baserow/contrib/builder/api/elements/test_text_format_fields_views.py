"""
Tests for the Plain/Markdown format of the form element labels, which are
`FormattedFormulaField`s and carry it on their formula object, and of the
choice element option names, which are plain strings and have their own
`option_format` setting.
"""

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

# (element type, formula that can be rendered as Markdown)
ELEMENT_MARKDOWN_FORMULAS = [
    ("input_text", "label"),
    ("choice", "label"),
    ("checkbox", "label"),
    ("rating_input", "label"),
    ("datetime_picker", "label"),
    ("record_selector", "label"),
]


def create_element(api_client, token, page, **values):
    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    return api_client.post(
        url, values, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )


def update_element(api_client, token, element_id, **values):
    url = reverse("api:builder:element:item", kwargs={"element_id": element_id})
    return api_client.patch(
        url, values, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("element_type,field_name", ELEMENT_MARKDOWN_FORMULAS)
def test_create_element_with_markdown_formula(
    api_client, data_fixture, element_type, field_name
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    response = create_element(
        api_client,
        token,
        page,
        type=element_type,
        **{field_name: {"formula": "'**bold**'", "format": "markdown"}},
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()[field_name] == {
        "formula": "'**bold**'",
        "mode": "simple",
        "version": "0.1",
        "format": "markdown",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("element_type,field_name", ELEMENT_MARKDOWN_FORMULAS)
def test_element_formula_format_defaults_to_plain(
    api_client, data_fixture, element_type, field_name
):
    """
    The formula of a formatted surface always returns its format: plain when it
    was omitted, or when the element was created without the formula at all.
    """

    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    response = create_element(api_client, token, page, type=element_type)
    assert response.status_code == HTTP_200_OK
    assert response.json()[field_name]["format"] == "plain"

    response = create_element(
        api_client,
        token,
        page,
        type=element_type,
        **{field_name: {"formula": "'x'"}},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()[field_name] == {
        "formula": "'x'",
        "mode": "simple",
        "version": "0.1",
        "format": "plain",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("element_type,field_name", ELEMENT_MARKDOWN_FORMULAS)
def test_cant_create_element_with_invalid_formula_format(
    api_client, data_fixture, element_type, field_name
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    response = create_element(
        api_client,
        token,
        page,
        type=element_type,
        **{field_name: {"formula": "'x'", "format": "html"}},
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"][field_name]["format"][0]["code"] == (
        "invalid_choice"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("element_type,field_name", ELEMENT_MARKDOWN_FORMULAS)
def test_update_element_formula_format(
    api_client, data_fixture, element_type, field_name
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element_id = create_element(api_client, token, page, type=element_type).json()["id"]

    response = update_element(
        api_client,
        token,
        element_id,
        **{field_name: {"formula": "'**bold**'", "format": "markdown"}},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()[field_name]["format"] == "markdown"

    response = update_element(
        api_client,
        token,
        element_id,
        **{field_name: {"formula": "'**bold**'", "format": "plain"}},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()[field_name]["format"] == "plain"

    response = update_element(
        api_client,
        token,
        element_id,
        **{field_name: {"formula": "'**bold**'", "format": "html"}},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"][field_name]["format"][0]["code"] == (
        "invalid_choice"
    )


@pytest.mark.django_db
def test_formulas_without_the_toggle_ignore_the_format(api_client, data_fixture):
    """
    The placeholder is an HTML attribute and can't render Markdown, so the UI
    doesn't offer the toggle for it and its formula is a plain `FormulaField`.
    That field doesn't know the key, so it drops it like any other undeclared
    key and never returns one: the API and the UI agree on which surfaces can
    be Markdown, and the type is what they agree on.
    """

    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    response = create_element(
        api_client,
        token,
        page,
        type="input_text",
        label={"formula": "'x'", "format": "markdown"},
        placeholder={"formula": "'x'", "format": "markdown"},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["label"]["format"] == "markdown"
    assert response.json()["placeholder"] == {
        "formula": "'x'",
        "mode": "simple",
        "version": "0.1",
    }


@pytest.mark.django_db
def test_choice_element_option_format(api_client, data_fixture):
    """
    The option names are plain strings, their format is a setting of the
    element.
    """

    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    response = create_element(api_client, token, page, type="choice")
    assert response.status_code == HTTP_200_OK
    assert response.json()["option_format"] == "plain"
    element_id = response.json()["id"]

    response = create_element(
        api_client, token, page, type="choice", option_format="markdown"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["option_format"] == "markdown"

    response = create_element(
        api_client, token, page, type="choice", option_format="html"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["option_format"][0]["code"] == "invalid_choice"

    response = update_element(api_client, token, element_id, option_format="markdown")
    assert response.status_code == HTTP_200_OK
    assert response.json()["option_format"] == "markdown"

    response = update_element(api_client, token, element_id, option_format="html")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"]["option_format"][0]["code"] == "invalid_choice"
