import uuid
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.builder.action_scopes import (
    PageActionScopeType,
    SharedPageActionScopeType,
)
from baserow.contrib.builder.elements.actions import (
    CreateElementActionType,
    DeleteElementActionType,
    DuplicateElementActionType,
    MoveElementActionType,
    UpdateElementActionType,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.trash_types import PageTrashableItemType
from baserow.contrib.builder.workflow_actions.actions import (
    CreateBuilderWorkflowActionActionType,
)
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.signals import (
    workflow_action_created,
    workflow_action_deleted,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
)
from baserow.core.graph.types import GraphPointPosition
from baserow.core.trash.handler import TrashHandler


def _next_id(page, element_id):
    # The graph handler is cached per page id within the test process and mutated
    # in place by the action's do/undo/redo, so reading it back reflects the
    # current state without re-fetching from the database. Returns the id of the
    # element directly after ``element_id`` on the default edge.
    return page.get_graph().graph[str(element_id)]["next"][""][0]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    heading_type = element_type_registry.get("heading")

    element = CreateElementActionType.do(user, heading_type, page, {})

    assert Element.objects.filter(id=element.id).exists()
    assert str(element.id) in page.get_graph().graph

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db(fields=["trashed"])
    assert element.trashed
    assert str(element.id) not in page.get_graph().graph

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed
    assert str(element.id) in page.get_graph().graph


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page, level=1)

    UpdateElementActionType.do(user, element, {"level": 3})

    element.refresh_from_db()
    assert element.level == 3

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db()
    assert element.level == 1

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db()
    assert element.level == 3


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    DeleteElementActionType.do(user, element)

    element.refresh_from_db(fields=["trashed"])
    assert element.trashed
    assert str(element.id) not in page.get_graph().graph

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed
    assert str(element.id) in page.get_graph().graph

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db(fields=["trashed"])
    assert element.trashed


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    result = DuplicateElementActionType.do(user, element)
    duplicated = result["elements"][0]

    assert duplicated.id != element.id
    assert Element.objects.filter(id=duplicated.id).exists()

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    duplicated.refresh_from_db(fields=["trashed"])
    assert duplicated.trashed
    # The source element is untouched.
    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    duplicated.refresh_from_db(fields=["trashed"])
    assert not duplicated.trashed


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    second = data_fixture.create_builder_heading_element(page=page)
    third = data_fixture.create_builder_heading_element(page=page)

    # Initial chain: first -> second -> third.
    assert _next_id(page, first.id) == second.id

    # Move third to be south of first: first -> third -> second.
    MoveElementActionType.do(
        user,
        third,
        page,
        "",
        first.id,
        "south",
    )

    assert _next_id(page, first.id) == third.id

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    assert _next_id(page, first.id) == second.id

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    assert _next_id(page, first.id) == third.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_head_element_undo_restores_it_as_head(data_fixture):
    # Moving the first (head/root) element away and then undoing must put it back
    # at the head — not append it to the bottom of the page. The head's captured
    # position is `(None, "north", "")`, whose move-inverse re-roots it.
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    second = data_fixture.create_builder_heading_element(page=page)
    third = data_fixture.create_builder_heading_element(page=page)

    # Initial chain: first (head) -> second -> third.
    assert page.get_graph().graph["0"] == first.id

    # Move the head element to just before the last one: second -> first -> third.
    MoveElementActionType.do(user, first, page, "", third.id, "north")

    assert page.get_graph().graph["0"] == second.id
    assert _next_id(page, second.id) == first.id
    assert _next_id(page, first.id) == third.id

    # Undo restores `first` as the head and the original chain.
    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    assert page.get_graph().graph["0"] == first.id
    assert _next_id(page, first.id) == second.id
    assert _next_id(page, second.id) == third.id

    # Redo re-applies the move.
    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    assert page.get_graph().graph["0"] == second.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_element_out_of_container_undo_restores_head_child_position(
    data_fixture,
):
    # Regression: moving the *first* child out of a container and then undoing
    # must put it back as the head of the container's child chain (before its
    # former sibling), not appended after it. get_position reports "child" only
    # for the head child, so the move undo replays insert(..., "child", ...),
    # which must therefore prepend.
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)

    container = ElementService().create_element(
        user, element_type_registry.get("simple_container"), page=page
    )
    child1 = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.CHILD,
        reference_element=container,
        place_in_container="",
    )
    child2 = data_fixture.create_builder_heading_element(
        page=page,
        position=GraphPointPosition.SOUTH,
        reference_element=child1,
        place_in_container="",
    )
    outside = data_fixture.create_builder_heading_element(page=page)

    # The container's "" slot chain is child1 -> child2.
    assert page.get_graph().graph[str(container.id)]["children"][""] == [child1.id]
    assert _next_id(page, child1.id) == child2.id

    # Move child1 (the head child) out, to be south of the outside element.
    MoveElementActionType.do(
        user,
        ElementHandler().get_element_for_update(child1.id),
        page,
        "",
        outside.id,
        GraphPointPosition.SOUTH,
    )

    graph = page.get_graph().graph
    assert graph[str(container.id)]["children"][""] == [child2.id]
    assert _next_id(page, outside.id) == child1.id

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    # child1 is back as the *head* child, before child2 — not appended after it.
    graph = page.get_graph().graph
    assert graph[str(container.id)]["children"][""] == [child1.id]
    assert _next_id(page, child1.id) == child2.id

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    graph = page.get_graph().graph
    assert graph[str(container.id)]["children"][""] == [child2.id]
    assert _next_id(page, outside.id) == child1.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_shared_element_action_is_scoped_to_shared_page(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    content_page = data_fixture.create_builder_page(builder=builder)
    shared_page = builder.shared_page
    header_type = element_type_registry.get("header")

    # A header element lives on the builder's shared page.
    element = CreateElementActionType.do(user, header_type, shared_page, {})
    assert Element.objects.filter(id=element.id).exists()

    # The content page scope alone must NOT undo a shared element's action.
    ActionHandler.undo(user, [PageActionScopeType.value(content_page.id)], session_id)
    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed

    # The shared page scope (sent by the editor alongside the content page) does.
    ActionHandler.undo(
        user, [SharedPageActionScopeType.value(shared_page.id)], session_id
    )
    element.refresh_from_db(fields=["trashed"])
    assert element.trashed

    ActionHandler.redo(
        user, [SharedPageActionScopeType.value(shared_page.id)], session_id
    )
    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed


def _undo(user, page, session_id):
    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)


def _redo(user, page, session_id):
    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_table_element_fields_action_undo_redo(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_builder_table_element(
        page=page,
        fields=[
            {"name": "Id", "type": "text", "config": {"value": "''"}},
            {"name": "Name", "type": "text", "config": {"value": "'Name'"}},
        ],
    )
    columns = [
        {
            "uid": str(column.uid),
            "name": column.name,
            "type": column.type,
            "config": dict(column.config),
            "styles": column.styles,
        }
        for column in table.fields.order_by("order")
    ]
    uids = [column["uid"] for column in columns]
    columns[0]["config"]["value"] = BaserowFormulaObject.create(
        "get('current_record.id')", mode=BASEROW_FORMULA_MODE_ADVANCED
    )

    def column_values():
        return [
            (str(column.uid), column.name, column.config["value"]["formula"])
            for column in table.fields.order_by("order")
        ]

    UpdateElementActionType.do(user, table, {"fields": columns})
    generated = [
        (uids[0], "Id", "get('current_record.id')"),
        (uids[1], "Name", "'Name'"),
    ]
    assert column_values() == generated

    _undo(user, page, session_id)
    assert column_values() == [(uids[0], "Id", "''"), (uids[1], "Name", "'Name'")]

    _redo(user, page, session_id)
    assert column_values() == generated


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_collection_element_property_options_action_undo_redo(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_builder_table_element(page=page)
    UpdateElementActionType.do(
        user,
        table,
        {"property_options": [{"schema_property": "field_1", "sortable": True}]},
    )
    UpdateElementActionType.do(
        user,
        table,
        {"property_options": [{"schema_property": "field_2", "filterable": True}]},
    )

    def options():
        return list(
            table.property_options.order_by("schema_property").values_list(
                "schema_property", "sortable", "filterable"
            )
        )

    assert options() == [("field_2", False, True)]

    _undo(user, page, session_id)
    assert options() == [("field_1", True, False)]

    _redo(user, page, session_id)
    assert options() == [("field_2", False, True)]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_menu_element_items_action_undo_redo(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    menu = data_fixture.create_builder_menu_element(page=page)
    home, about, team = (str(uuid.uuid4()) for _ in range(3))

    def link(uid, name, **kwargs):
        return {"uid": uid, "type": "link", "variant": "link", "name": name, **kwargs}

    UpdateElementActionType.do(
        user, menu, {"menu_items": [link(home, "Home"), link(about, "About")]}
    )
    UpdateElementActionType.do(
        user,
        menu,
        {"menu_items": [link(about, "About us", children=[link(team, "Team")])]},
    )

    def items():
        return sorted(
            (
                str(item.uid),
                item.name,
                item.parent_menu_item and str(item.parent_menu_item.uid),
            )
            for item in menu.menu_items.all()
        )

    changed = sorted([(about, "About us", None), (team, "Team", about)])
    assert items() == changed

    _undo(user, page, session_id)
    assert items() == sorted([(home, "Home", None), (about, "About", None)])

    _redo(user, page, session_id)
    assert items() == changed


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_choice_element_options_action_undo_redo(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    choice = data_fixture.create_builder_choice_element(page=page)
    UpdateElementActionType.do(user, choice, {"options": [{"value": "a", "name": "A"}]})
    UpdateElementActionType.do(
        user,
        choice,
        {"options": [{"value": "b", "name": "B"}, {"value": None, "name": "C"}]},
    )

    def options():
        return list(
            choice.choiceelementoption_set.order_by("id").values_list("value", "name")
        )

    assert options() == [("b", "B"), (None, "C")]

    _undo(user, page, session_id)
    assert options() == [("a", "A")]

    _redo(user, page, session_id)
    assert options() == [("b", "B"), (None, "C")]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "create,values,related_tables",
    [
        (
            "create_builder_table_element",
            {"items_per_page": 5},
            ["builder_collectionfield", "builder_collectionelementpropertyoptions"],
        ),
        (
            "create_builder_menu_element",
            {"alignment": "right"},
            ["builder_menuitemelement"],
        ),
        (
            "create_builder_choice_element",
            {"label": "'L'"},
            ["builder_choiceelementoption"],
        ),
    ],
)
def test_update_element_action_only_snapshots_the_updated_values(
    data_fixture, create, values, related_tables
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = getattr(data_fixture, create)(page=page)

    with CaptureQueriesContext(connection) as queries:
        UpdateElementActionType.do(user, element, values)

    related_queries = [
        query["sql"]
        for query in queries.captured_queries
        if any(f'"{table}' in query["sql"] for table in related_tables)
    ]
    assert related_queries == []


def _remove_page(user, page, how):
    if how == "trash":
        TrashHandler.trash(user, page.builder.workspace, page.builder, page)
    else:
        page.delete()


def _restore_page(user, page):
    TrashHandler.restore_item(user, PageTrashableItemType.type, page.id)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_of_menu_items_drops_a_link_to_a_deleted_page(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    other_page = data_fixture.create_builder_page(builder=page.builder)
    menu = data_fixture.create_builder_menu_element(page=page)
    uid = str(uuid.uuid4())

    def link(name, **kwargs):
        return {"uid": uid, "type": "link", "variant": "link", "name": name, **kwargs}

    UpdateElementActionType.do(
        user,
        menu,
        {
            "menu_items": [
                link(
                    "Other",
                    navigation_type="page",
                    navigate_to_page_id=other_page.id,
                )
            ]
        },
    )
    UpdateElementActionType.do(user, menu, {"menu_items": [link("Renamed")]})
    _remove_page(user, other_page, "delete")

    _undo(user, page, session_id)

    item = menu.menu_items.get()
    assert (item.name, item.navigate_to_page_id) == ("Other", None)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_of_menu_items_keeps_a_link_to_a_trashed_page(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    other_page = data_fixture.create_builder_page(builder=page.builder)
    menu = data_fixture.create_builder_menu_element(page=page)
    uid = str(uuid.uuid4())

    def link(name, **kwargs):
        return {"uid": uid, "type": "link", "variant": "link", "name": name, **kwargs}

    UpdateElementActionType.do(
        user,
        menu,
        {
            "menu_items": [
                link(
                    "Other",
                    navigation_type="page",
                    navigate_to_page_id=other_page.id,
                )
            ]
        },
    )
    UpdateElementActionType.do(user, menu, {"menu_items": [link("Renamed")]})
    _remove_page(user, other_page, "trash")

    _undo(user, page, session_id)
    _restore_page(user, other_page)

    item = menu.menu_items.get()
    assert (item.name, item.navigate_to_page_id) == ("Other", other_page.id)


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("how", ["trash", "delete"])
def test_undo_of_table_fields_with_a_link_to_a_removed_page(data_fixture, how):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    other_page = data_fixture.create_builder_page(builder=page.builder)
    table = data_fixture.create_builder_table_element(
        page=page,
        fields=[
            {
                "name": "Open",
                "type": "link",
                "config": {
                    "navigation_type": "page",
                    "navigate_to_page_id": other_page.id,
                },
            }
        ],
    )
    column = table.fields.get()
    UpdateElementActionType.do(
        user,
        table,
        {
            "fields": [
                {
                    "uid": str(column.uid),
                    "name": "Renamed",
                    "type": "link",
                    "config": column.config,
                }
            ]
        },
    )
    _remove_page(user, other_page, how)

    _undo(user, page, session_id)

    column = table.fields.get()
    assert column.name == "Open"
    # A trashed page can still be restored.
    expected = other_page.id if how == "trash" else None
    assert column.config["navigate_to_page_id"] == expected


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_of_a_link_with_page_parameters_to_a_trashed_page(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    item_page = data_fixture.create_builder_page(
        builder=page.builder,
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    link = data_fixture.create_builder_link_element(
        page=page,
        navigation_type="page",
        navigate_to_page_id=item_page.id,
        page_parameters=[{"name": "id", "value": "'1'"}],
    )
    UpdateElementActionType.do(
        user,
        link,
        {
            "navigation_type": "custom",
            "navigate_to_page_id": None,
            "page_parameters": [],
        },
    )
    _remove_page(user, item_page, "trash")

    _undo(user, page, session_id)
    _restore_page(user, item_page)

    link.refresh_from_db()
    assert link.navigation_type == "page"
    assert link.navigate_to_page_id == item_page.id
    assert [param["name"] for param in link.page_parameters] == ["id"]


@pytest.mark.django_db
def test_only_links_to_deleted_pages_are_cleared(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    kept = data_fixture.create_builder_page(builder=page.builder)
    trashed = data_fixture.create_builder_page(builder=page.builder)
    deleted = data_fixture.create_builder_page(builder=page.builder)
    deleted_id = deleted.id
    _remove_page(user, trashed, "trash")
    _remove_page(user, deleted, "delete")

    values = PageHandler().without_links_to_deleted_pages(
        page.builder,
        {
            "fields": [
                {"config": {"navigate_to_page_id": str(kept.id)}},
                {"config": {"navigate_to_page_id": trashed.id}},
                {"config": {"navigate_to_page_id": deleted_id}},
                {
                    "config": {
                        "navigation_type": "custom",
                        "navigate_to_page_id": deleted_id,
                    }
                },
            ]
        },
    )

    assert [field["config"]["navigate_to_page_id"] for field in values["fields"]] == [
        str(kept.id),
        trashed.id,
        None,
        deleted_id,
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_and_redo_round_trip_click_actions_a_replay_trashes(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_builder_table_element(page=page, fields=[])
    UpdateElementActionType.do(user, table, {"fields": [_button_column()]})
    [go] = table.fields.all()
    # A collaborator's click action, outside this user's undo history.
    action = data_fixture.create_notification_workflow_action(
        page=page, element=table, event=f"{go.uid}_click"
    )

    _undo(user, page, session_id)  # The column, and so its click action, goes.
    assert not _live(action)

    _redo(user, page, session_id)
    assert _live(action)

    _undo(user, page, session_id)
    assert not _live(action)

    _redo(user, page, session_id)
    assert _live(action)


def _button_column(name="Go"):
    return {"name": name, "type": "button", "config": {"label": "'Go'"}}


def _columns(table):
    return table.get_type().export_prepared_values(table, {"fields"})["fields"]


def _live(workflow_action):
    return BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_of_removing_a_button_column_brings_back_its_click_actions(
    data_fixture,
):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_builder_table_element(
        page=page, fields=[_button_column(), _button_column("Kept")]
    )
    go, kept = list(table.fields.order_by("order"))
    removed_action = data_fixture.create_notification_workflow_action(
        page=page, element=table, event=f"{go.uid}_click"
    )
    kept_action = data_fixture.create_notification_workflow_action(
        page=page, element=table, event=f"{kept.uid}_click"
    )

    with (
        patch.object(workflow_action_deleted, "send") as deleted,
        patch.object(workflow_action_created, "send") as created,
    ):
        UpdateElementActionType.do(user, table, {"fields": _columns(table)[1:]})
        assert not _live(removed_action)
        assert _live(kept_action)
        assert [c.kwargs["workflow_action_id"] for c in deleted.call_args_list] == [
            removed_action.id
        ]

        _undo(user, page, session_id)
        assert [str(c.uid) for c in table.fields.order_by("order")] == [
            str(go.uid),
            str(kept.uid),
        ]
        assert _live(removed_action)
        assert [c.kwargs["workflow_action"].id for c in created.call_args_list] == [
            removed_action.id
        ]

        _redo(user, page, session_id)
        assert not _live(removed_action)
        assert _live(kept_action)

        _undo(user, page, session_id)
        assert _live(removed_action)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_of_removing_a_menu_button_brings_back_its_click_actions(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    menu = data_fixture.create_builder_menu_element(page=page)
    uid = str(uuid.uuid4())
    button = {"uid": uid, "type": "button", "variant": "link", "name": "Go"}
    UpdateElementActionType.do(user, menu, {"menu_items": [button]})
    action = data_fixture.create_notification_workflow_action(
        page=page, element=menu, event=f"{uid}_click"
    )

    UpdateElementActionType.do(user, menu, {"menu_items": []})
    assert not _live(action)

    _undo(user, page, session_id)
    assert [str(item.uid) for item in menu.menu_items.all()] == [uid]
    assert _live(action)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_column_add_keeps_its_trashed_click_action_for_redo(
    data_fixture,
):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_builder_table_element(page=page, fields=[])
    UpdateElementActionType.do(user, table, {"fields": [_button_column()]})
    [go] = table.fields.all()
    action = CreateBuilderWorkflowActionActionType.do(
        user,
        builder_workflow_action_type_registry.get("notification"),
        page,
        element_id=table.id,
        event=f"{go.uid}_click",
    )

    _undo(user, page, session_id)  # The click action is trashed.
    _undo(user, page, session_id)  # The column is removed.
    assert BuilderWorkflowAction.trash.filter(id=action.id).exists()

    _redo(user, page, session_id)
    _redo(user, page, session_id)
    assert _live(action)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_element_action_undo_redo_of_style_and_visibility(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)
    values = {
        "styles": {"typography": {"heading_1_text_color": "red"}},
        "style_padding_top": 42,
        "css_classes": "big",
        "visibility": "logged-in",
        "role_type": "disallow_all_except",
        "roles": ["Admin"],
    }
    before = {key: getattr(element, key) for key in values}

    def saved():
        element.refresh_from_db()
        return {key: getattr(element, key) for key in values}

    UpdateElementActionType.do(user, element, values)
    assert saved() == values

    _undo(user, page, session_id)
    assert saved() == before

    _redo(user, page, session_id)
    assert saved() == values
