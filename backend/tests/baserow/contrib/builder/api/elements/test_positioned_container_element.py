from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.constants import PageAlignments, PageBehaviours


@pytest.fixture
def positioned_container_fixture(data_fixture):
    """Fixture to help test the Menu element."""

    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, path="/page/")

    element = data_fixture.create_builder_positioned_container_element(
        user=user, page=page
    )

    return {
        "token": token,
        "page": page,
        "element": element,
    }


@pytest.mark.django_db
def test_get_positioned_container_element(api_client, positioned_container_fixture):
    positioned_container_element = positioned_container_fixture["element"]

    page = positioned_container_fixture["page"]
    token = positioned_container_fixture["token"]

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    [element] = response.json()

    assert element["id"] == positioned_container_element.id
    assert element["type"] == "positioned_container"
    assert element["alignment"] == PageAlignments.TOP
    assert element["behaviour"] == PageBehaviours.FIXED


@pytest.mark.django_db
def test_create_positioned_container_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})

    response = api_client.post(
        url,
        {
            "type": "positioned_container",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["type"] == "positioned_container"


@pytest.mark.django_db
def test_can_update_positioned_container_element(
    api_client, positioned_container_fixture
):
    element = positioned_container_fixture["element"]
    token = positioned_container_fixture["token"]

    assert element.alignment == PageAlignments.TOP
    assert element.behaviour == PageBehaviours.FIXED

    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {
            "alignment": PageAlignments.BOTTOM,
            "behaviour": PageBehaviours.STICKY,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    data = response.json()

    assert data["id"] == element.id
    assert data["alignment"] == PageAlignments.BOTTOM
    assert data["behaviour"] == PageBehaviours.STICKY
