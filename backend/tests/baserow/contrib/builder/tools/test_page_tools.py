"""The shared page tools."""

import pytest

from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.tools import pages
from baserow.contrib.builder.tools.types import PageChanges, PageCreate
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.tools.errors import ToolInputError, tool_error_message


@pytest.mark.django_db
def test_create_pages_with_a_duplicate_path_in_the_middle_keeps_the_others(builder_ctx):
    builder = builder_ctx["builder"]

    result = pages.create_pages(
        builder_ctx["ctx"],
        builder.id,
        [
            PageCreate(name="One", path="/one"),
            PageCreate(name="Two", path="/one"),
            PageCreate(name="Three", path="/three"),
        ],
    )

    assert [p["name"] for p in result["created_pages"]] == ["One", "Three"]
    assert len(result["errors"]) == 1
    assert result["errors"][0].startswith("Two: The path '/one' is already used by")
    assert not Page.objects.filter(builder=builder, name="Two").exists()


@pytest.mark.django_db
def test_create_pages_returns_no_errors_key_when_all_are_created(builder_ctx):
    result = pages.create_pages(
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        [PageCreate(name="Item", path="/item/:id", visibility="logged-in")],
    )

    assert "errors" not in result
    created = result["created_pages"][0]
    assert created["path_params"] == [{"name": "id", "type": "text"}]
    assert created["visibility"] == "logged-in"


@pytest.mark.django_db
def test_create_pages_in_another_type_of_application_is_not_found(
    data_fixture, builder_ctx
):
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )

    with pytest.raises(ApplicationDoesNotExist):
        pages.create_pages(
            builder_ctx["ctx"], database.id, [PageCreate(name="One", path="/one")]
        )


@pytest.mark.django_db
def test_update_page_to_a_path_in_use_is_refused(builder_ctx):
    pages.create_pages(
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        [PageCreate(name="One", path="/one")],
    )

    with pytest.raises(ToolInputError, match="already used by"):
        pages.update_page(
            builder_ctx["ctx"], builder_ctx["page"].id, PageChanges(path="/one")
        )


@pytest.mark.django_db
def test_update_page_of_another_workspace_is_not_found(data_fixture, builder_ctx):
    other_page = data_fixture.create_builder_page(user=builder_ctx["user"])

    with pytest.raises(PageDoesNotExist) as exc:
        pages.update_page(builder_ctx["ctx"], other_page.id, PageChanges(name="Stolen"))
    assert tool_error_message(exc.value) == "Not found in this workspace."
