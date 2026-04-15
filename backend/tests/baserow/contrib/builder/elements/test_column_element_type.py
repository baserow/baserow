import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.builder.elements.element_types import (
    ColumnElementType,
)
from baserow.core.db import specific_iterator
from baserow.core.graph.types import GraphPointPosition
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
    container = data_fixture.create_builder_column_element(page=page)
    element_inside_container_one = data_fixture.create_builder_heading_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_two = data_fixture.create_builder_text_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_three = data_fixture.create_builder_image_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_four = data_fixture.create_builder_iframe_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_five = data_fixture.create_builder_link_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_six = data_fixture.create_builder_button_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_seven = data_fixture.create_builder_table_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_eight = data_fixture.create_builder_input_text_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_nine = data_fixture.create_builder_choice_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_ten = data_fixture.create_builder_checkbox_element(
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )
    element_inside_container_eleven = data_fixture.create_builder_element(
        AuthFormElementType,
        page=page,
        reference_element=container,
        position=GraphPointPosition.CHILD,
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
    assert element_inside_container_one.get_sibling_points() == [
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
