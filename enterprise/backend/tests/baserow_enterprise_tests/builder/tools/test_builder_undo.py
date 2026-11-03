"""
Kuma's builder writes are recorded as actions, so undo restores the earlier state.
"""

import uuid
from typing import Any

from django.db import transaction

import pytest

from baserow.api.sessions import set_client_undo_redo_action_group_id
from baserow.contrib.builder.action_scopes import (
    PageActionScopeType,
)
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.services.models import Service
from baserow.core.user_sources.models import UserSource
from baserow_enterprise.assistant.tools.builder.tools import (
    create_pages,
)
from baserow_enterprise.assistant.tools.builder.tools import (
    update_data_source as update_data_source_tool,
)
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.builder.elements.models import AuthFormElement
from baserow_enterprise.builder.tools import helpers
from baserow_enterprise.builder.tools.types import (
    ActionCreate,
    DataSourceCreate,
    DataSourceUpdate,
    PageCreate,
    PageUpdate,
)
from baserow_enterprise.builder.tools.types.workflow_action import FieldValueMapping
from baserow_enterprise_tests.assistant.utils import make_test_ctx


@pytest.fixture
def site(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, path="/home")
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True, name="Name")
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    return {
        "user": user,
        "session_id": session_id,
        "workspace": workspace,
        "builder": builder,
        "page": page,
        "table": table,
        "integration": integration,
        "ctx": make_test_ctx(user, workspace),
    }


def undo(site: dict[str, Any], *pages: Page) -> None:
    scopes = [
        ApplicationActionScopeType.value(site["builder"].id),
        PageActionScopeType.value(site["page"].id),
        *(PageActionScopeType.value(page.id) for page in pages),
    ]
    with transaction.atomic():
        ActionHandler.undo(site["user"], scopes, site["session_id"])


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_page_is_undoable(site):
    page = helpers.create_page(
        site["user"], site["builder"], PageCreate(name="New", path="/new")
    )

    undo(site)

    assert not Page.objects.filter(id=page.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_page_keeps_the_clash_error(site):
    with pytest.raises(ToolInputError, match="The path '/home' is already used"):
        helpers.create_page(
            site["user"], site["builder"], PageCreate(name="Clash", path="/home")
        )

    assert not Action.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_page_is_undoable_and_derives_path_params(site):
    original_params = site["page"].path_params
    page = helpers.update_page(
        site["user"],
        site["workspace"],
        PageUpdate(page_id=site["page"].id, name="Renamed", path="/home/:id"),
    )

    assert page.path_params == [{"name": "id", "type": "text"}]

    undo(site)

    page.refresh_from_db()
    assert page.name != "Renamed"
    assert page.path == "/home"
    assert page.path_params == original_params


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_data_source_is_undoable(site):
    data_source, data_source_id = helpers.create_data_source(
        site["user"],
        site["page"],
        DataSourceCreate(
            ref="a", name="A", type="list_rows", table_id=site["table"].id
        ),
        site["integration"],
    )

    undo(site)

    assert not DataSource.objects.filter(id=data_source_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_data_source_with_a_bad_sort_leaves_nothing(site):
    other_table = site["table"].database.table_set.create(name="Other", order=2)
    from baserow.contrib.database.fields.models import TextField

    other_field = TextField.objects.create(table=other_table, name="X", order=1)

    with pytest.raises(ToolInputError):
        helpers.create_data_source(
            site["user"],
            site["page"],
            DataSourceCreate(
                ref="a",
                name="A",
                type="list_rows",
                table_id=site["table"].id,
                sortings=[{"field_id": other_field.id, "direction": "ASC"}],
            ),
            site["integration"],
        )

    assert not DataSource.objects.exists()
    assert not Action.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_data_source_is_undoable(data_fixture, site):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'", name="Before"
    )

    helpers.update_data_source(
        site["user"],
        site["page"],
        DataSourceUpdate(data_source_id=data_source.id, name="After"),
    )
    data_source.refresh_from_db()
    assert data_source.name == "After"

    undo(site)

    data_source.refresh_from_db()
    assert data_source.name == "Before"


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_update_data_source_with_a_formula_is_undone_in_one_step(
    data_fixture, site, monkeypatch
):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'", name="Before"
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.get_formula_generator",
        lambda *args: (
            lambda formulas, context: {
                field: "get('page_parameter.id')" for field in formulas
            }
        ),
    )
    set_client_undo_redo_action_group_id(site["user"], str(uuid.uuid4()))

    result = update_data_source_tool(
        site["ctx"],
        page_id=site["page"].id,
        data_source=DataSourceUpdate(
            data_source_id=data_source.id,
            name="After",
            row_id="$formula: the id page parameter",
        ),
        thought="test",
    )

    assert result["status"] == "ok"
    data_source.refresh_from_db()
    assert data_source.name == "After"
    assert data_source.service.specific.row_id["formula"] == "get('page_parameter.id')"

    undo(site)

    data_source.refresh_from_db()
    assert data_source.name == "Before"
    assert data_source.service.specific.row_id["formula"] == "'1'"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_workflow_action_is_undoable(data_fixture, site):
    button = data_fixture.create_builder_button_element(page=site["page"])

    _, action_id = helpers.create_workflow_action(
        site["user"],
        site["page"],
        ActionCreate(type="notification", element=button.id, title="Hi"),
        {},
        {},
        site["integration"],
    )
    assert BuilderWorkflowAction.objects.filter(id=action_id).exists()

    undo(site)

    assert not BuilderWorkflowAction.objects.filter(id=action_id).exists()
    assert BuilderWorkflowAction.trash.filter(id=action_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_workflow_action_with_an_invalid_event_leaves_no_service(
    data_fixture, site
):
    table_element = data_fixture.create_builder_table_element(
        page=site["page"],
        fields=[
            {"name": "Edit", "type": "button", "config": {}},
            {"name": "Edit", "type": "button", "config": {}},
        ],
    )
    name_field = site["table"].field_set.first()
    services = Service.objects.count()

    with pytest.raises(ToolInputError, match="does not identify one button column"):
        helpers.create_workflow_action(
            site["user"],
            site["page"],
            ActionCreate(
                type="create_row",
                element=table_element.id,
                event="Edit_click",
                table_id=site["table"].id,
                field_values=[
                    FieldValueMapping(field_id=str(name_field.id), value="'x'")
                ],
            ),
            {},
            {},
            site["integration"],
        )

    assert Service.objects.count() == services
    assert not BuilderWorkflowAction.objects.exists()
    assert not Action.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_user_source_is_undoable(data_fixture, site):
    table = site["table"]
    field_map = {
        "name": table.field_set.first(),
        "email": data_fixture.create_email_field(table=table, name="Email"),
        "password": data_fixture.create_password_field(table=table, name="Password"),
    }

    user_source = helpers.create_user_source(
        site["user"], site["builder"], "Members", table, field_map, site["integration"]
    )
    assert UserSource.objects.filter(id=user_source.id).exists()

    undo(site)

    assert not UserSource.objects.filter(id=user_source.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_login_page_is_undoable(data_fixture, site):
    table = site["table"]
    field_map = {
        "name": table.field_set.first(),
        "email": data_fixture.create_email_field(table=table, name="Email"),
        "password": data_fixture.create_password_field(table=table, name="Password"),
    }
    user_source = helpers.create_user_source(
        site["user"], site["builder"], "Members", table, field_map, site["integration"]
    )

    page = helpers.create_login_page(site["user"], site["builder"], user_source.id)
    assert page.path == "/login"
    assert site["builder"].login_page_id == page.id
    assert Element.objects.filter(page=page).count() == 1

    undo(site, page)
    assert not Element.objects.filter(page=page).exists()

    undo(site, page)
    assert not Page.objects.filter(id=page.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_failed_batch_item_leaves_no_action_row(site):
    result = create_pages(
        site["ctx"],
        application_id=site["builder"].id,
        pages=[
            PageCreate(name="First", path="/first"),
            PageCreate(name="Clash", path="/home"),
            PageCreate(name="Last", path="/last"),
        ],
        thought="test",
    )

    assert len(result["errors"]) == 1
    assert Action.objects.filter(type="create_page").count() == 2


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_setup_creates_a_new_login_page_after_the_old_one_is_undone(data_fixture, site):
    from baserow_enterprise.assistant.tools.builder.tools import setup_user_source
    from baserow_enterprise.builder.tools.types.user_source import UserSourceSetup

    table = site["table"]
    data_fixture.create_email_field(table=table, name="Email")
    data_fixture.create_password_field(table=table, name="Password")
    setup = UserSourceSetup(name="Members", table_id=table.id)

    first = setup_user_source(
        site["ctx"], application_id=site["builder"].id, setup=setup, thought="t"
    )
    first_page = Page.objects.get(id=first["login_page_id"])
    undo(site, first_page)
    undo(site, first_page)
    assert not Page.objects.filter(id=first_page.id).exists()

    result = setup_user_source(
        site["ctx"], application_id=site["builder"].id, setup=setup, thought="t"
    )

    site["builder"].refresh_from_db()
    assert result["login_page_id"] != first_page.id
    assert site["builder"].login_page_id == result["login_page_id"]
    login_page = Page.objects.get(id=result["login_page_id"])
    assert AuthFormElement.objects.filter(page=login_page).exists()
