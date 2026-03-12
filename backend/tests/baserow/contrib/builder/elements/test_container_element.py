import pytest

from baserow.contrib.builder.elements.models import ColumnElement, HeadingElement
from baserow.core.db import specific_iterator


@pytest.mark.django_db
def test_column_element_can_have_children(data_fixture):
    """
    We are using the column element here as an example of a container element. A
    container element is an element that can have children elements. In this case the
    column element can have children elements, but the heading element can not.
    """

    page = data_fixture.create_builder_page()
    container_element = ColumnElement.objects.create(page=page)
    child_element_one = HeadingElement.objects.create(
        page=page, parent_element=container_element
    )
    child_element_two = HeadingElement.objects.create(
        page=page, parent_element=container_element
    )

    assert list(specific_iterator(container_element.children.all())) == [
        child_element_one,
        child_element_two,
    ]
    assert not container_element.is_nested_point
    assert child_element_one.is_nested_point
    assert child_element_two.is_nested_point
    assert list(specific_iterator(child_element_one.get_sibling_points())) == [
        child_element_two
    ]
