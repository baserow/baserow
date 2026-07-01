import pytest

from baserow.core.graph.types import GraphPointPosition


@pytest.mark.django_db
def test_element_place_in_container(data_fixture):
    page = data_fixture.create_builder_page()
    column = data_fixture.create_builder_column_element(page=page, column_amount=2)
    column1_element1 = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=column,
    )
    column1_element2 = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=column,
    )
    column2_element1 = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="1",
        position=GraphPointPosition.CHILD,
        reference_element=column,
    )
    page.refresh_from_db(fields=["graph"])

    assert column.place_in_container == ""
    assert column1_element1.place_in_container == "0"
    assert column1_element2.place_in_container == "0"
    assert column2_element1.place_in_container == "1"
