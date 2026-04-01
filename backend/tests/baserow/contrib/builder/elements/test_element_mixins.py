import pytest

from baserow.contrib.builder.elements.mixins import ContainerElementTypeMixin


@pytest.mark.django_db
def test_after_move_updates_descendants_page_ids_recursively(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    target_page = data_fixture.create_builder_page(user=user, builder=builder)

    outer_container = data_fixture.create_builder_form_container_element(page=page)
    outer_text = data_fixture.create_builder_text_element(
        page=page, parent_element=outer_container
    )
    column_container = data_fixture.create_builder_column_element(
        page=page, parent_element=outer_container, column_amount=1
    )
    column_text = data_fixture.create_builder_text_element(
        page=page, parent_element=column_container, place_in_container="0"
    )
    inner_container = data_fixture.create_builder_form_container_element(
        page=page, parent_element=column_container, place_in_container="0"
    )
    inner_text = data_fixture.create_builder_text_element(
        page=page, parent_element=inner_container
    )

    outer_container.page = target_page
    outer_container.save(update_fields=["page"])

    ContainerElementTypeMixin().after_move(outer_container)

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
