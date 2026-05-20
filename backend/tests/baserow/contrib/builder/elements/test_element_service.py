from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.elements.exceptions import (
    ElementDoesNotExist,
    ElementNotInSamePage,
)
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.pages.exceptions import PageNotInBuilder
from baserow.core.exceptions import PermissionException
from baserow.core.graph.types import GraphPointPosition


def pytest_generate_tests(metafunc):
    if "element_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "element_type",
            [pytest.param(e, id=e.type) for e in element_type_registry.get_all()],
        )


@pytest.mark.django_db
@patch("baserow.contrib.builder.elements.service.element_created")
def test_create_element(element_created_mock, data_fixture, element_type):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    shared_page = page.builder.shared_page

    if element_type.is_multi_page_element:
        page = shared_page

    prev_is_deactivated = element_type.is_deactivated
    element_type.is_deactivated = lambda x: False

    pytest_params = element_type.get_pytest_params(data_fixture)

    service = ElementService()
    element = service.create_element(user, element_type, page=page, **pytest_params)

    element_type.is_deactivated = prev_is_deactivated

    last_element = Element.objects.last()

    # Check it's the last element
    assert last_element.id == element.id

    element_created_mock.send.assert_called_once_with(
        service, element=element, user=user
    )


@pytest.mark.django_db
def test_create_element_before(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_heading_element(page=page)

    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element3.id]}},
        str(element3.id): {},
    }

    element_type = element_type_registry.get("heading")
    pytest_params = element_type.get_pytest_params(data_fixture)

    element2 = ElementService().create_element(
        user, element_type, page, element3.id, GraphPointPosition.NORTH, **pytest_params
    )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element2.id]}},
        str(element2.id): {"next": {"": [element3.id]}},
        str(element3.id): {},
    }


@pytest.mark.django_db
def test_create_element_before_not_same_page(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_heading_element()

    element_type = element_type_registry.get("heading")
    pytest_params = element_type.get_pytest_params(data_fixture)

    with pytest.raises(ElementNotInSamePage):
        ElementService().create_element(
            user,
            element_type,
            page=page,
            reference_element_id=element3.id,
            **pytest_params,
        )


@pytest.mark.django_db
def test_create_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    element_type = element_type_registry.get("heading")

    with (
        stub_check_permissions(raise_permission_denied=True),
        pytest.raises(PermissionException),
    ):
        ElementService().create_element(
            user,
            element_type,
            page=page,
            **element_type.get_pytest_params(data_fixture),
        )


@pytest.mark.django_db
def test_create_element_and_shared_page(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    shared_page = page.builder.shared_page

    regular_element_type = next(
        filter(lambda t: not t.is_multi_page_element, element_type_registry.get_all())
    )

    with pytest.raises(DRFValidationError):
        ElementService().create_element(
            user=user,
            element_type=regular_element_type,
            page=shared_page,
            **regular_element_type.get_pytest_params(data_fixture),
        )

    shared_element_type = next(
        filter(lambda t: t.is_multi_page_element, element_type_registry.get_all())
    )

    with pytest.raises(DRFValidationError):
        ElementService().create_element(
            user=user,
            element_type=shared_element_type,
            page=page,
            **shared_element_type.get_pytest_params(data_fixture),
        )


@pytest.mark.django_db
def test_get_element(data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    assert ElementService().get_element(user, element.id).id == element.id


@pytest.mark.django_db
def test_get_element_does_not_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(ElementDoesNotExist):
        assert ElementService().get_element(user, 0)


@pytest.mark.django_db
def test_get_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    with (
        stub_check_permissions(raise_permission_denied=True),
        pytest.raises(PermissionException),
    ):
        ElementService().get_element(user, element.id)


@pytest.mark.django_db
def test_get_elements(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page)

    assert [p.id for p in ElementService().get_elements(user, page)] == [
        element1.id,
        element2.id,
        element3.id,
    ]

    def exclude_element_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=element1.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_element_1

        assert [p.id for p in ElementService().get_elements(user, page)] == [
            element2.id,
            element3.id,
        ]


@pytest.mark.django_db
def test_get_builder_elements(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page.builder)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page2)

    def exclude_element_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=element1.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_element_1

        assert sorted(
            [p.id for p in ElementService().get_builder_elements(user, page.builder)]
        ) == sorted(
            [
                element2.id,
                element3.id,
            ]
        )


@pytest.mark.django_db
@patch("baserow.contrib.builder.elements.service.element_deleted")
def test_delete_element(element_deleted_mock, data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    service = ElementService()
    service.delete_element(user, element)

    element_deleted_mock.send.assert_called_once_with(
        service, element_id=element.id, page=element.page, user=user
    )


@pytest.mark.django_db(transaction=True)
def test_delete_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    with (
        stub_check_permissions(raise_permission_denied=True),
        pytest.raises(PermissionException),
    ):
        ElementService().delete_element(user, element)


@pytest.mark.django_db
@patch("baserow.contrib.builder.elements.service.element_updated")
def test_update_element(element_updated_mock, data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    service = ElementService()
    element_updated = service.update_element(user, element, value="newValue")

    element_updated_mock.send.assert_called_once_with(
        service, element=element_updated, user=user
    )


@pytest.mark.django_db(transaction=True)
def test_update_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    with (
        stub_check_permissions(raise_permission_denied=True),
        pytest.raises(PermissionException),
    ):
        ElementService().update_element(user, element, value="newValue")


@pytest.mark.django_db
@patch("baserow.contrib.builder.elements.service.element_moved")
def test_move_element(element_moved_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page)

    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element2.id]}},
        str(element2.id): {"next": {"": [element3.id]}},
        str(element3.id): {},
    }

    service = ElementService()
    service.move_element(
        user,
        page,
        element3,
        element3.place_in_container,
        element2.id,
        GraphPointPosition.NORTH,
    )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element3.id]}},
        str(element3.id): {"next": {"": [element2.id]}},
        str(element2.id): {},
    }

    element_moved_mock.send.assert_called_once_with(
        service,
        element=element3,
        position=GraphPointPosition.NORTH,
        reference_element=element2,
        user=user,
    )


@pytest.mark.django_db
def test_move_element_not_same_builder(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page2)

    with pytest.raises(PageNotInBuilder):
        ElementService().move_element(
            user,
            page,
            element3,
            element3.place_in_container,
            element2.id,
            GraphPointPosition.SOUTH,
        )


@pytest.mark.django_db
def test_move_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page)

    with (
        stub_check_permissions(raise_permission_denied=True),
        pytest.raises(PermissionException),
    ):
        ElementService().move_element(
            user,
            page,
            element3,
            element3.place_in_container,
            element2,
            GraphPointPosition.SOUTH,
        )


@pytest.mark.django_db
@patch("baserow.contrib.builder.elements.service.elements_created")
def test_duplicate_element(elements_created_mock, data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    service = ElementService()
    result = service.duplicate_element(user, element)

    elements_created_mock.send.assert_called_once_with(
        service,
        elements=result["elements"],
        workflow_actions=result["workflow_actions"],
        user=user,
        page=element.page,
    )


@pytest.mark.django_db(transaction=True)
def test_duplicate_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    with (
        stub_check_permissions(raise_permission_denied=True),
        pytest.raises(PermissionException),
    ):
        ElementService().duplicate_element(user, element)


@pytest.mark.django_db
def test_move_element_end_of_page(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_heading_element(page=page)

    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element2.id]}},
        str(element2.id): {"next": {"": [element3.id]}},
        str(element3.id): {},
    }

    ElementService().move_element(
        user,
        page,
        element1,
        element1.place_in_container,
        element3.id,
        GraphPointPosition.SOUTH,
    )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": element2.id,
        str(element2.id): {"next": {"": [element3.id]}},
        str(element3.id): {"next": {"": [element1.id]}},
        str(element1.id): {},
    }


@pytest.mark.django_db
def test_move_element_before(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_heading_element(page=page)

    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element2.id]}},
        str(element2.id): {"next": {"": [element3.id]}},
        str(element3.id): {},
    }

    ElementService().move_element(
        user,
        page,
        element3,
        element3.place_in_container,
        element2.id,
        GraphPointPosition.NORTH,
    )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element3.id]}},
        str(element3.id): {"next": {"": [element2.id]}},
        str(element2.id): {},
    }


@pytest.mark.django_db
def test_moving_elements_inside_container(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    container = data_fixture.create_builder_column_element(page=page)
    root_element = data_fixture.create_builder_text_element(page=page)
    element_inside_container_one = data_fixture.create_builder_text_element(
        page=page,
        place_in_container="1",
        reference_element=container,
        position=GraphPointPosition.CHILD,
    )
    element_inside_container_two = data_fixture.create_builder_text_element(
        page=page,
        place_in_container="1",
        reference_element=container,
        position=GraphPointPosition.CHILD,
    )

    assert page.graph == {
        "0": container.id,
        str(container.id): {
            "next": {"": [root_element.id]},
            "children": {"1": [element_inside_container_one.id]},
        },
        str(element_inside_container_one.id): {
            "next": {"": [element_inside_container_two.id]}
        },
        str(element_inside_container_two.id): {},
        str(root_element.id): {},
    }

    ElementService().move_element(
        user,
        page,
        element_inside_container_two,
        element_inside_container_two.place_in_container,
        element_inside_container_one.id,
        GraphPointPosition.NORTH,
    )

    assert page.graph == {
        "0": container.id,
        str(container.id): {
            "next": {"": [root_element.id]},
            "children": {"1": [element_inside_container_two.id]},
        },
        str(element_inside_container_two.id): {
            "next": {"": [element_inside_container_one.id]}
        },
        str(element_inside_container_one.id): {},
        str(root_element.id): {},
    }
