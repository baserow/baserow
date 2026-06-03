import pytest

from baserow.contrib.builder.elements.service import ElementService
from baserow.core.graph.types import GraphPointPosition


@pytest.mark.django_db
def test_move_container_element_updates_child_page_ids_recursively(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    target_page = data_fixture.create_builder_page(user=user, builder=builder)

    outer_container = data_fixture.create_builder_form_container_element(page=page)
    outer_text = data_fixture.create_builder_text_element(
        page=page, reference_element=outer_container, position=GraphPointPosition.CHILD
    )
    column_container = data_fixture.create_builder_column_element(
        page=page,
        reference_element=outer_container,
        position=GraphPointPosition.CHILD,
        column_amount=1,
    )
    column_text = data_fixture.create_builder_text_element(
        page=page,
        reference_element=column_container,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )
    inner_container = data_fixture.create_builder_form_container_element(
        page=page,
        reference_element=column_container,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )
    inner_text = data_fixture.create_builder_text_element(
        page=page, reference_element=inner_container, position=GraphPointPosition.CHILD
    )

    ElementService().move_element(
        user,
        target_page,
        outer_container,
        place_in_container="",
        reference_element_id=None,
        position=GraphPointPosition.SOUTH,
    )

    for element in [
        outer_container,
        outer_text,
        column_container,
        column_text,
        inner_container,
        inner_text,
    ]:
        element.refresh_from_db()
        assert element.page_id == target_page.id


@pytest.mark.django_db
def test_after_move_unlinks_non_shared_data_source_when_moved_to_shared_page(
    data_fixture,
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    shared_page = builder.shared_page

    table_element = data_fixture.create_builder_table_element(page=page)
    table_element.schema_property = "field_1"
    table_element.save(update_fields=["schema_property"])
    table_element.property_options.create(schema_property="field_1", sortable=True)

    with table_element.get_type().wrap_move(
        table_element,
        None,
        GraphPointPosition.SOUTH,
        shared_page,
        "",
    ):
        table_element.page = shared_page
        table_element.save(update_fields=["page"])

    table_element.refresh_from_db()

    assert table_element.page_id == shared_page.id
    assert table_element.data_source_id is None
    assert table_element.schema_property is None
    assert table_element.property_options.count() == 0
