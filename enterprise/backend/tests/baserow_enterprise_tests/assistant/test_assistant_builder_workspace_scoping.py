"""
Kuma's builder tools only reach objects in the chat's workspace, and only the
elements and data sources of the page a tool works on or of its builder's shared
page. Any other ID gets the same error as a missing one, and nothing changes.
"""

from typing import Any

from django.db import transaction

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.exceptions import PermissionDenied
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.assistant.tools.builder import helpers
from baserow_enterprise.assistant.tools.builder.types import (
    ActionCreate,
    DataSourceCreate,
    DataSourceSort,
    DataSourceUpdate,
    ElementItemCreate,
    ElementMove,
    ElementStyleUpdate,
    ElementUpdate,
    MenuItemCreate,
    PageUpdate,
)
from baserow_enterprise.assistant.tools.core.tools import update_builder
from baserow_enterprise.assistant.tools.core.types import BuilderUpdate
from baserow_enterprise.assistant.tools.shared import ToolInputError

from .utils import make_test_ctx


@pytest.fixture
def two_workspaces(data_fixture):
    user = data_fixture.create_user()
    here = data_fixture.create_workspace(user=user)
    other = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=other)
    page = data_fixture.create_builder_page(builder=builder)
    heading = data_fixture.create_builder_heading_element(page=page, value="'Title'")
    data_fixture.create_builder_heading_element(page=page)
    button = data_fixture.create_builder_button_element(page=page)
    column = data_fixture.create_builder_column_element(page=page, column_amount=2)
    action = data_fixture.create_notification_workflow_action(
        page=page, element=button, event="click"
    )
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, name="Original"
    )
    here_page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=here)
    )
    here_button = data_fixture.create_builder_button_element(page=here_page)
    return {
        "user": user,
        "here": here,
        "other": other,
        "page": page,
        "heading": heading,
        "action": action,
        "column": column,
        "data_source": data_source,
        "here_page": here_page,
        "here_button": here_button,
    }


def _snapshot(element: Element) -> dict[str, Any]:
    element = Element.objects.get(id=element.id).specific
    return {
        "value": element.value,
        "styles": element.styles,
        "page_graph": Page.objects.get(id=element.page_id).graph,
    }


@pytest.mark.django_db
def test_page_from_other_workspace_is_not_found(two_workspaces):
    w = two_workspaces

    with pytest.raises(ToolInputError, match=f"Page with ID {w['page'].id} not found"):
        helpers.get_page(w["user"], w["here"], w["page"].id)
    assert helpers.get_page(w["user"], w["other"], w["page"].id) == w["page"]


@pytest.mark.django_db
def test_page_of_trashed_builder_is_not_found(two_workspaces):
    w = two_workspaces
    builder = w["page"].builder
    TrashHandler.trash(w["user"], w["other"], builder, builder)

    with pytest.raises(ToolInputError, match=f"Page with ID {w['page'].id} not found"):
        helpers.get_page(w["user"], w["other"], w["page"].id)


@pytest.mark.django_db
def test_page_from_other_workspace_is_not_updated(two_workspaces):
    w = two_workspaces
    page = w["page"]

    with pytest.raises(ToolInputError, match=f"Page with ID {page.id} not found"):
        helpers.update_page(
            w["user"], w["here"], PageUpdate(page_id=page.id, name="Changed")
        )

    assert Page.objects.get(id=page.id).name == page.name


@pytest.mark.django_db
def test_element_from_other_workspace_is_not_changed(two_workspaces):
    w = two_workspaces
    user, heading, here_page = w["user"], w["heading"], w["here_page"]
    before = _snapshot(heading)

    with transaction.atomic():
        with pytest.raises(ToolInputError, match="not found"):
            helpers.update_element(
                user, here_page, ElementUpdate(element_id=heading.id, value="Changed")
            )
        with pytest.raises(ToolInputError, match="not found"):
            helpers.update_element_style(
                user,
                here_page,
                ElementStyleUpdate(element_id=heading.id, padding=40),
            )
        with pytest.raises(ToolInputError, match="not found"):
            helpers.move_element(user, here_page, ElementMove(element_id=heading.id))

    assert _snapshot(heading) == before


@pytest.mark.django_db
def test_element_on_another_page_of_the_workspace_is_not_changed(
    data_fixture, two_workspaces
):
    w = two_workspaces
    user, heading = w["user"], w["heading"]
    sibling_page = data_fixture.create_builder_page(builder=w["page"].builder)
    before = _snapshot(heading)

    with pytest.raises(ToolInputError, match="not found"):
        helpers.update_element(
            user, sibling_page, ElementUpdate(element_id=heading.id, value="Changed")
        )

    assert _snapshot(heading) == before


@pytest.mark.django_db
def test_element_on_the_shared_page_is_reachable_from_a_page(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=workspace)
    )
    shared_heading = data_fixture.create_builder_heading_element(
        page=page.builder.shared_page, value="'Title'"
    )

    helpers.update_element(
        user, page, ElementUpdate(element_id=shared_heading.id, value="Changed")
    )

    assert Element.objects.get(id=shared_heading.id).specific.value["formula"] == (
        "'Changed'"
    )


@pytest.mark.django_db
def test_create_element_rejects_ids_from_other_workspace(data_fixture, two_workspaces):
    w = two_workspaces
    user, here_page = w["user"], w["here_page"]
    count = Element.objects.filter(page=here_page).count()

    with pytest.raises(ToolInputError, match="Parent element"):
        helpers.create_element(
            user,
            here_page,
            ElementItemCreate(
                ref="h", type="heading", value="Hi", parent_element=w["column"].id
            ),
            {},
            {},
        )
    with pytest.raises(ToolInputError, match="Before element"):
        helpers.create_element(
            user,
            here_page,
            ElementItemCreate(ref="h", type="heading", value="Hi"),
            {},
            {},
            before_id=w["heading"].id,
        )
    with pytest.raises(ToolInputError, match="Data source"):
        helpers.create_element(
            user,
            here_page,
            ElementItemCreate(
                ref="t", type="table", data_source=w["data_source"].id, fields=[]
            ),
            {},
            {},
        )
    with pytest.raises(ToolInputError, match=f"Page with ID {w['page'].id}"):
        helpers.create_element(
            user,
            here_page,
            ElementItemCreate(
                ref="l",
                type="link",
                value="Go",
                navigation_type="page",
                navigate_to_page_id=w["page"].id,
            ),
            {},
            {},
        )

    assert Element.objects.filter(page=here_page).count() == count


@pytest.mark.django_db
def test_data_source_from_other_workspace_is_not_changed(two_workspaces):
    w = two_workspaces
    user, data_source = w["user"], w["data_source"]
    update = DataSourceUpdate(data_source_id=data_source.id, name="Changed")

    with pytest.raises(ToolInputError, match="not found"):
        helpers.update_data_source(user, w["here_page"], update)
    assert DataSource.objects.get(id=data_source.id).name == "Original"

    helpers.update_data_source(user, w["page"], update)
    assert DataSource.objects.get(id=data_source.id).name == "Changed"


@pytest.mark.django_db
def test_action_from_other_workspace_is_not_found(two_workspaces):
    w = two_workspaces
    action = w["action"]

    with pytest.raises(ToolInputError, match=f"Action with ID {action.id} not found"):
        helpers.add_field_mapping_to_action(w["user"], w["here"], action.id, 1, "'x'")


@pytest.mark.django_db
def test_field_mapping_reaches_an_action_without_element(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=workspace)
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table, fields, _ = data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["a"]], database=database
    )
    action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=None, event="click", user=user
    )
    action.service.table = table
    action.service.save()

    result = helpers.add_field_mapping_to_action(
        user, workspace, action.id, fields[0].id, "'x'"
    )

    assert result["status"] == "created"


@pytest.mark.django_db
def test_create_action_rejects_ids_from_other_workspace(two_workspaces):
    w = two_workspaces
    user, here_page, here_button = w["user"], w["here_page"], w["here_button"]

    with pytest.raises(ToolInputError, match="Data source"):
        helpers.create_workflow_action(
            user,
            here_page,
            ActionCreate(
                type="refresh_data_source",
                element=here_button.id,
                data_source=w["data_source"].id,
            ),
            {},
            {},
        )
    with pytest.raises(ToolInputError, match=f"Page with ID {w['page'].id}"):
        helpers.create_workflow_action(
            user,
            here_page,
            ActionCreate(
                type="open_page",
                element=here_button.id,
                navigate_to_page_id=w["page"].id,
            ),
            {},
            {},
        )

    assert not BuilderWorkflowAction.objects.filter(page=here_page).exists()


@pytest.mark.django_db
def test_no_op_updates_still_check_permissions(
    data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    workspace = data_fixture.create_workspace()
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=workspace)
    )
    heading = data_fixture.create_builder_heading_element(page=page)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    user = enterprise_data_fixture.create_user()
    enterprise_data_fixture.create_user_workspace(
        user=user, workspace=workspace, permissions="NO_ACCESS"
    )

    with pytest.raises(PermissionDenied):
        helpers.update_data_source(
            user, page, DataSourceUpdate(data_source_id=data_source.id)
        )
    with pytest.raises(PermissionDenied):
        helpers.update_element_style(
            user, page, ElementStyleUpdate(element_id=heading.id)
        )
    with transaction.atomic(), pytest.raises(PermissionDenied):
        helpers.move_element(user, page, ElementMove(element_id=heading.id))


@pytest.mark.django_db
def test_update_builder_from_other_workspace_is_not_found(two_workspaces):
    w = two_workspaces
    builder = w["page"].builder
    ctx = make_test_ctx(w["user"], w["here"])

    with pytest.raises(ToolInputError, match=f"Application with ID {builder.id}"):
        update_builder(
            ctx,
            builder_id=builder.id,
            update=BuilderUpdate(name="Changed"),
            thought="rename",
        )

    builder.refresh_from_db()
    assert builder.name != "Changed"


@pytest.mark.django_db
def test_update_builder_refuses_a_login_page_outside_the_builder(
    data_fixture, two_workspaces
):
    w = two_workspaces
    builder = w["here_page"].builder
    sibling = data_fixture.create_builder_application(workspace=w["here"])
    other_builder_page = data_fixture.create_builder_page(builder=sibling)
    ctx = make_test_ctx(w["user"], w["here"])

    for page_id in [
        other_builder_page.id,
        w["page"].id,
        builder.shared_page.id,
        999999,
    ]:
        with pytest.raises(ToolInputError, match=f"Page with ID {page_id}"):
            update_builder(
                ctx,
                builder_id=builder.id,
                update=BuilderUpdate(login_page_id=page_id),
                thought="login page",
            )

    builder.refresh_from_db()
    assert builder.login_page_id is None


@pytest.mark.django_db
def test_header_refuses_pages_of_another_builder(data_fixture, two_workspaces):
    w = two_workspaces
    user, here_page = w["user"], w["here_page"]
    sibling_page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=w["here"])
    )
    shared_page = here_page.builder.shared_page
    count = Element.objects.filter(page=shared_page).count()

    for header in [
        ElementItemCreate(
            ref="h", type="header", share_type="only", page_ids=[sibling_page.id]
        ),
        ElementItemCreate(
            ref="h", type="header", share_type="only", page_ids=[w["page"].id]
        ),
        ElementItemCreate(
            ref="h",
            type="header",
            menu_items=[MenuItemCreate(name="Away", page_id=sibling_page.id)],
        ),
    ]:
        with pytest.raises(ToolInputError, match="Page with ID"):
            helpers.create_element(user, here_page, header, {}, {})

    assert Element.objects.filter(page=shared_page).count() == count


@pytest.mark.django_db
def test_header_keeps_pages_of_its_builder(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=workspace)
    )

    header, _, _ = helpers.create_element(
        user,
        page,
        ElementItemCreate(
            ref="h",
            type="header",
            share_type="only",
            page_ids=[page.id],
            menu_items=[MenuItemCreate(name="Home", page_id=page.id)],
        ),
        {},
        {},
    )

    assert list(header.specific.pages.values_list("id", flat=True)) == [page.id]


@pytest.fixture
def two_tables(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=workspace)
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, primary=True)
    other_table = data_fixture.create_database_table(database=database)
    other_field = data_fixture.create_text_field(table=other_table, primary=True)
    return {
        "user": user,
        "page": page,
        "table": table,
        "field": field,
        "view": data_fixture.create_grid_view(table=table),
        "other_field": other_field,
        "other_view": data_fixture.create_grid_view(table=other_table),
        "integration": helpers.get_local_baserow_integration(user, page.builder),
    }


@pytest.mark.django_db
def test_data_source_refuses_a_sort_field_of_another_table(two_tables):
    t = two_tables

    with pytest.raises(
        ToolInputError,
        match=f"Field with ID {t['other_field'].id} .* Use get_tables_schema ",
    ):
        helpers.create_data_source(
            t["user"],
            t["page"],
            DataSourceCreate(
                ref="ds",
                name="Rows",
                type="list_rows",
                table_id=t["table"].id,
                sortings=[DataSourceSort(field_id=t["other_field"].id)],
            ),
            t["integration"],
        )

    data_source, _ = helpers.create_data_source(
        t["user"],
        t["page"],
        DataSourceCreate(
            ref="ds",
            name="Rows",
            type="list_rows",
            table_id=t["table"].id,
            sortings=[DataSourceSort(field_id=t["field"].id)],
        ),
        t["integration"],
    )
    assert list(
        data_source.service.specific.service_sorts.values_list("field_id", flat=True)
    ) == [t["field"].id]


@pytest.mark.django_db
def test_data_source_refuses_a_view_of_another_table(two_tables):
    t = two_tables
    view_id = t["other_view"].id

    with pytest.raises(ToolInputError, match=f"View with ID {view_id}"):
        helpers.create_data_source(
            t["user"],
            t["page"],
            DataSourceCreate(
                ref="ds",
                name="Rows",
                type="list_rows",
                table_id=t["table"].id,
                view_id=view_id,
            ),
            t["integration"],
        )

    data_source, _ = helpers.create_data_source(
        t["user"],
        t["page"],
        DataSourceCreate(
            ref="ds",
            name="Rows",
            type="list_rows",
            table_id=t["table"].id,
            view_id=t["view"].id,
        ),
        t["integration"],
    )
    with pytest.raises(ToolInputError, match=f"View with ID {view_id}"):
        helpers.update_data_source(
            t["user"],
            t["page"],
            DataSourceUpdate(data_source_id=data_source.id, view_id=view_id),
        )

    assert data_source.service.specific.view_id == t["view"].id
    assert DataSource.objects.get(id=data_source.id).service.specific.view_id == (
        t["view"].id
    )
