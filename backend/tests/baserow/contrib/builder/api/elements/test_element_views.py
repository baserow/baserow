from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.builder.elements.element_types import HeaderElementType
from baserow.contrib.builder.elements.models import (
    ChoiceElementOption,
    Element,
    LinkElement,
)
from baserow.core.graph.types import GraphPointPosition


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles,role_type",
    [
        (
            ["a_role"],
            Element.ROLE_TYPES.ALLOW_ALL,
        ),
        (
            ["a_role", "b_role"],
            Element.ROLE_TYPES.ALLOW_ALL,
        ),
        (
            ["a_role"],
            Element.ROLE_TYPES.ALLOW_ALL_EXCEPT,
        ),
        (
            ["a_role"],
            Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
        ),
    ],
)
def test_elements_list_endpoint_returns_expected_roles(
    api_client,
    data_fixture,
    roles,
    role_type,
):
    """
    Ensure the element:list endpoint returns expected values for the
    roles and role_type fields.
    """

    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    element.roles = roles
    element.role_type = role_type
    element.save()

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    data = response.json()[0]

    assert data["roles"] == roles
    assert data["role_type"] == role_type


@pytest.mark.django_db
def test_get_elements(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    assert response_json[0]["id"] == element1.id
    assert response_json[0]["type"] == "heading"
    assert "level" in response_json[0]
    assert response_json[1]["id"] == element2.id
    assert response_json[1]["type"] == "heading"
    assert response_json[2]["id"] == element3.id
    assert response_json[2]["type"] == "text"
    assert "level" not in response_json[2]


@pytest.mark.django_db
def test_create_element_north_position(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": "heading",
            "position": "north",
            "reference_element_id": page.get_graph().graph["0"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "heading",
            "heading": {"next": {"": ["heading-"]}},
            "heading-": {},
        }
    )


@pytest.mark.django_db
def test_create_element_south_position(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    existing = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": "heading",
            "position": "south",
            "reference_element_id": existing.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "heading",
            "heading": {"next": {"": ["heading-"]}},
            "heading-": {},
        }
    )


@pytest.mark.django_db
def test_create_elements_in_container_slot_ordering(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    column = data_fixture.create_builder_column_element(page=page, column_amount=3)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})

    # Add heading_a as the first child of slot '0'
    resp_a = api_client.post(
        url,
        {
            "type": "heading",
            "position": GraphPointPosition.CHILD,
            "reference_element_id": column.id,
            "place_in_container": "0",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp_a.status_code == HTTP_200_OK
    id_a = resp_a.json()["id"]

    # Insert heading_b before heading_a
    resp_b = api_client.post(
        url,
        {
            "type": "heading",
            "position": GraphPointPosition.NORTH,
            "reference_element_id": id_a,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp_b.status_code == HTTP_200_OK

    # Insert heading_c after heading_a
    resp_c = api_client.post(
        url,
        {
            "type": "heading",
            "position": GraphPointPosition.SOUTH,
            "reference_element_id": id_a,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp_c.status_code == HTTP_200_OK

    # Verify order in slot '0': heading_b → heading_a → heading_c
    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "column",
            "column": {"children": {"": ["heading"]}},
            "heading": {"next": {"": ["heading-"]}},
            "heading-": {"next": {"": ["heading--"]}},
            "heading--": {},
        }
    )


@pytest.mark.django_db
def test_create_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": "heading",
            "place_in_container": "",
            "position": GraphPointPosition.SOUTH,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "heading"
    assert response_json["value"] == {"formula": "", "version": "0.1", "mode": "simple"}

    response = api_client.post(
        url,
        {
            "type": "heading",
            "value": '"test"',
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["value"] == {
        "formula": '"test"',
        "version": "0.1",
        "mode": "simple",
    }


@pytest.mark.django_db
def test_create_element_deactivated_type(
    api_client, data_fixture, mutable_element_type_registry
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    regular_element_type = next(
        filter(
            lambda t: not t.is_multi_page_element,
            mutable_element_type_registry.get_all(),
        )
    )

    prev_is_deactivated = regular_element_type.is_deactivated
    regular_element_type.is_deactivated = lambda x: True

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": regular_element_type.type, "value": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    regular_element_type.is_deactivated = prev_is_deactivated

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ELEMENT_TYPE_DEACTIVATED"


@pytest.mark.django_db
def test_create_element_bad_request_for_formula(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": "heading", "value": "not a formula"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["value"][0]["error"]
        == "The formula is invalid: Invalid syntax at line 1, col 3: missing '(' at ' '"
    )


@pytest.mark.django_db
def test_create_element_bad_request_for_invalid_runtime_formula(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": "heading", "value": "unsupported_function()"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ELEMENT_INVALID_FORMULA"


@pytest.mark.django_db
def test_create_element_permission_denied(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    with stub_check_permissions(raise_permission_denied=True):
        response = api_client.post(
            url,
            {"type": "heading"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_create_element_page_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:element:list", kwargs={"page_id": 0})
    response = api_client.post(
        url,
        {"type": "heading"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_PAGE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_element_reference_node_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": "heading", "reference_element_id": 99999999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ELEMENT_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": element1.id})
    response = api_client.patch(
        url,
        {"value": '"unusual suspect"', "level": 3},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["value"]["formula"] == '"unusual suspect"'
    assert response.json()["level"] == 3


@pytest.mark.django_db
def test_updating_element_with_invalid_formula_arguments_throws_error(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {"value": "get('foobar.123')", "level": 3},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            "value": [
                {
                    "error": "The formula provider 'foobar' used "
                    "in 'foobar.123' does not exist in this module.",
                    "code": "invalid_formula_argument",
                }
            ]
        },
    }


@pytest.mark.django_db
def test_update_element_bad_request_for_invalid_runtime_formula(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {"value": "unsupported_function()"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ELEMENT_INVALID_FORMULA"


@pytest.mark.django_db
def test_update_element_styles(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": element1.id})
    response = api_client.patch(
        url,
        {"styles": {"typography": {"heading_1_text_color": "#CCCCCCCC"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["styles"] == {
        "typography": {"heading_1_text_color": "#CCCCCCCC"}
    }


@pytest.mark.django_db
def test_update_element_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:element:item", kwargs={"element_id": 0})
    response = api_client.patch(
        url,
        {"value": '"test"'},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ELEMENT_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_element_bad_style_property(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": element1.id})

    # Bad root property
    response = api_client.patch(
        url,
        {"styles": {"typpography": {"heading_1_text_color": "#CCCCCCCC"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["styles"] == {}

    # Bad theme property
    response = api_client.patch(
        url,
        {"styles": {"typography": {"heading_25_text_color": "#CCCCCCCC"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["styles"] == {"typography": {}}


@pytest.mark.django_db
def test_move_element_empty_payload(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:move", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            "reference_element_id": [
                {"error": "This field is required.", "code": "required"}
            ]
        },
    }


@pytest.mark.django_db
def test_move_element_north(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:move", kwargs={"element_id": element3.id})
    response = api_client.patch(
        url,
        {"reference_element_id": element2.id, "position": GraphPointPosition.NORTH},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    page.refresh_from_db(fields=["graph"])
    assert page.get_graph().graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element3.id]}},
        str(element3.id): {"next": {"": [element2.id]}},
        str(element2.id): {},
    }


@pytest.mark.django_db
def test_move_element_reference_element_not_in_same_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)
    page2 = data_fixture.create_builder_page(user=user)
    element2 = data_fixture.create_builder_heading_element(page=page2)

    url = reverse("api:builder:element:move", kwargs={"element_id": element2.id})
    response = api_client.patch(
        url,
        {"reference_element_id": element.id, "position": GraphPointPosition.SOUTH},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_NOT_IN_BUILDER"


@pytest.mark.django_db
def test_move_element_bad_reference_element_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:move", kwargs={"element_id": element1.id})
    response = api_client.patch(
        url,
        {"reference_element_id": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": element1.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_element_permission_denied(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": element1.id})

    with stub_check_permissions(raise_permission_denied=True):
        response = api_client.delete(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_delete_element_element_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:element:item", kwargs={"element_id": 0})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ELEMENT_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_link_element_path_parameter_wrong_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    page_with_params = data_fixture.create_builder_page(
        builder=builder,
        path="/test/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )

    link_element = data_fixture.create_builder_link_element(
        page=page,
        navigation_type=LinkElement.NAVIGATION_TYPES.PAGE,
        navigate_to_page=page_with_params,
    )

    url = reverse("api:builder:element:item", kwargs={"element_id": link_element.id})
    response = api_client.patch(
        url,
        {"page_parameters": [{"name": "id", "value": "not a number"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    assert (
        response.json()["detail"]["page_parameters"][0]["value"][0]["error"]
        == "The formula is invalid: Invalid syntax at line 1, col 3: missing '(' at ' '"
    )


@pytest.mark.django_db
def test_can_move_element_outside_container(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    container_element = data_fixture.create_builder_column_element(page=page)
    element_one = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=container_element,
    )
    element_two = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=container_element,
    )

    url = reverse("api:builder:element:move", kwargs={"element_id": element_two.id})
    response = api_client.patch(
        url,
        {
            "position": GraphPointPosition.NORTH,
            "reference_element_id": container_element.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200

    page.refresh_from_db(fields=["graph"])
    assert page.get_graph().graph == {
        "0": element_two.id,
        str(container_element.id): {"children": {"0": [element_one.id]}},
        str(element_one.id): {},
        str(element_two.id): {"next": {"": [container_element.id]}},
    }


@pytest.mark.django_db
def test_move_element_returns_error_when_place_in_container_is_invalid(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    column_element = data_fixture.create_builder_column_element(
        page=page, column_amount=2
    )
    child = data_fixture.create_builder_text_element(page=page)

    url = reverse("api:builder:element:move", kwargs={"element_id": child.id})
    response = api_client.patch(
        url,
        {
            "reference_element_id": column_element.id,
            "place_in_container": "9999",
            "position": GraphPointPosition.CHILD,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == ["place_in_container can at most be 1, (9999, was given)"]


@pytest.mark.django_db
def test_move_element_with_before_returns_error_when_place_in_container_is_invalid(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    column_element = data_fixture.create_builder_column_element(
        page=page, column_amount=2
    )
    first_child = data_fixture.create_builder_text_element(
        page=page,
        place_in_container="0",
        reference_element=column_element,
        position=GraphPointPosition.CHILD,
    )
    second_child = data_fixture.create_builder_text_element(
        page=page,
        place_in_container="0",
        reference_element=column_element,
        position=GraphPointPosition.CHILD,
    )

    url = reverse("api:builder:element:move", kwargs={"element_id": second_child.id})
    response = api_client.patch(
        url,
        {
            "place_in_container": "9999",
            "position": GraphPointPosition.CHILD,
            "reference_element_id": column_element.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == ["place_in_container can at most be 1, (9999, was given)"]

    second_child.refresh_from_db()
    assert second_child.parent_element_id == column_element.id
    assert second_child.place_in_container == "0"


@pytest.mark.django_db
def test_move_element_to_other_page_container_returns_error_when_place_is_invalid(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    target_page = data_fixture.create_builder_page(user=user, builder=builder)
    column_element = data_fixture.create_builder_column_element(
        page=target_page, column_amount=2
    )
    child = data_fixture.create_builder_text_element(page=page)

    url = reverse("api:builder:element:move", kwargs={"element_id": child.id})
    response = api_client.patch(
        url,
        {
            "reference_element_id": column_element.id,
            "place_in_container": "9999",
            "position": GraphPointPosition.CHILD,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == ["place_in_container can at most be 1, (9999, was given)"]

    child.refresh_from_db()
    assert child.page_id == page.id
    assert child.parent_element_id is None
    assert child.place_in_container == ""


@pytest.mark.django_db
def test_move_element_to_shared_page_without_parent_is_invalid_for_regular_element(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    shared_page = builder.shared_page
    element = data_fixture.create_builder_text_element(page=page)

    url = reverse("api:builder:element:move", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {
            "target_page_id": shared_page.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST

    element.refresh_from_db()
    assert element.page_id == page.id
    assert element.parent_element_id is None
    assert element.place_in_container == ""


@pytest.mark.django_db
def test_move_element_to_regular_page_without_parent_is_invalid_for_shared_element(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    shared_page = builder.shared_page
    header = data_fixture.create_builder_element(
        HeaderElementType,
        user=user,
        page=shared_page,
        share_type="all",
    )

    url = reverse("api:builder:element:move", kwargs={"element_id": header.id})
    response = api_client.patch(
        url,
        {
            "target_page_id": page.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST

    header.refresh_from_db()
    assert header.page_id == shared_page.id
    assert header.parent_element_id is None


@pytest.mark.django_db
def test_can_move_element_between_places(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    container_element = data_fixture.create_builder_column_element(page=page)
    element_one = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=container_element,
    )
    element_two = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=container_element,
    )

    url = reverse("api:builder:element:move", kwargs={"element_id": element_two.id})
    response = api_client.patch(
        url,
        {
            "place_in_container": "1",
            "position": GraphPointPosition.CHILD,
            "reference_element_id": container_element.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200

    page.refresh_from_db(fields=["graph"])
    assert page.get_graph().graph == {
        "0": container_element.id,
        str(container_element.id): {
            "children": {"0": [element_one.id], "1": [element_two.id]}
        },
        str(element_one.id): {},
        str(element_two.id): {},
    }


@pytest.mark.django_db
def test_duplicate_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    container = data_fixture.create_builder_column_element(page=page, column_amount=2)
    heading = data_fixture.create_builder_heading_element(
        value="'test'",
        page=page,
        place_in_container="1",
        position=GraphPointPosition.CHILD,
        reference_element=container,
    )

    url = reverse("api:builder:element:duplicate", kwargs={"element_id": container.id})
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")

    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert len(response_json["elements"]) == 2
    duplicated_container = response_json["elements"][0]
    duplicated_heading = response_json["elements"][1]
    assert response_json["graph_additions"] == {
        str(duplicated_container["id"]): {
            "children": {"1": [duplicated_heading["id"]]}
        },
        str(duplicated_heading["id"]): {},
    }

    page.refresh_from_db(fields=["graph"])
    page.assert_reference(
        {
            "0": "column",
            "column": {"next": {"": ["column-"]}, "children": {"": ["heading"]}},
            "heading": {},
            "column-": {"children": {"": ["heading-"]}},
            "heading-": {},
        }
    )


@pytest.mark.django_db
def test_duplicate_container_preserves_child_order(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    form_container = data_fixture.create_builder_form_container_element(page=page)

    # Create children in reverse graph order so pk(checkbox) < pk(text) < pk(input_text) < pk(heading).
    # Desired graph order: heading → input_text → text → checkbox
    checkbox = data_fixture.create_builder_checkbox_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=form_container,
        place_in_container="",
    )
    text = data_fixture.create_builder_text_element(
        page=page,
        position=GraphPointPosition.NORTH,
        reference_element=checkbox,
    )
    input_text = data_fixture.create_builder_input_text_element(
        page=page,
        position=GraphPointPosition.NORTH,
        reference_element=text,
    )
    heading = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.NORTH,
        reference_element=input_text,
    )

    # Confirm pk order is the inverse of graph order.
    assert checkbox.id < text.id < input_text.id < heading.id

    url = reverse(
        "api:builder:element:duplicate",
        kwargs={"element_id": form_container.id},
    )
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK

    response_json = response.json()
    fc_copy, h_copy, it_copy, t_copy, cb_copy = response_json["elements"]

    # Types reveal graph order. If children were iterated in pk order (checkbox has
    # the lowest pk), checkbox would appear first instead of heading.
    assert fc_copy["type"] == "form_container"
    assert h_copy["type"] == "heading"
    assert it_copy["type"] == "input_text"
    assert t_copy["type"] == "text"
    assert cb_copy["type"] == "checkbox"

    # graph_additions must form the same chain as the original:
    # fc_copy → h_copy → it_copy → t_copy → cb_copy
    assert response_json["graph_additions"] == {
        str(fc_copy["id"]): {"children": {"": [h_copy["id"]]}},
        str(h_copy["id"]): {"next": {"": [it_copy["id"]]}},
        str(it_copy["id"]): {"next": {"": [t_copy["id"]]}},
        str(t_copy["id"]): {"next": {"": [cb_copy["id"]]}},
        str(cb_copy["id"]): {},
    }


@pytest.mark.django_db
def test_duplicate_element_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:element:duplicate", kwargs={"element_id": 0})
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ELEMENT_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_child_type_not_allowed_validation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    reference_element = data_fixture.create_builder_form_container_element(page=page)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": "form_container",
            "position": GraphPointPosition.CHILD,
            "reference_element_id": reference_element.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == [
        "Container of type form_container can't have child of type form_container"
    ]


@pytest.mark.django_db
def test_choice_options_created(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    options = [{"value": "'hello'", "name": "'there'"}]

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": "choice", "options": options},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["options"][0]["value"] == "'hello'"
    assert ChoiceElementOption.objects.count() == len(options)


@pytest.mark.django_db
def test_choice_options_updated(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    choice_element = data_fixture.create_builder_choice_element(page=page)

    # Add an existing option
    ChoiceElementOption.objects.create(choice=choice_element)

    options = [{"value": "'hello'", "name": "'there'"}]

    url = reverse("api:builder:element:item", kwargs={"element_id": choice_element.id})
    response = api_client.patch(
        url,
        {"options": options},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["options"][0]["value"] == "'hello'"
    assert ChoiceElementOption.objects.count() == len(options)


@pytest.mark.django_db
def test_choice_options_deleted(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    choice_element = data_fixture.create_builder_choice_element(page=page)

    # Add an existing option
    ChoiceElementOption.objects.create(choice=choice_element)

    url = reverse("api:builder:element:item", kwargs={"element_id": choice_element.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert ChoiceElementOption.objects.count() == 0


@pytest.mark.django_db
def test_create_collection_element_type_with_invalid_data_source_id(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_table_element(page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {"data_source_id": 999999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DATA_SOURCE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_collection_element_with_property_option(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_repeat_element(user=user, page=page)
    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {
            "property_options": [
                {
                    "schema_property": "foo",
                    "searchable": False,
                    "filterable": True,
                    "sortable": True,
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["property_options"] == [
        {
            "schema_property": "foo",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        }
    ]

    response = api_client.patch(
        url,
        {
            "property_options": [
                {
                    "schema_property": "bar",
                    "searchable": False,
                    "filterable": False,
                    "sortable": False,
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["property_options"] == [
        {
            "schema_property": "bar",
            "searchable": False,
            "filterable": False,
            "sortable": False,
        }
    ]


@pytest.mark.django_db
def test_create_collection_element_with_non_unique_schema_properties(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_repeat_element(user=user, page=page)
    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {
            "property_options": [
                {
                    "schema_property": "foo",
                    "searchable": False,
                    "filterable": True,
                    "sortable": True,
                },
                {
                    "schema_property": "foo",
                    "searchable": True,
                    "filterable": True,
                    "sortable": True,
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ELEMENT_PROPERTY_OPTIONS_NOT_UNIQUE"


@pytest.mark.django_db
def test_create_collection_element_with_blank_property_option_schema_property(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_repeat_element(user=user, page=page)
    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {"property_options": [{"schema_property": ""}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            "property_options": [
                {
                    "schema_property": [
                        {"error": "This field may not be blank.", "code": "blank"}
                    ]
                }
            ]
        },
    }
