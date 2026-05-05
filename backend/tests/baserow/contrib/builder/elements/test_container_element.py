import pytest

from baserow.core.graph.types import GraphPointPosition


@pytest.mark.django_db
def test_column_element_can_have_children(data_fixture):
    page = data_fixture.create_builder_page()
    column = data_fixture.create_builder_column_element(page=page)
    child_element_one = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=column,
    )
    child_element_two = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=column,
    )

    child_ids = [child.id for child in column.children.all()]
    assert child_ids == [
        child_element_one.id,
        child_element_two.id,
    ]
    assert not column.is_nested_point
    assert child_element_one.is_nested_point
    assert child_element_two.is_nested_point
    assert child_element_one.get_sibling_points() == [child_element_two]
