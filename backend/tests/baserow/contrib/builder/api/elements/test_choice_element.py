from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.builder.elements.models import ChoiceElement


@pytest.mark.django_db
@pytest.mark.parametrize(
    "search_values,expected_search",
    [({}, False), ({"show_search": False}, False), ({"show_search": True}, True)],
)
@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize("option_type", ChoiceElement.OPTION_TYPE.values)
def test_choice_search_create_and_read(
    api_client, data_fixture, search_values, expected_search, multiple, option_type
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})

    response = api_client.post(
        url,
        {
            "type": "choice",
            "multiple": multiple,
            "option_type": option_type,
            **search_values,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["show_search"] is expected_search
    element = ChoiceElement.objects.get(id=response.json()["id"])
    assert element.show_search is expected_search

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert response.json()[0]["show_search"] is expected_search


@pytest.mark.django_db
@pytest.mark.parametrize("multiple", [False, True])
def test_choice_search_update_and_preserve_when_switching_display(
    api_client, data_fixture, multiple
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_choice_element(page=page, multiple=multiple)
    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})

    for values, expected_search in [
        ({"show_search": True}, True),
        ({"show_as_dropdown": False}, True),
        ({"show_as_dropdown": True}, True),
        ({"show_search": False}, False),
    ]:
        response = api_client.patch(
            url,
            values,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["show_search"] is expected_search
        element.refresh_from_db()
        assert element.show_search is expected_search
        assert element.multiple is multiple
        if "show_as_dropdown" in values:
            assert element.show_as_dropdown is values["show_as_dropdown"]


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_search", [None, "invalid"])
def test_choice_search_rejects_invalid_values(api_client, data_fixture, invalid_search):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    response = api_client.post(
        reverse("api:builder:element:list", kwargs={"page_id": page.id}),
        {"type": "choice", "show_search": invalid_search},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "show_search" in response.json()["detail"]
    assert not ChoiceElement.objects.filter(page=page).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("show_search", [False, True])
def test_choice_search_duplicate(api_client, data_fixture, show_search):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_choice_element(
        page=page, show_search=show_search
    )

    response = api_client.post(
        reverse("api:builder:element:duplicate", kwargs={"element_id": element.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    duplicated = response.json()["elements"][0]
    assert duplicated["id"] != element.id
    assert duplicated["show_search"] is show_search
    assert ChoiceElement.objects.get(id=duplicated["id"]).show_search is show_search


@pytest.mark.django_db
@pytest.mark.parametrize("show_search", [False, True])
def test_choice_search_public_serialization(api_client, data_fixture, show_search):
    published_builder = data_fixture.create_builder_application(workspace=None)
    page = data_fixture.create_builder_page(builder=published_builder)
    element = data_fixture.create_builder_choice_element(
        page=page, show_search=show_search
    )
    data_fixture.create_builder_custom_domain(published_to=published_builder)

    response = api_client.get(
        reverse("api:builder:domains:list_elements", kwargs={"page_id": page.id})
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()[0]["id"] == element.id
    assert response.json()[0]["show_search"] is show_search
