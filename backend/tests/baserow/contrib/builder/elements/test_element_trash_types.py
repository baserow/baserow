import pytest

from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.trash_types import ElementTrashableItemType
from baserow.core.graph.types import GraphPointPosition
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_trashing_and_restoring_element_updates_graph(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    second = data_fixture.create_builder_heading_element(page=page)

    page.assert_reference(
        {
            "0": "heading",
            "heading": {"next": {"": ["heading-"]}},
            "heading-": {},
        }
    )

    builder = page.builder
    trash_entry = TrashHandler.trash(user, builder.workspace, builder, first)

    assert trash_entry.additional_restoration_data == {
        "position": [None, "south", ""],
        "hierarchical_parent_id": None,
        "children": [],
    }

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "heading",
            "heading": {},
        }
    )

    TrashHandler.restore_item(
        user,
        ElementTrashableItemType.type,
        first.id,
    )

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "heading",
            "heading": {"next": {"": ["heading-"]}},
            "heading-": {},
        }
    )


@pytest.mark.django_db
def test_trashing_second_element_stores_reference_to_first(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    second = data_fixture.create_builder_heading_element(page=page)

    builder = page.builder
    trash_entry = TrashHandler.trash(user, builder.workspace, builder, second)

    assert trash_entry.additional_restoration_data == {
        "position": [str(first.id), "south", ""],
        "hierarchical_parent_id": None,
        "children": [],
    }


@pytest.mark.django_db
def test_restoring_element_after_reference_deleted_is_disallowed(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    second = data_fixture.create_builder_heading_element(page=page)

    builder = page.builder
    TrashHandler.trash(user, builder.workspace, builder, second)

    first.delete()

    with pytest.raises(TrashItemRestorationDisallowed) as exc:
        TrashHandler.restore_item(
            user,
            ElementTrashableItemType.type,
            second.id,
        )

    assert exc.value.args[0] == (
        "This record cannot be restored as its reference record has been deleted."
    )


@pytest.mark.django_db
def test_trashing_container_soft_deletes_children_and_restore_brings_them_back(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    container = data_fixture.create_builder_column_element(page=page, column_amount=2)
    child1 = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=container,
        place_in_container="0",
    )
    child2 = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=container,
        place_in_container="1",
    )

    builder = page.builder
    trash_entry = TrashHandler.trash(user, builder.workspace, builder, container)

    # Container is trashed; children are soft-deleted too (not accessible via objects).
    assert container.trashed is True
    assert not Element.objects.filter(id__in=[child1.id, child2.id]).exists()
    assert Element.trash.filter(id__in=[child1.id, child2.id]).count() == 2

    # Restoration data records both the container's own position and its children.
    data = trash_entry.additional_restoration_data
    assert data["position"] == [None, "south", ""]
    assert len(data["children"]) == 2
    child_ids = [row[0] for row in data["children"]]
    assert child1.id in child_ids
    assert child2.id in child_ids

    # After restore the container and its children are all back in the graph.
    TrashHandler.restore_item(user, ElementTrashableItemType.type, container.id)

    container.refresh_from_db()
    assert container.trashed is False
    assert Element.objects.filter(id__in=[child1.id, child2.id]).count() == 2

    page.refresh_from_db(fields=["graph"])
    for element_id in [container.id, child1.id, child2.id]:
        assert str(element_id) in page.graph


@pytest.mark.django_db
def test_trashing_child_records_its_parent(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    container = data_fixture.create_builder_column_element(page=page, column_amount=2)
    child = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=container,
        place_in_container="0",
    )

    builder = page.builder
    trash_entry = TrashHandler.trash(user, builder.workspace, builder, child)

    # The child's restoration data records the container as its parent so that the
    # restore can later refuse if the parent is still trashed.
    assert (
        trash_entry.additional_restoration_data["hierarchical_parent_id"]
        == container.id
    )


@pytest.mark.django_db
def test_get_name_mentions_parent_for_nested_element(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    container = data_fixture.create_builder_column_element(page=page, column_amount=2)
    child = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=container,
        place_in_container="0",
    )

    name = ElementTrashableItemType().get_name(child)

    assert name == f"heading ({child.id}) inside column ({container.id})"


@pytest.mark.django_db
def test_restoring_child_before_parent_is_disallowed(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    container = data_fixture.create_builder_column_element(page=page, column_amount=2)
    child = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=container,
        place_in_container="0",
    )

    builder = page.builder

    # Trash the child first, then its parent container. Both have their own entry.
    TrashHandler.trash(user, builder.workspace, builder, child)
    TrashHandler.trash(user, builder.workspace, builder, container)

    # The child cannot be restored while its parent is still trashed. The message
    # names the parent so the user knows what to restore first.
    with pytest.raises(TrashItemRestorationDisallowed) as exc:
        TrashHandler.restore_item(user, ElementTrashableItemType.type, child.id)

    assert exc.value.args[0] == (
        f"This record cannot be restored until its parent "
        f"Column ({container.id}) is restored first."
    )

    # The child is still trashed (the failed restore rolled back).
    child.refresh_from_db()
    assert child.trashed is True

    # Once the parent is restored, the child can be restored too.
    TrashHandler.restore_item(user, ElementTrashableItemType.type, container.id)
    TrashHandler.restore_item(user, ElementTrashableItemType.type, child.id)

    child.refresh_from_db()
    container.refresh_from_db()
    assert child.trashed is False
    assert container.trashed is False

    page.refresh_from_db(fields=["graph"])
    assert str(child.id) in page.graph
    assert str(container.id) in page.graph
