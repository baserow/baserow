"""
Every shared builder write tool refuses a workspace viewer, whose role has no
builder write operation, and changes nothing.
"""

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.exceptions import PermissionException
from baserow.core.tools import ToolContext
from baserow.core.user_sources.models import UserSource
from baserow_enterprise.builder.tools import (
    actions,
    applications,
    data_sources,
    elements,
    pages,
    themes,
    user_sources,
)
from baserow_enterprise.builder.tools.types import (
    ActionChanges,
    ActionCreate,
    CollectionElementCreate,
    DataSourceChanges,
    DataSourceCreate,
    DisplayElementCreate,
    ElementEdits,
    ElementItemCreate,
    ElementMove,
    ElementStyleChanges,
    FormElementCreate,
    LayoutElementCreate,
    PageChanges,
    PageCreate,
)
from baserow_enterprise.builder.tools.types.user_source import UserSourceSetup
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture
def viewer_site(data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles):
    owner = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, name="Products"
    )
    button = data_fixture.create_builder_button_element(page=page, value="'Go'")
    notification = data_fixture.create_notification_workflow_action(
        page=page, element=button, event="click"
    )
    create_row = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=button, event="click"
    )
    create_row.service.specific.table = table
    create_row.service.specific.save()
    columns = data_fixture.create_builder_table_element(
        page=page, data_source=data_source
    )

    viewer = enterprise_data_fixture.create_user()
    enterprise_data_fixture.create_user_workspace(
        user=viewer, workspace=workspace, permissions="NO_ACCESS"
    )
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(
        viewer, workspace, role=Role.objects.get(uid="VIEWER")
    )
    return {
        "ctx": ToolContext(user=viewer, workspace=workspace),
        "builder": builder,
        "page": page,
        "database": database,
        "table": table,
        "name": name,
        "data_source": data_source,
        "button": button,
        "notification": notification,
        "create_row": create_row,
        "columns": columns,
    }


WRITE_TOOLS = {
    "create_builder": lambda s: applications.create_builder(s["ctx"], "Portal"),
    "update_builder": lambda s: applications.update_builder(
        s["ctx"], s["builder"].id, name="Renamed"
    ),
    "set_theme": lambda s: themes.set_theme(s["ctx"], s["builder"].id, "eclipse"),
    "create_pages": lambda s: pages.create_pages(
        s["ctx"], s["builder"].id, [PageCreate(name="One", path="/one")]
    ),
    "update_page": lambda s: pages.update_page(
        s["ctx"], s["page"].id, PageChanges(name="Renamed")
    ),
    "setup_page": lambda s: pages.setup_page(
        s["ctx"],
        s["page"].id,
        elements=[ElementItemCreate(ref="h", type="heading", value="Title")],
    ),
    "create_data_sources": lambda s: data_sources.create_data_sources(
        s["ctx"],
        s["page"].id,
        [DataSourceCreate(ref="a", name="A", type="list_rows", table_id=s["table"].id)],
    ),
    "update_data_source": lambda s: data_sources.update_data_source(
        s["ctx"], s["data_source"].id, DataSourceChanges(name="Renamed")
    ),
    "create_display_elements": lambda s: elements.create_display_elements(
        s["ctx"],
        s["page"].id,
        [DisplayElementCreate(ref="h", type="heading", value="Title", level=1)],
    ),
    "create_layout_elements": lambda s: elements.create_layout_elements(
        s["ctx"], s["page"].id, [LayoutElementCreate(ref="top", type="header")]
    ),
    "create_form_elements": lambda s: elements.create_form_elements(
        s["ctx"], s["page"].id, [FormElementCreate(ref="f", type="form_container")]
    ),
    "create_collection_elements": lambda s: elements.create_collection_elements(
        s["ctx"],
        s["page"].id,
        [
            CollectionElementCreate(
                ref="r", type="repeat", data_source=s["data_source"].id
            )
        ],
    ),
    "update_element": lambda s: elements.update_element(
        s["ctx"], s["button"].id, ElementEdits(value="Stop")
    ),
    "update_element_style": lambda s: elements.update_element_style(
        s["ctx"], s["button"].id, ElementStyleChanges(padding=1)
    ),
    "move_elements": lambda s: elements.move_elements(
        s["ctx"], [ElementMove(element_id=s["button"].id)]
    ),
    "delete_element_items": lambda s: elements.delete_element_items(
        s["ctx"],
        s["columns"].id,
        table_columns=[str(s["columns"].fields.order_by("order").first().uid)],
    ),
    "create_element_actions": lambda s: actions.create_element_actions(
        s["ctx"],
        s["page"].id,
        [ActionCreate(type="notification", element=s["button"].id, title="Hi")],
    ),
    "update_element_action": lambda s: actions.update_element_action(
        s["ctx"], s["notification"].id, ActionChanges(title="Bye")
    ),
    "add_element_action_field_mapping": (
        lambda s: actions.add_element_action_field_mapping(
            s["ctx"], s["create_row"].id, s["name"].id, "'Fixed'"
        )
    ),
    "setup_user_source": lambda s: user_sources.setup_user_source(
        s["ctx"],
        s["builder"].id,
        UserSourceSetup(name="Users", database_id=s["database"].id),
    ),
}


def _state(site):
    builder = Builder.objects.get(id=site["builder"].id)
    return {
        "builders": Builder.objects.count(),
        "builder_name": builder.name,
        "login_page": builder.login_page_id,
        # The graph holds where each element sits.
        "pages": list(
            Page.objects.order_by("id").values_list("id", "name", "path", "graph")
        ),
        "data_sources": list(
            DataSource.objects.order_by("id").values_list("id", "name")
        ),
        "elements": list(Element.objects.order_by("id").values_list("id", flat=True)),
        "button": site["button"].__class__.objects.get(id=site["button"].id).value,
        "columns": site["columns"]
        .__class__.objects.get(id=site["columns"].id)
        .fields.count(),
        "actions": BuilderWorkflowAction.objects.count(),
        "user_sources": UserSource.objects.count(),
        "tables": site["database"].table_set.count(),
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("tool", sorted(WRITE_TOOLS))
def test_every_builder_write_tool_refuses_a_viewer(viewer_site, tool):
    before = _state(viewer_site)

    with pytest.raises(PermissionException):
        WRITE_TOOLS[tool](viewer_site)

    assert _state(viewer_site) == before
