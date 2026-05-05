from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.core.graph.types import GraphPointPosition


@pytest.mark.django_db
def test_can_get_a_column_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    column_element = data_fixture.create_builder_column_element(user=user)

    url = reverse(
        "api:builder:element:list", kwargs={"page_id": column_element.page.id}
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    [column_element_returned] = response.json()
    assert response.status_code == HTTP_200_OK
    assert column_element_returned["id"] == column_element.id
    assert column_element_returned["type"] == "column"


@pytest.mark.django_db
def test_can_create_a_column_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})

    response = api_client.post(
        url,
        {
            "type": "column",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["type"] == "column"


@pytest.mark.django_db
def test_column_element_column_amount_errors(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})

    response = api_client.post(
        url,
        {
            "type": "column",
            "column_amount": 0,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        url,
        {
            "type": "column",
            "column_amount": 7,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_column_element_column_gap_errors(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})

    response = api_client.post(
        url,
        {
            "type": "column",
            "column_gap": -1,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        url,
        {
            "type": "column",
            "column_gap": 2001,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_elements_moved_when_column_is_removed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    column = data_fixture.create_builder_column_element(
        user=user, page=page, column_amount=3
    )
    column_element_column_0 = data_fixture.create_builder_text_element(
        user=user,
        page=page,
        place_in_container="0",
        reference_element=column,
        position=GraphPointPosition.CHILD,
    )
    column_element_column_1 = data_fixture.create_builder_text_element(
        user=user,
        page=page,
        place_in_container="1",
        reference_element=column,
        position=GraphPointPosition.CHILD,
    )
    column_element_column_1_1 = data_fixture.create_builder_text_element(
        user=user,
        page=page,
        place_in_container="1",
        reference_element=column,
        position=GraphPointPosition.CHILD,
    )
    column_element_column_2 = data_fixture.create_builder_text_element(
        user=user,
        page=page,
        place_in_container="2",
        reference_element=column,
        position=GraphPointPosition.CHILD,
    )

    url = reverse("api:builder:element:item", kwargs={"element_id": column.id})

    response = api_client.patch(
        url,
        {
            "column_amount": 1,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    column_element_column_0.refresh_from_db()
    column_element_column_1.refresh_from_db()
    column_element_column_1_1.refresh_from_db()
    column_element_column_2.refresh_from_db()

    assert column_element_column_0.place_in_container == "0"
    assert column_element_column_1.place_in_container == "0"
    assert column_element_column_1_1.place_in_container == "0"
    assert column_element_column_2.place_in_container == "0"

    assert column_element_column_0.order < column_element_column_1.order
    assert column_element_column_1.order < column_element_column_1_1.order
    assert column_element_column_1_1.order < column_element_column_2.order


@pytest.mark.django_db
def test_moving_an_element_to_new_column_appends_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    column_element = data_fixture.create_builder_column_element(
        user=user, page=page, column_amount=2
    )

    element_in_column_0 = data_fixture.create_builder_text_element(
        user=user,
        page=page,
        reference_element=column_element,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
        order=1,
    )

    element_in_column_1 = data_fixture.create_builder_text_element(
        user=user,
        page=page,
        reference_element=column_element,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
        order=4,
    )

    url = reverse(
        "api:builder:element:move", kwargs={"element_id": element_in_column_0.id}
    )

    response = api_client.patch(
        url,
        {
            "reference_element_id": column_element.id,
            "position": GraphPointPosition.CHILD,
            "place_in_container": "1",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    element_in_column_0.refresh_from_db()
    element_in_column_1.refresh_from_db()

    assert element_in_column_0.place_in_container == "1"
    assert element_in_column_1.place_in_container == "1"


@pytest.mark.django_db
def test_column_element_invalid_child_in_container_on_move(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    column_element = data_fixture.create_builder_column_element(
        user=user, column_amount=2
    )
    child = data_fixture.create_builder_text_element(page=column_element.page)

    url = reverse("api:builder:element:move", kwargs={"element_id": child.id})
    response = api_client.patch(
        url,
        {
            "reference_element_id": column_element.id,
            "position": GraphPointPosition.CHILD,
            "place_in_container": "9999",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == ["place_in_container can at most be 1, (9999, was given)"]


@pytest.mark.django_db
def test_column_element_invalid_child_in_container_on_create(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    column_element = data_fixture.create_builder_column_element(
        user=user, column_amount=2
    )

    url = reverse(
        "api:builder:element:list", kwargs={"page_id": column_element.page.id}
    )
    response = api_client.post(
        url,
        {
            "type": "text",
            "reference_element_id": column_element.id,
            "position": GraphPointPosition.CHILD,
            "place_in_container": "9999",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == ["place_in_container can at most be 1, (9999, was given)"]
