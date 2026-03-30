import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.elements.element_types import (
    ColumnElementType,
)
from baserow.contrib.builder.elements.exceptions import (
    ElementDoesNotExist,
    ElementTypeDeactivated,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element, HeadingElement, TextElement
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.core.graph.types import GraphPointPosition


def pytest_generate_tests(metafunc):
    if "element_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "element_type",
            [pytest.param(e, id=e.type) for e in element_type_registry.get_all()],
        )


@pytest.mark.django_db
def test_create_element(data_fixture, element_type):
    page = data_fixture.create_builder_page()
    shared_page = page.builder.shared_page

    pytest_params = element_type.get_pytest_params(data_fixture)

    if element_type.is_multi_page_element:
        page = shared_page

    prev_is_deactivated = element_type.is_deactivated
    element_type.is_deactivated = lambda x: False

    element = ElementHandler().create_element(element_type, page=page, **pytest_params)

    element_type.is_deactivated = prev_is_deactivated

    assert element.page.id == page.id

    for key, value in pytest_params.items():
        assert getattr(element, key) == value

    assert Element.objects.count() == 1


@pytest.mark.django_db
def test_create_element_and_shared_page(data_fixture):
    page = data_fixture.create_builder_page()
    shared_page = page.builder.shared_page

    regular_element_type = next(
        filter(lambda t: not t.is_multi_page_element, element_type_registry.get_all())
    )

    with pytest.raises(DRFValidationError):
        ElementHandler().create_element(
            regular_element_type,
            page=shared_page,
            **regular_element_type.get_pytest_params(data_fixture),
        )

    shared_element_type = next(
        filter(lambda t: t.is_multi_page_element, element_type_registry.get_all())
    )

    with pytest.raises(DRFValidationError):
        ElementHandler().create_element(
            shared_element_type,
            page=page,
            **regular_element_type.get_pytest_params(data_fixture),
        )


@pytest.mark.django_db
def test_create_element_deactivated_type(data_fixture, mutable_element_type_registry):
    page = data_fixture.create_builder_page()

    regular_element_type = next(
        filter(
            lambda t: not t.is_multi_page_element,
            mutable_element_type_registry.get_all(),
        )
    )

    prev_is_deactivated = regular_element_type.is_deactivated
    regular_element_type.is_deactivated = lambda x: True

    with pytest.raises(ElementTypeDeactivated):
        ElementHandler().create_element(
            regular_element_type,
            page=page,
            **regular_element_type.get_pytest_params(data_fixture),
        )

    regular_element_type.is_deactivated = prev_is_deactivated


@pytest.mark.django_db
def test_get_element(data_fixture):
    element = data_fixture.create_builder_heading_element()
    assert ElementHandler().get_element(element.id).id == element.id


@pytest.mark.django_db
def test_get_element_does_not_exist(data_fixture):
    with pytest.raises(ElementDoesNotExist):
        assert ElementHandler().get_element(0)


@pytest.mark.django_db
def test_get_elements(data_fixture, django_assert_num_queries):
    page = data_fixture.create_builder_page()
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page)

    with django_assert_num_queries(3):
        elements = ElementHandler().get_elements(page)

    assert [e.id for e in elements] == [
        element1.id,
        element2.id,
        element3.id,
    ]

    assert isinstance(elements[0], HeadingElement)
    assert isinstance(elements[1], HeadingElement)
    assert isinstance(elements[2], TextElement)

    # Cache of specific elements is re-used.
    with django_assert_num_queries(0):
        elements = ElementHandler().get_elements(page)
        assert len(elements) == 3

    # We request non-specific records, the cache changes.
    with django_assert_num_queries(1):
        elements = list(ElementHandler().get_elements(page, specific=False))
        assert len(elements) == 3

    # We request non-specific records, the cache is reused.
    with django_assert_num_queries(0):
        elements = list(ElementHandler().get_elements(page, specific=False))
        assert len(elements) == 3

    # We pass in a base queryset, no caching strategy is available.
    base_queryset = Element.objects.filter(page=page, visibility="all")
    with django_assert_num_queries(4):
        elements = ElementHandler().get_elements(page, base_queryset)
        assert len(elements) == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    "specific,expected_query_count",
    [
        [
            True,
            3,
        ],
        [
            False,
            1,
        ],
    ],
)
def test_get_builder_elements(
    data_fixture, django_assert_num_queries, specific, expected_query_count
):
    page = data_fixture.create_builder_page()
    page2 = data_fixture.create_builder_page(builder=page.builder)

    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_text_element(page=page2)

    with django_assert_num_queries(expected_query_count):
        elements = list(
            ElementHandler().get_builder_elements(page.builder, specific=specific)
        )

    assert sorted([e.id for e in elements]) == sorted(
        [
            element1.id,
            element2.id,
        ]
    )


@pytest.mark.django_db
def test_delete_element(data_fixture):
    element = data_fixture.create_builder_heading_element()

    ElementHandler().delete_element(element)

    assert Element.objects.count() == 0


@pytest.mark.django_db
def test_update_element(data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    element_updated = ElementHandler().update_element(element, value="'newValue'")

    assert element_updated.value["formula"] == "'newValue'"


@pytest.mark.django_db
def test_update_element_invalid_values(data_fixture):
    element = data_fixture.create_builder_heading_element()

    element_updated = ElementHandler().update_element(element, nonsense="hello")

    assert not hasattr(element_updated, "nonsense")


@pytest.mark.django_db
def test_creating_element_in_container_starts_its_own_order_sequence(data_fixture):
    page = data_fixture.create_builder_page()
    container = data_fixture.create_builder_column_element(page=page)
    root_element = data_fixture.create_builder_heading_element(page=page)
    element_inside_container_one = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="1",
        reference_element=container,
        position=GraphPointPosition.CHILD,
    )
    element_inside_container_two = data_fixture.create_builder_heading_element(
        page=page,
        place_in_container="1",
        reference_element=container,
        position=GraphPointPosition.CHILD,
    )

    # Irrespective of the order the elements were created, we need to assert that a new
    # order has started inside the container
    assert container.order < root_element.order
    assert element_inside_container_one.order < element_inside_container_two.order
    assert element_inside_container_one.order < root_element.order


@pytest.mark.django_db
def test_before_places_in_container_removed(data_fixture):
    page = data_fixture.create_builder_page()
    column_element = data_fixture.create_builder_column_element(
        page=page, column_amount=3
    )

    element_one = data_fixture.create_builder_heading_element(
        page=page,
        reference_element=column_element,
        position=GraphPointPosition.CHILD,
        place_in_container="2",
    )
    element_two = data_fixture.create_builder_heading_element(
        page=page,
        reference_element=column_element,
        position=GraphPointPosition.CHILD,
        place_in_container="1",
    )

    result = ElementHandler().before_places_in_container_removed(
        column_element, ["1", "2"]
    )
    result_specific = [element.specific for element in result]

    element_one.refresh_from_db()
    element_two.refresh_from_db()

    assert element_one.place_in_container == "0"
    assert element_two.place_in_container == "0"
    assert element_one.order > element_two.order
    assert result_specific == [element_two, element_one]


@pytest.mark.django_db
def test_before_places_in_container_removed_no_change(data_fixture):
    page = data_fixture.create_builder_page()
    column_element = data_fixture.create_builder_column_element(
        page=page, column_amount=3
    )

    element_one = data_fixture.create_builder_heading_element(
        page=page,
        reference_element=column_element,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )
    element_two = data_fixture.create_builder_heading_element(
        page=page,
        reference_element=column_element,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )

    result = ElementHandler().before_places_in_container_removed(
        column_element, ["1", "2"]
    )

    element_one.refresh_from_db()
    element_two.refresh_from_db()

    assert element_one.place_in_container == "0"
    assert element_two.place_in_container == "0"
    assert result == []


@pytest.mark.django_db
def test_duplicate_element_single_element(data_fixture):
    element = data_fixture.create_builder_text_element(value="'test'")

    [element_duplicated] = ElementHandler().duplicate_element(element)["elements"]

    assert element.id != element_duplicated.id
    assert element.value == element_duplicated.value
    assert element.page_id == element_duplicated.page_id
    assert element.order < element_duplicated.order


@pytest.mark.django_db
def test_duplicate_element_multiple_elements(data_fixture):
    container_element = data_fixture.create_builder_column_element(column_amount=12)
    child = data_fixture.create_builder_text_element(
        value="'test'",
        place_in_container="0",
        page=container_element.page,
        reference_element=container_element,
        position=GraphPointPosition.CHILD,
    )
    child_two = data_fixture.create_builder_text_element(
        value="'test2'",
        place_in_container="0",
        page=container_element.page,
        reference_element=container_element,
        position=GraphPointPosition.CHILD,
    )

    [
        container_element_duplicated,
        child_duplicated,
        child_two_duplicated,
    ] = ElementHandler().duplicate_element(container_element)["elements"]

    assert container_element.id != container_element_duplicated.id
    assert container_element.column_amount == container_element_duplicated.column_amount
    assert container_element.page_id == container_element_duplicated.page_id

    assert child.id != child_duplicated.id
    assert child.value == child_duplicated.value
    assert child.page_id == child_duplicated.page_id

    assert child_two.id != child_two_duplicated.id
    assert child_two.value == child_two_duplicated.value
    assert child_two.page_id == child_two_duplicated.page_id

    assert child_duplicated.parent_element_id == container_element_duplicated.id
    assert child_two_duplicated.parent_element_id == container_element_duplicated.id


@pytest.mark.django_db
def test_duplicate_element_deeply_nested(data_fixture):
    container_element = data_fixture.create_builder_column_element(column_amount=12)
    child_first_level = data_fixture.create_builder_column_element(
        reference_element=container_element,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        page=container_element.page,
    )
    child_second_level = data_fixture.create_builder_column_element(
        reference_element=child_first_level,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        page=container_element.page,
    )

    [
        container_element_duplicated,
        child_first_level_duplicated,
        child_second_level_duplicated,
    ] = ElementHandler().duplicate_element(container_element)["elements"]

    assert container_element.id != container_element_duplicated.id
    assert container_element.column_amount == container_element_duplicated.column_amount
    assert container_element.page_id == container_element_duplicated.page_id

    assert child_first_level.id != child_first_level_duplicated.id
    assert child_first_level.page_id == child_first_level_duplicated.page_id

    assert child_second_level.id != child_second_level_duplicated.id
    assert child_second_level.page_id == child_second_level_duplicated.page_id

    assert (
        child_first_level_duplicated.parent_element_id
        == container_element_duplicated.id
    )
    assert (
        child_second_level_duplicated.parent_element_id
        == child_first_level_duplicated.id
    )


@pytest.mark.django_db
def test_duplicate_element_with_workflow_action(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element
    )

    result = ElementHandler().duplicate_element(element)
    [element_duplicated] = result["elements"]
    [duplicated_workflow_action] = result["workflow_actions"]

    assert duplicated_workflow_action.id != workflow_action.id
    assert duplicated_workflow_action.page_id == workflow_action.page_id
    assert duplicated_workflow_action.element_id == element_duplicated.id


@pytest.mark.django_db
def test_get_element_workflow_actions(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element()
    # Order is intentionally switched to check that the result is ordered correctly
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=page, element=element, order=2
    )
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=page, element=element, order=1
    )

    [
        workflow_action_one_returned,
        workflow_action_two_returned,
    ] = ElementHandler().get_element_workflow_actions(element)

    assert workflow_action_one.id == workflow_action_one_returned.id
    assert workflow_action_two.id == workflow_action_two_returned.id


@pytest.mark.django_db
def test_duplicate_element_with_workflow_action_in_container(data_fixture):
    page = data_fixture.create_builder_page()

    container_element = data_fixture.create_builder_column_element(
        column_amount=2, page=page
    )
    first_child = data_fixture.create_builder_button_element(
        page=page,
        place_in_container="0",
        position=GraphPointPosition.CHILD,
        reference_element=container_element,
    )
    second_child = data_fixture.create_builder_button_element(
        page=page,
        place_in_container="1",
        position=GraphPointPosition.CHILD,
        reference_element=container_element,
    )

    workflow_action1 = data_fixture.create_notification_workflow_action(
        page=page, element=first_child
    )
    workflow_action2 = data_fixture.create_notification_workflow_action(
        page=page, element=second_child
    )

    result = ElementHandler().duplicate_element(container_element)

    [duplicated_workflow_action1, duplicated_workflow_action2] = result[
        "workflow_actions"
    ]
    assert duplicated_workflow_action1.page_id == workflow_action1.page_id
    assert duplicated_workflow_action2.page_id == workflow_action2.page_id


@pytest.mark.django_db
def test_get_ancestors(data_fixture, django_assert_num_queries):
    page = data_fixture.create_builder_page()
    great_grandparent = data_fixture.create_builder_column_element(
        column_amount=1, page=page
    )
    grandparent = data_fixture.create_builder_column_element(
        page=page,
        column_amount=3,
        reference_element=great_grandparent,
        position=GraphPointPosition.CHILD,
    )
    parent = data_fixture.create_builder_form_container_element(
        page=page,
        reference_element=grandparent,
        position=GraphPointPosition.CHILD,
    )
    child = data_fixture.create_builder_heading_element(
        page=page,
        reference_element=parent,
        position=GraphPointPosition.CHILD,
    )

    # Query and cache the page's elements for the same context.
    # Query 1: fetch the elements on the page.
    # 2: fetch the specific column types.
    # 3: fetch the specific heading type.
    with django_assert_num_queries(4):
        ancestors = ElementHandler().get_ancestors(child.id, page)

    assert len(ancestors) == 3
    assert ancestors == [parent, grandparent, great_grandparent]

    # Second call is cached, no queries are made.
    # Add a predicate to only return ancestors with a column_amount of 1.
    with django_assert_num_queries(0):
        ancestors = ElementHandler().get_ancestors(
            child.id, page, predicate=lambda el: getattr(el, "column_amount", 0) == 1
        )

    assert len(ancestors) == 1
    assert ancestors == [great_grandparent]


@pytest.mark.django_db
def test_get_first_ancestor_of_type(data_fixture, django_assert_num_queries):
    page = data_fixture.create_builder_page()
    grandparent = data_fixture.create_builder_column_element(column_amount=1, page=page)
    parent = data_fixture.create_builder_form_container_element(
        page=page,
        reference_element=grandparent,
        position=GraphPointPosition.CHILD,
    )
    child = data_fixture.create_builder_choice_element(
        page=page,
        reference_element=parent,
        position=GraphPointPosition.CHILD,
    )

    with django_assert_num_queries(7):
        nearest_column_ancestor = ElementHandler().get_first_ancestor_of_type(
            child.id, ColumnElementType
        )

    assert nearest_column_ancestor.specific == grandparent

    nearest_column_ancestor = ElementHandler().get_first_ancestor_of_type(
        grandparent.id, ColumnElementType
    )

    assert nearest_column_ancestor.specific == grandparent


@pytest.fixture
def property_options_fixture(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Fruit", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Green"],
            ["Blueberry", "Blue"],
            ["Cherry", "Red"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
    )
    table_element = data_fixture.create_builder_table_element(
        page=page, data_source=data_source
    )

    return {
        "table": table,
        "table_element": table_element,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filterable,searchable,sortable",
    [
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
        (False, False, False),
    ],
)
def test_get_element_property_options_returns_expected_options(
    property_options_fixture, filterable, searchable, sortable
):
    table = property_options_fixture["table"]
    filterable_field = table.field_set.get(name="Fruit")

    table_element = property_options_fixture["table_element"]
    table_element.property_options.create(
        schema_property=filterable_field.db_column,
        filterable=filterable,
        searchable=searchable,
        sortable=sortable,
    )

    result = ElementHandler().get_element_property_options(table_element)

    assert result == {
        filterable_field.db_column: {
            "filterable": filterable,
            "searchable": searchable,
            "sortable": sortable,
        },
    }
