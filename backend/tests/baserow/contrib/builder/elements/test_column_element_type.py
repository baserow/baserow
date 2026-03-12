import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.builder.elements.element_types import (
    ButtonElementType,
    CheckboxElementType,
    ChoiceElementType,
    ColumnElementType,
    HeadingElementType,
    IFrameElementType,
    ImageElementType,
    InputTextElementType,
    LinkElementType,
    TableElementType,
    TextElementType,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.core.db import specific_iterator
from baserow_enterprise.builder.elements.element_types import AuthFormElementType


@pytest.mark.django_db
def test_get_new_place_in_container(data_fixture):
    column_element = data_fixture.create_builder_column_element(column_amount=3)

    assert ColumnElementType().get_new_place_in_container(column_element, ["2"]) == 1
    assert (
        ColumnElementType().get_new_place_in_container(column_element, ["2", "1"]) == 0
    )
    assert ColumnElementType().get_new_place_in_container(column_element, []) == 2


@pytest.mark.django_db
def test_get_places_in_container_removed(data_fixture):
    column_element = data_fixture.create_builder_column_element(column_amount=3)

    assert ColumnElementType().get_places_in_container_removed(
        {"column_amount": 2}, column_element
    ) == ["2"]
    assert ColumnElementType().get_places_in_container_removed(
        {"column_amount": 1}, column_element
    ) == ["1", "2"]
    assert (
        ColumnElementType().get_places_in_container_removed(
            {"column_amount": 3}, column_element
        )
        == []
    )
    assert ColumnElementType().get_places_in_container_removed(
        {"column_amount": 0}, column_element
    ) == ["0", "1", "2"]


@pytest.mark.django_db
def test_apply_order_by_children(data_fixture):
    column_element = data_fixture.create_builder_column_element(column_amount=20)
    first_element = data_fixture.create_builder_heading_element(
        reference_element=column_element, place_in_container="0"
    )
    last_element = data_fixture.create_builder_text_element(
        reference_element=column_element, place_in_container="11"
    )
    middle_element = data_fixture.create_builder_text_element(
        reference_element=column_element, place_in_container="5"
    )

    queryset = Element.objects.filter(parent_element=column_element)
    queryset_ordered = ColumnElementType().apply_order_by_children(queryset)

    ids_ordered = [element.id for element in queryset_ordered]

    assert ids_ordered == [first_element.id, middle_element.id, last_element.id]


@pytest.mark.django_db
def test_validate_place_in_container(data_fixture):
    column_element = data_fixture.create_builder_column_element(column_amount=2)

    with pytest.raises(ValidationError):
        ColumnElementType().validate_place_in_container("5", column_element)

    try:
        ColumnElementType().validate_place_in_container("1", column_element)
    except ValidationError:
        pytest.fail("Should not have raised since 1 is between 0-1")


@pytest.mark.django_db
def test_column_element_type_can_have_children(data_fixture):
    """
    We are using the column element type here to test it with the ElementHandler.
    Ideally, every element type that can be added to a column element should be tested
    """

    page = data_fixture.create_builder_page()
    container = ElementHandler().create_element(ColumnElementType(), page=page)
    element_inside_container_one = ElementHandler().create_element(
        HeadingElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_two = ElementHandler().create_element(
        TextElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_three = ElementHandler().create_element(
        ImageElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_four = ElementHandler().create_element(
        IFrameElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_five = ElementHandler().create_element(
        LinkElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_six = ElementHandler().create_element(
        ButtonElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_seven = ElementHandler().create_element(
        TableElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_eight = ElementHandler().create_element(
        InputTextElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_nine = ElementHandler().create_element(
        ChoiceElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_ten = ElementHandler().create_element(
        CheckboxElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )
    element_inside_container_eleven = ElementHandler().create_element(
        AuthFormElementType(),
        page=page,
        parent_element_id=container.id,
        place_in_container="1",
    )

    assert list(specific_iterator(container.children.all())) == [
        element_inside_container_one,
        element_inside_container_two,
        element_inside_container_three,
        element_inside_container_four,
        element_inside_container_five,
        element_inside_container_six,
        element_inside_container_seven,
        element_inside_container_eight,
        element_inside_container_nine,
        element_inside_container_ten,
        element_inside_container_eleven,
    ]
    assert not container.is_nested_point
    assert element_inside_container_one.is_nested_point
    assert element_inside_container_two.is_nested_point
    assert list(
        specific_iterator(element_inside_container_one.get_sibling_points())
    ) == [
        element_inside_container_two,
        element_inside_container_three,
        element_inside_container_four,
        element_inside_container_five,
        element_inside_container_six,
        element_inside_container_seven,
        element_inside_container_eight,
        element_inside_container_nine,
        element_inside_container_ten,
        element_inside_container_eleven,
    ]
