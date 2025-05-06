from decimal import Decimal
from unittest.mock import patch

import pytest

from baserow.contrib.builder.elements.exceptions import (
    ElementDoesNotExist,
    ElementNotInSamePage,
)
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.core.exceptions import PermissionException


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
    shared_page = page.builder.shared_page

    if element_type.is_multi_page_element:
        page = shared_page

    prev_is_deactivated = element_type.is_deactivated
    element_type.is_deactivated = lambda x: False

    element1 = data_fixture.create_builder_heading_element(page=page, order="1.0000")
    element3 = data_fixture.create_builder_heading_element(page=page, order="2.0000")

    pytest_params = element_type.get_pytest_params(data_fixture)

    service = ElementService()
    element = service.create_element(user, element_type, page=page, **pytest_params)

    element_type.is_deactivated = prev_is_deactivated

    last_element = Element.objects.last()

    # Check it's the last element
    assert last_element.id == element.id

    element_created_mock.send.assert_called_once_with(
        service, element=element, before_id=None, user=user
    )


@pytest.mark.django_db
def test_create_element_before(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page, order="1.0000")
    element3 = data_fixture.create_builder_heading_element(page=page, order="2.0000")

    element_type = element_type_registry.get("heading")
    pytest_params = element_type.get_pytest_params(data_fixture)

    element2 = ElementService().create_element(
        user, element_type, page=page, before=element3, **pytest_params
    )

    elements = Element.objects.all()
    assert elements[0].id == element1.id
    assert elements[1].id == element2.id
    assert elements[2].id == element3.id


@pytest.mark.django_db
def test_create_element_before_not_same_page(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page, order="1.0000")
    element3 = data_fixture.create_builder_heading_element(order="2.0000")

    element_type = element_type_registry.get("heading")
    pytest_params = element_type.get_pytest_params(data_fixture)

    with pytest.raises(ElementNotInSamePage):
        ElementService().create_element(
            user, element_type, page=page, before=element3, **pytest_params
        )


@pytest.mark.django_db
def test_get_unique_orders_before_element_triggering_full_page_order_reset(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element_1 = data_fixture.create_builder_heading_element(
        page=page, order="1.00000000000000000000"
    )
    element_2 = data_fixture.create_builder_heading_element(
        page=page, order="1.00000000000000001000"
    )
    element_3 = data_fixture.create_builder_heading_element(
        page=page, order="2.99999999999999999999"
    )
    element_4 = data_fixture.create_builder_heading_element(
        page=page, order="2.99999999999999999998"
    )

    element_type = element_type_registry.get("heading")
    pytest_params = element_type.get_pytest_params(data_fixture)

    element_created = ElementService().create_element(
        user, element_type, page=page, before=element_3, **pytest_params
    )

    element_1.refresh_from_db()
    element_2.refresh_from_db()
    element_3.refresh_from_db()
    element_4.refresh_from_db()

    assert element_1.order == Decimal("1.00000000000000000000")
    assert element_2.order == Decimal("2.00000000000000000000")
    assert element_4.order == Decimal("3.00000000000000000000")
    assert element_3.order == Decimal("4.00000000000000000000")
    assert element_created.order == Decimal("3.50000000000000000000")


@pytest.mark.django_db
@patch("baserow.contrib.builder.elements.service.element_orders_recalculated")
def test_recalculate_full_order(element_orders_recalculated_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page, order="1.9000")
    data_fixture.create_builder_heading_element(page=page, order="3.4000")

    service = ElementService()
    service.recalculate_full_orders(user, page)

    element_orders_recalculated_mock.send.assert_called_once_with(service, page=page)


@pytest.mark.django_db
def test_create_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    element_type = element_type_registry.get("heading")

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        ElementService().create_element(
            user,
            element_type,
            page=page,
            **element_type.get_pytest_params(data_fixture),
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

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
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

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
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

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
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

    service = ElementService()
    element_moved = service.move_element(
        user,
        element3,
        element3.parent_element,
        element3.place_in_container,
        before=element2,
    )

    element_moved_mock.send.assert_called_once_with(
        service, element=element_moved, before=element2, user=user
    )


@pytest.mark.django_db
def test_move_element_not_same_page(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page2)

    with pytest.raises(ElementNotInSamePage):
        ElementService().move_element(
            user,
            element3,
            element3.parent_element,
            element3.place_in_container,
            before=element2,
        )


@pytest.mark.django_db
def test_move_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        ElementService().move_element(
            user,
            element3,
            element3.parent_element,
            element3.place_in_container,
            before=element2,
        )


@pytest.mark.django_db
@patch("baserow.contrib.builder.elements.service.element_orders_recalculated")
def test_move_element_trigger_order_recalculated(
    element_orders_recalculated_mock, data_fixture
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(
        page=page, order="2.99999999999999999998"
    )
    element2 = data_fixture.create_builder_heading_element(
        page=page, order="2.99999999999999999999"
    )
    element3 = data_fixture.create_builder_heading_element(page=page, order="3.0000")

    service = ElementService()
    service.move_element(
        user,
        element3,
        element3.parent_element,
        element3.place_in_container,
        before=element2,
    )

    element_orders_recalculated_mock.send.assert_called_once_with(service, page=page)


@pytest.mark.django_db
@patch("baserow.contrib.builder.elements.service.elements_created")
def test_duplicate_element(elements_created_mock, data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    service = ElementService()
    elements_duplicated = service.duplicate_element(user, element)["elements"]

    elements_created_mock.send.assert_called_once_with(
        service, elements=elements_duplicated, user=user, page=element.page
    )


@pytest.mark.django_db(transaction=True)
def test_duplicate_element_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        ElementService().duplicate_element(user, element)
