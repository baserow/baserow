"""
A bad item in a Kuma builder batch is reported in ``errors`` with a readable message
and leaves nothing behind, while the other items of the call are saved.
"""

from typing import Any

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.services.models import Service
from baserow_enterprise.assistant.tools.builder.tools import (
    add_action_field_mapping,
    create_actions,
    create_data_sources,
    create_display_elements,
    create_pages,
    setup_page,
    update_page,
)
from baserow_enterprise.assistant.tools.builder.types import (
    ActionCreate,
    DataSourceCreate,
    DisplayElementCreate,
    ElementItemCreate,
    PageCreate,
    PageUpdate,
)
from baserow_enterprise.assistant.tools.builder.types.workflow_action import (
    FieldValueMapping,
)
from baserow_enterprise.assistant.tools.shared import ToolInputError

from .utils import make_test_ctx


@pytest.fixture(autouse=True)
def no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid(*args: Any, **kwargs: Any) -> Any:
        def generate(*args: Any, **kwargs: Any) -> dict[str, str]:
            raise AssertionError("These tests use literal values only.")

        return generate

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.get_formula_generator",
        forbid,
    )


@pytest.fixture
def site(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, path="/home")
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, primary=True, name="Name")
    return {
        "user": user,
        "builder": builder,
        "page": page,
        "table": table,
        "name_field": name_field,
        "ctx": make_test_ctx(user, workspace),
    }


@pytest.mark.django_db
def test_create_pages_saves_the_pages_around_a_bad_one(site):
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

    assert [p["name"] for p in result["created_pages"]] == ["First", "Last"]
    assert result["errors"] == [
        "Clash: The page path /home already exists for your builder instance."
    ]
    assert not Page.objects.filter(builder=site["builder"], name="Clash").exists()


@pytest.mark.django_db
def test_update_page_gives_a_readable_path_clash(data_fixture, site):
    other = data_fixture.create_builder_page(builder=site["builder"], path="/other")

    with pytest.raises(ToolInputError, match="The page path /home already exists"):
        update_page(
            site["ctx"], page=PageUpdate(page_id=other.id, path="/home"), thought="t"
        )


@pytest.mark.django_db
def test_update_page_derives_path_params_from_a_new_path(site):
    result = update_page(
        site["ctx"],
        page=PageUpdate(page_id=site["page"].id, path="/home/:id"),
        thought="test",
    )

    assert result["page"]["path"] == "/home/:id"
    site["page"].refresh_from_db()
    assert site["page"].path_params == [{"name": "id", "type": "text"}]


@pytest.mark.django_db
def test_create_data_sources_saves_the_sources_around_a_bad_one(site):
    result = create_data_sources(
        site["ctx"],
        page_id=site["page"].id,
        data_sources=[
            DataSourceCreate(
                ref="a", name="A", type="list_rows", table_id=site["table"].id
            ),
            DataSourceCreate(ref="b", name="B", type="list_rows", table_id=999999),
            DataSourceCreate(
                ref="c", name="C", type="list_rows", table_id=site["table"].id
            ),
        ],
        thought="test",
    )

    assert [ds["ref"] for ds in result["created_data_sources"]] == ["a", "c"]
    assert result["errors"] == ["b: Table with id 999999 not found."]
    assert sorted(
        DataSource.objects.filter(page=site["page"]).values_list("name", flat=True)
    ) == ["A", "C"]


@pytest.mark.django_db
def test_element_failing_after_it_is_written_leaves_nothing(site, monkeypatch):
    post_create = ElementItemCreate.post_create

    def fail_for_bad(self, user, orm_element, page):
        if self.ref == "bad":
            raise ValueError("post create failed")
        return post_create(self, user, orm_element, page)

    monkeypatch.setattr(ElementItemCreate, "post_create", fail_for_bad)

    result = create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[
            DisplayElementCreate(ref="first", type="heading", value="First"),
            DisplayElementCreate(ref="bad", type="heading", value="Bad"),
            DisplayElementCreate(
                ref="orphan", type="heading", value="O", parent_element="nope"
            ),
            DisplayElementCreate(ref="last", type="heading", value="Last"),
        ],
        thought="test",
    )

    assert [e["ref"] for e in result["created_elements"]] == ["first", "last"]
    assert result["errors"][0] == "bad: post create failed"
    assert result["errors"][1].startswith("orphan: Parent ref 'nope' not found.")
    values = [
        e.specific.value["formula"]
        for e in Element.objects.filter(page=site["page"]).order_by("id")
    ]
    assert values == ["'First'", "'Last'"]


@pytest.mark.django_db
def test_action_with_an_invalid_event_leaves_no_service(data_fixture, site):
    button = data_fixture.create_builder_button_element(page=site["page"])
    services = Service.objects.count()

    result = create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[
            ActionCreate(type="notification", element=button.id, title="First"),
            ActionCreate(
                type="create_row",
                element=button.id,
                event="submit",
                table_id=site["table"].id,
                field_values=[
                    FieldValueMapping(field_id=site["name_field"].id, value="x")
                ],
            ),
            ActionCreate(type="notification", element=button.id, title="Last"),
        ],
        thought="test",
    )

    assert len(result["created_actions"]) == 2
    assert len(result["errors"]) == 1
    assert "submit" in result["errors"][0]
    assert BuilderWorkflowAction.objects.filter(page=site["page"]).count() == 2
    assert Service.objects.count() == services


@pytest.mark.django_db
def test_setup_page_saves_the_items_around_a_bad_one(site):
    result = setup_page(
        site["ctx"],
        page_id=site["page"].id,
        data_sources=[
            DataSourceCreate(
                ref="a", name="A", type="list_rows", table_id=site["table"].id
            ),
            DataSourceCreate(ref="b", name="B", type="list_rows", table_id=999999),
        ],
        elements=[
            ElementItemCreate(ref="h", type="heading", value="Title"),
            ElementItemCreate(
                ref="x", type="heading", value="X", parent_element="nope"
            ),
            ElementItemCreate(ref="btn", type="button", value="Go"),
        ],
        actions=[
            ActionCreate(type="notification", element="btn", title="Hi"),
            ActionCreate(type="notification", element="missing", title="Hi"),
        ],
        thought="test",
    )

    assert DataSource.objects.filter(page=site["page"]).count() == 1
    assert Element.objects.filter(page=site["page"]).count() == 2
    assert BuilderWorkflowAction.objects.filter(page=site["page"]).count() == 1
    errors = " ".join(result["errors"])
    assert "Table with id 999999 not found." in errors
    assert "Parent ref 'nope' not found." in errors
    assert "Element ref 'missing' not found." in errors


@pytest.mark.django_db
def test_field_mapping_on_a_notification_is_a_readable_error(data_fixture, site):
    button = data_fixture.create_builder_button_element(page=site["page"])
    action = data_fixture.create_notification_workflow_action(
        page=site["page"], element=button, event="click"
    )

    with pytest.raises(ToolInputError, match="Cannot add field mappings"):
        add_action_field_mapping(
            site["ctx"],
            action_id=action.id,
            field_id=site["name_field"].id,
            value_formula="'x'",
            thought="test",
        )
