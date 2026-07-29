from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.elements.exceptions import (
    ElementDoesNotExist,
    ElementNotInSamePage,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.pages.exceptions import PageNotInBuilder
from baserow.core.exceptions import PermissionException
from baserow.core.graph.exceptions import GraphPointReferencePointInvalid
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
def test_element_type_validate_position_rejects_invalid_root_page(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    shared_page = page.builder.shared_page

    regular_element_type = element_type_registry.get("heading")
    shared_element_type = next(
        filter(lambda t: t.is_multi_page_element, element_type_registry.get_all())
    )

    with pytest.raises(DRFValidationError):
        regular_element_type.validate_position(
            shared_page, None, "", GraphPointPosition.SOUTH
        )

    shared_element_type.validate_position(
        shared_page, None, "", GraphPointPosition.SOUTH
    )

    with pytest.raises(DRFValidationError):
        shared_element_type.validate_position(page, None, "", GraphPointPosition.SOUTH)


@pytest.mark.django_db
def test_link_element_type_validate_position_uses_base_validation(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    shared_page = page.builder.shared_page

    link_element_type = element_type_registry.get("link")

    with pytest.raises(DRFValidationError):
        link_element_type.validate_position(
            shared_page, None, "", GraphPointPosition.SOUTH
        )


@pytest.mark.django_db
def test_element_type_validate_position_rejects_child_of_non_container(data_fixture):
    page = data_fixture.create_builder_page()
    reference_element = data_fixture.create_builder_heading_element(page=page)
    element_type = element_type_registry.get("text")

    with pytest.raises(GraphPointReferencePointInvalid):
        element_type.validate_position(
            page,
            reference_element,
            "",
            GraphPointPosition.CHILD,
        )


@pytest.mark.django_db
def test_multi_page_element_type_validate_position_rejects_child_position(
    data_fixture,
):
    page = data_fixture.create_builder_page()
    shared_page = page.builder.shared_page
    reference_element = data_fixture.create_builder_column_element(page=shared_page)
    shared_element_type = next(
        filter(lambda t: t.is_multi_page_element, element_type_registry.get_all())
    )

    with pytest.raises(DRFValidationError):
        shared_element_type.validate_position(
            shared_page,
            reference_element,
            "",
            GraphPointPosition.CHILD,
        )

    child_element = data_fixture.create_builder_heading_element(
        page=shared_page,
        reference_element=reference_element,
        position=GraphPointPosition.CHILD,
    )

    with pytest.raises(DRFValidationError):
        shared_element_type.validate_position(
            shared_page,
            child_element,
            "",
            GraphPointPosition.SOUTH,
        )


@pytest.mark.django_db
def test_element_type_validate_position_as_child_rejects_by_default(data_fixture):
    page = data_fixture.create_builder_page()
    reference_element = data_fixture.create_builder_heading_element(page=page)

    with pytest.raises(GraphPointReferencePointInvalid):
        reference_element.get_type().validate_position_as_child("", reference_element)


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
def test_delete_element(data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)
    element_id = element.id

    ElementService().delete_element(user, element)

    element.refresh_from_db()
    assert element.trashed is True
    assert not Element.objects.filter(id=element_id, trashed=False).exists()


@pytest.mark.django_db
def test_delete_container_element_removes_container_and_graph_entries(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    container = data_fixture.create_builder_column_element(page=page, column_amount=2)
    child1 = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=container,
        place_in_container="0",
    )
    child2 = data_fixture.create_builder_column_element(
        page=page,
        column_amount=1,
        position=GraphPointPosition.CHILD,
        reference_element=container,
        place_in_container="1",
    )
    grandchild = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=child2,
        place_in_container="0",
    )

    ElementService().delete_element(user, container)

    container.refresh_from_db()
    assert container.trashed is True

    # Children are soft-deleted (trashed) alongside the container so they can be
    # restored if the container is restored. Not accessible via the default manager.
    assert not Element.objects.filter(
        id__in=[child1.id, child2.id, grandchild.id]
    ).exists()
    assert (
        Element.trash.filter(id__in=[child1.id, child2.id, grandchild.id]).count() == 3
    )

    # All graph entries for the container and its descendants are gone.
    page.refresh_from_db(fields=["graph"])
    for element_id in [container.id, child1.id, child2.id, grandchild.id]:
        assert str(element_id) not in page.graph
    assert page.graph == {}


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
    updated = service.update_element(user, element, value="newValue")

    element_updated_mock.send.assert_called_once_with(
        service, element=updated.element, user=user
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
        source_page=page,
        position=GraphPointPosition.NORTH,
        reference_element=element2,
        user=user,
    )


@pytest.mark.django_db
def test_move_orphan_element_makes_it_join_the_graph(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    # An element that exists in the DB but isn't in the page graph (an "orphan",
    # e.g. created during a not-yet-zero-downtime deployment). create_element does
    # not insert into the graph, so this leaves it absent from it.
    orphan = ElementHandler().create_element(
        element_type_registry.get("heading"), page=page
    )

    page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) not in page.graph

    # Moving the orphan must not raise; it should join the graph at the requested
    # position.
    move = ElementService().move_element(
        user,
        page,
        ElementHandler().get_element_for_update(orphan.id),
        "",
        element1.id,
        GraphPointPosition.SOUTH,
    )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [orphan.id]}},
        str(orphan.id): {},
    }

    # There is no prior position for an orphan, so the move records an
    # append-to-end-of-root position (used by undo to send it back to the bottom).
    assert move.previous_reference_element is None
    assert move.previous_position == GraphPointPosition.SOUTH
    assert move.previous_output == ""


@pytest.mark.django_db
def test_heal_orphan_elements_appends_to_unshared_page_root(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    # An element in the DB but missing from the graph (created without a graph
    # insert, mimicking an old-code write during a non-zero-downtime deploy).
    orphan = ElementHandler().create_element(
        element_type_registry.get("heading"), page=page
    )
    page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) not in page.graph

    patch = ElementHandler().heal_orphan_elements(page)

    # The patch contains only the entries that changed: the orphan's new entry and
    # the element it was linked after.
    assert patch == {
        str(element1.id): {"next": {"": [orphan.id]}},
        str(orphan.id): {},
    }

    page.refresh_from_db(fields=["graph"])
    # The orphan is appended to the end of the (unshared) page's root chain.
    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [orphan.id]}},
        str(orphan.id): {},
    }


@pytest.mark.django_db
def test_heal_orphan_elements_is_a_noop_when_graph_is_consistent(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)

    page.refresh_from_db(fields=["graph"])
    before = dict(page.graph)

    assert ElementHandler().heal_orphan_elements(page) == {}

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before


@pytest.mark.django_db
def test_heal_orphan_elements_appends_to_first_shared_element_on_shared_page(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    shared_page = page.builder.shared_page

    # The first shared element (a Header container) lives at the root of the
    # shared page.
    header = ElementService().create_element(
        user, element_type_registry.get("header"), page=shared_page
    )

    # A regular element on the shared page that's missing from the graph.
    orphan = ElementHandler().create_element(
        element_type_registry.get("heading"), page=shared_page
    )
    shared_page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) not in shared_page.graph

    patch = ElementHandler().heal_orphan_elements(shared_page)

    # The patch carries the orphan and the header (whose children changed).
    assert str(orphan.id) in patch
    assert str(header.id) in patch

    shared_page.refresh_from_db(fields=["graph"])
    # The orphan is appended to the end of the first shared element (the header).
    assert shared_page.graph[str(header.id)]["children"][""] == [orphan.id]


@pytest.mark.django_db
def test_heal_orphan_elements_service_returns_patch_and_persists(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)
    orphan = ElementHandler().create_element(
        element_type_registry.get("heading"), page=page
    )

    patch = ElementService().heal_orphan_elements(user, page)

    assert str(orphan.id) in patch
    page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) in page.graph


@pytest.mark.django_db
@patch("sentry_sdk.capture_message")
def test_heal_orphan_elements_reports_to_sentry(capture_message_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)
    ElementHandler().create_element(element_type_registry.get("heading"), page=page)

    ElementHandler().heal_orphan_elements(page)

    capture_message_mock.assert_called_once()
    # The message reports how many elements were healed, at warning level.
    assert "1 orphan" in capture_message_mock.call_args[0][0]
    assert capture_message_mock.call_args.kwargs["level"] == "warning"


@pytest.mark.django_db
@patch("sentry_sdk.capture_message")
def test_heal_orphan_elements_does_not_report_when_consistent(
    capture_message_mock, data_fixture
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)

    ElementHandler().heal_orphan_elements(page)

    capture_message_mock.assert_not_called()


@pytest.mark.django_db
def test_heal_prunes_stale_point_for_hard_deleted_element(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    # A 3-element root chain through the graph: e1 → e2 → e3.
    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)
    e3 = ElementService().create_element(user, heading, page=page)

    page.refresh_from_db(fields=["graph"])
    assert str(e2.id) in page.graph

    # Simulate old code hard-deleting the middle element's row without touching
    # the graph: the graph now references a point with no DB row ("stale point").
    Element.objects.filter(id=e2.id).delete()

    patch = ElementHandler().heal_orphan_elements(page)

    page.refresh_from_db(fields=["graph"])
    # The stale point is spliced out and the chain re-stitched: e1 → e3.
    assert str(e2.id) not in page.graph
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [e3.id]}},
        str(e3.id): {},
    }
    # The relinked predecessor is carried in the patch.
    assert patch == {str(e1.id): {"next": {"": [e3.id]}}}


@pytest.mark.django_db
def test_heal_prunes_stale_point_and_does_not_raise_on_traversal(data_fixture):
    """A stale point would make graph traversal resolve a missing element and
    raise; after healing, the ordered traversal succeeds."""

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    Element.objects.filter(id=e1.id).delete()  # the root point is now stale

    ElementHandler().heal_orphan_elements(page)

    page.refresh_from_db(fields=["graph"])
    # The surviving element is promoted to root; traversal resolves cleanly.
    assert page.graph == {"0": e2.id, str(e2.id): {}}
    graph = page.get_graph()
    assert graph.get_point(e2.id).id == e2.id


@pytest.mark.django_db
def test_heal_reconciles_orphan_and_stale_point_together(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    # e2 was hard-deleted (stale), and a fresh row was written without a graph
    # insert (orphan) — both at once, as can happen mid-deploy.
    Element.objects.filter(id=e2.id).delete()
    orphan = ElementHandler().create_element(heading, page=page)

    page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) not in page.graph

    ElementHandler().heal_orphan_elements(page)

    page.refresh_from_db(fields=["graph"])
    # Stale e2 pruned, orphan appended to the end of the (now single-element) chain.
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [orphan.id]}},
        str(orphan.id): {},
    }


@pytest.mark.django_db
@patch("sentry_sdk.capture_message")
def test_heal_reports_pruned_stale_points_to_sentry(capture_message_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    ElementService().create_element(user, heading, page=page)
    Element.objects.filter(id=e1.id).delete()

    ElementHandler().heal_orphan_elements(page)

    capture_message_mock.assert_called_once()
    assert "1 stale" in capture_message_mock.call_args[0][0]
    assert capture_message_mock.call_args.kwargs["level"] == "warning"


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
def test_move_element_relative_to_itself_is_disallowed(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    with pytest.raises(GraphPointReferencePointInvalid):
        ElementService().move_element(
            user,
            page,
            element,
            element.place_in_container,
            element.id,  # the element references itself
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
def test_move_element_into_container_with_null_place_in_container(data_fixture):
    # Regression: moving an element into a container with a null place_in_container
    # (which the move endpoint accepts) must land it in the default "" slot, never a
    # bogus "None" slot key.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    container = ElementService().create_element(
        user, element_type_registry.get("simple_container"), page=page
    )
    heading = data_fixture.create_builder_heading_element(page=page)

    ElementService().move_element(
        user,
        page,
        ElementHandler().get_element_for_update(heading.id),
        None,  # place_in_container
        container.id,
        GraphPointPosition.CHILD,
    )

    page.refresh_from_db(fields=["graph"])
    assert page.graph[str(container.id)]["children"] == {"": [heading.id]}
    assert "None" not in page.graph[str(container.id)]["children"]


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


@pytest.mark.django_db
def test_move_element_cross_page_migrates_container_subtree(data_fixture):
    """
    Moving a container element across pages must migrate its whole subtree (the
    container *and* its descendants) into the target page's graph. Previously the
    cross-graph move only relocated the root point, so the children's page_id was
    updated in the DB but their graph entries never reached the target page,
    leaving the target graph inconsistent.
    """

    user = data_fixture.create_user()
    page1 = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page1.builder)

    container = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("column"),
        page=page1,
    )
    child = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("heading"),
        page=page1,
        reference_element_id=container.id,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )

    assert str(container.id) in page1.graph
    assert str(child.id) in page1.graph

    ElementService().move_element(
        user,
        page2,
        container,
        "",
        None,
        GraphPointPosition.SOUTH,
    )

    page1.refresh_from_db(fields=["graph"])
    page2.refresh_from_db(fields=["graph"])
    container.refresh_from_db(fields=["page"])
    child.refresh_from_db(fields=["page"])

    # Both elements moved to page2 in the DB.
    assert container.page_id == page2.id
    assert child.page_id == page2.id

    # The whole subtree is present in the target graph (not just the container).
    assert str(container.id) in page2.graph
    assert str(child.id) in page2.graph
    assert page2.graph[str(container.id)]["children"]["0"] == [child.id]

    # The source graph no longer references either element.
    assert str(container.id) not in page1.graph
    assert str(child.id) not in page1.graph


@pytest.mark.django_db
def test_move_element_cross_page_moves_its_workflow_action(data_fixture):
    # A workflow action has its own page foreign key. When its element moves to
    # another page (e.g. to/from the shared page) the action must follow, not be
    # left behind on the source page.
    user = data_fixture.create_user()
    page1 = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page1.builder)

    button = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("button"),
        page=page1,
    )
    workflow_action = data_fixture.create_notification_workflow_action(element=button)
    assert workflow_action.page_id == page1.id

    ElementService().move_element(
        user, page2, button, "", None, GraphPointPosition.SOUTH
    )

    workflow_action.refresh_from_db(fields=["page"])
    assert workflow_action.page_id == page2.id


@pytest.mark.django_db
def test_move_element_cross_page_moves_descendant_workflow_actions(data_fixture):
    # Moving a container cross-page must move the workflow actions of its
    # descendants too, since each element in the subtree changes page.
    user = data_fixture.create_user()
    page1 = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page1.builder)

    container = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("column"),
        page=page1,
    )
    child_button = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("button"),
        page=page1,
        reference_element_id=container.id,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )
    workflow_action = data_fixture.create_notification_workflow_action(
        element=child_button
    )
    assert workflow_action.page_id == page1.id

    ElementService().move_element(
        user, page2, container, "", None, GraphPointPosition.SOUTH
    )

    child_button.refresh_from_db(fields=["page"])
    workflow_action.refresh_from_db(fields=["page"])
    assert child_button.page_id == page2.id
    assert workflow_action.page_id == page2.id


@pytest.mark.django_db
def test_move_element_same_page_keeps_workflow_action(data_fixture):
    # A same-page reorder must not touch the workflow action's page.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    button = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("button"),
        page=page,
    )
    workflow_action = data_fixture.create_notification_workflow_action(element=button)

    ElementService().move_element(
        user, page, button, "", first.id, GraphPointPosition.NORTH
    )

    workflow_action.refresh_from_db(fields=["page"])
    assert workflow_action.page_id == page.id


@pytest.mark.django_db
def test_move_element_cross_page_removes_entry_from_source_graph(data_fixture):
    """
    Moving an element from one page to another must remove the element's graph
    entry from the source page's graph.  Before this fix, move() preserved the
    entry (via remove(keep_info=True)) and never cleaned it up, leaving stale
    'X: {}' nodes that broke export/import.
    """

    user = data_fixture.create_user()
    page1 = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page1.builder)

    element1 = data_fixture.create_builder_heading_element(page=page1)
    element2 = data_fixture.create_builder_heading_element(page=page1)
    element3 = data_fixture.create_builder_heading_element(page=page1)

    # Sanity-check initial state: page1 has a clean chain, page2 is empty.
    assert page1.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element2.id]}},
        str(element2.id): {"next": {"": [element3.id]}},
        str(element3.id): {},
    }
    assert page2.graph == {}

    # Move element2 from page1 to page2 (append to end, i.e. null reference + south).
    ElementService().move_element(
        user,
        page2,
        element2,
        element2.place_in_container,
        None,
        GraphPointPosition.SOUTH,
    )

    page1.refresh_from_db(fields=["graph"])
    page2.refresh_from_db(fields=["graph"])

    # element2 must NOT appear as a key in the source graph.
    assert str(element2.id) not in page1.graph, (
        f"Stale entry for element {element2.id} found in source page graph: "
        f"{page1.graph}"
    )

    # Source chain relinked correctly: element1 → element3.
    assert page1.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [element3.id]}},
        str(element3.id): {},
    }

    # element2 is properly placed in the target graph.
    assert page2.graph == {
        "0": element2.id,
        str(element2.id): {},
    }


@pytest.mark.django_db
def test_heal_strips_self_referencing_point(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    # Simulate the real-world corruption: the tail element lists itself as its
    # own `next`. There is no DB<->graph drift, so only the self-reference scan
    # can detect this.
    page.graph[str(e2.id)]["next"] = {"": [e2.id]}
    page.save(update_fields=["graph"])

    patch = ElementHandler().heal_orphan_elements(page)

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [e2.id]}},
        str(e2.id): {},
    }
    # The stripped entry is carried in the patch so clients can shallow-merge.
    assert patch == {str(e2.id): {}}


@pytest.mark.django_db
def test_heal_reattaches_detached_element(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    # Simulate the real-world "3311" corruption: e2 stays keyed in the graph
    # and its row exists, but nothing references it. There is no DB<->graph
    # drift, so only the reachability scan can detect it.
    page.graph = {"0": e1.id, str(e1.id): {}, str(e2.id): {}}
    page.save(update_fields=["graph"])

    patch = ElementHandler().heal_orphan_elements(page)

    page.refresh_from_db(fields=["graph"])
    # e2 is re-attached as the last element of the page.
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [e2.id]}},
        str(e2.id): {},
    }
    assert patch == {str(e1.id): {"next": {"": [e2.id]}}}


@pytest.mark.django_db
def test_heal_reattaches_live_children_of_pruned_stale_container(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    column = element_type_registry.get("column")
    heading = element_type_registry.get("heading")
    container = ElementService().create_element(user, column, page=page)
    child = ElementService().create_element(
        user,
        heading,
        page=page,
        parent_element_id=container.id,
        place_in_container="0",
    )

    # Old code hard-deletes the container row without touching the graph. The
    # stale container is pruned, which detaches its live child — the child must
    # be re-attached in the same heal pass, not become a ghost.
    Element.objects.filter(id=container.id).delete()

    ElementHandler().heal_orphan_elements(page)

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {"0": child.id, str(child.id): {}}
