from unittest.mock import MagicMock

import pytest

from baserow.contrib.builder.pages.models import Page
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.models import Database
from baserow.contrib.database.views.models import View
from baserow_enterprise.assistant.tools.builder.tools import create_pages
from baserow_enterprise.assistant.tools.builder.types import PageCreate
from baserow_enterprise.assistant.tools.core.tools import create_builders
from baserow_enterprise.assistant.tools.core.types import BuilderItemCreate
from baserow_enterprise.assistant.tools.database.tools import (
    create_views,
    delete_fields,
    update_fields,
)
from baserow_enterprise.assistant.tools.database.types import (
    FieldItemUpdate,
    ViewItemCreate,
)
from baserow_enterprise.assistant.tools.shared import stopped_after

from .utils import create_fake_tool_helpers, make_test_ctx

STOPPED_AFTER_TWO = stopped_after(2, 3)


@pytest.fixture
def ctx(data_fixture) -> MagicMock:
    """A tool context whose run is cancelled while the tool works on item 2 of 3."""

    user = data_fixture.create_user()
    tool_helpers = create_fake_tool_helpers()
    tool_helpers.navigate_to = MagicMock()
    statuses: list[str] = []

    def update_status(status: str) -> None:
        statuses.append(status)
        if len(statuses) == 2:
            tool_helpers.cancel()

    tool_helpers.update_status = update_status
    workspace = data_fixture.create_workspace(user=user)
    return make_test_ctx(user, workspace, tool_helpers=tool_helpers)


@pytest.fixture
def table(data_fixture, ctx):
    database = data_fixture.create_database_application(workspace=ctx.deps.workspace)
    return data_fixture.create_database_table(database=database)


@pytest.fixture
def three_fields(data_fixture, table) -> list[Field]:
    return [data_fixture.create_text_field(table=table, name=f"F{i}") for i in range(3)]


@pytest.mark.django_db
def test_create_builders_keeps_the_builders_finished_before_the_stop(ctx):
    builders = [BuilderItemCreate(name=f"B{i}", type="database") for i in range(3)]

    result = create_builders(ctx, builders=builders, thought="")

    assert [b["name"] for b in result["created_builders"]] == ["B0", "B1"]
    assert result["stopped"] == STOPPED_AFTER_TWO
    assert {d.name for d in Database.objects.all()} == {"B0", "B1"}


@pytest.mark.django_db
def test_update_fields_keeps_the_fields_updated_before_the_stop(ctx, three_fields):
    updates = [FieldItemUpdate(field_id=f.id, name=f"R{f.name}") for f in three_fields]

    result = update_fields(ctx, fields=updates, thought="")

    assert [f["name"] for f in result["updated_fields"]] == ["RF0", "RF1"]
    assert result["stopped"] == STOPPED_AFTER_TWO
    assert [f.name for f in Field.objects.order_by("id")] == ["RF0", "RF1", "F2"]


@pytest.mark.django_db
def test_delete_fields_keeps_the_fields_deleted_before_the_stop(ctx, three_fields):
    ids = [field.id for field in three_fields]

    result = delete_fields(ctx, field_ids=ids, thought="")

    assert result["deleted_field_ids"] == ids[:2]
    assert result["stopped"] == STOPPED_AFTER_TWO
    assert [f.name for f in Field.objects.all()] == ["F2"]


@pytest.mark.django_db
def test_create_views_keeps_the_views_created_before_the_stop(ctx, table):
    views = [ViewItemCreate(name=f"V{i}", type="grid") for i in range(3)]

    result = create_views(ctx, thought="", table_id=table.id, views=views)

    assert [v["name"] for v in result["created_views"]] == ["V0", "V1"]
    assert result["stopped"] == STOPPED_AFTER_TWO
    assert [v.name for v in View.objects.order_by("id")] == ["V0", "V1"]
    ctx.deps.tool_helpers.navigate_to.assert_not_called()


@pytest.mark.django_db
def test_create_pages_keeps_the_pages_created_before_the_stop(data_fixture, ctx):
    builder = data_fixture.create_builder_application(workspace=ctx.deps.workspace)
    pages = [PageCreate(name=f"P{i}", path=f"/p{i}") for i in range(3)]

    result = create_pages(ctx, application_id=builder.id, pages=pages, thought="")

    assert [p["name"] for p in result["created_pages"]] == ["P0", "P1"]
    assert result["stopped"] == STOPPED_AFTER_TWO
    names = Page.objects_without_shared.values_list("name", flat=True)
    assert set(names) == {"P0", "P1"}
