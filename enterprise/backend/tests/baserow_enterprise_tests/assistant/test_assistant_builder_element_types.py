"""Kuma's builder tools treat each element type through its hooks."""

from typing import Any, NamedTuple
from unittest.mock import MagicMock

import pytest

from baserow.contrib.builder.elements.operations import UpdateElementOperationType
from baserow.contrib.builder.pages.models import Page
from baserow.core.exceptions import PermissionDenied
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.tools.builder.assistant_element_types import (
    TableAssistantElementType,
)
from baserow_enterprise.assistant.tools.builder.registries import (
    PreparedElementUpdate,
    assistant_element_type_registry,
)
from baserow_enterprise.assistant.tools.builder.tools import update_element
from baserow_enterprise.assistant.tools.builder.types import ElementUpdate
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

from .utils import make_test_ctx


class SeededPage(NamedTuple):
    ctx: MagicMock
    page: Page


@pytest.fixture
def seeded(data_fixture: Fixtures) -> SeededPage:
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    return SeededPage(make_test_ctx(user, workspace), page)


def test_a_table_gets_the_registered_table_type() -> None:
    table = assistant_element_type_registry.get_for("table")

    assert isinstance(table, TableAssistantElementType)
    assert table is assistant_element_type_registry.get("table")
    assert table.property_aliases == {
        "add_table_columns": "fields",
        "update_table_columns": "fields",
        "reorder_table_columns": "fields",
        "remove_table_columns": "fields",
    }


@pytest.mark.django_db
def test_an_element_type_without_hooks_gets_hooks_that_do_nothing(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    heading = data_fixture.create_builder_heading_element(
        page=seeded.page, value="'Title'"
    )
    update = ElementUpdate(element_id=heading.id, value="New title")

    hooks = assistant_element_type_registry.get_for("heading")

    assert hooks.prepare_update(seeded.ctx.deps.user, heading, update) == (
        PreparedElementUpdate(kwargs={}, result={})
    )
    assert hooks.updated_result(heading, update) == {}
    assert hooks.item_details(heading) == {}
    assert hooks.property_aliases == {}


def test_an_element_type_without_hooks_keeps_its_property_aliases() -> None:
    assert assistant_element_type_registry.get_for("link").property_aliases == {
        "link_variant": "variant",
        "link_target": "target",
    }


@pytest.mark.django_db
def test_the_unsupported_properties_guidance_lists_a_links_aliased_properties(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    link = data_fixture.create_builder_link_element(page=seeded.page)

    with pytest.raises(ToolInputError) as raised:
        update_element(
            seeded.ctx,
            page_id=seeded.page.id,
            element=ElementUpdate(element_id=link.id, level=2),
            thought="Change the link.",
        )

    message = str(raised.value)
    assert message.startswith(
        "Unsupported properties for link: level. No changes were applied."
    )
    supported = message.split("Supported properties include: ")[1].rstrip(".")
    assert {"link_variant", "link_target"} <= set(supported.split(", "))


@pytest.mark.django_db
def test_a_heading_update_reports_no_table_keys(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    heading = data_fixture.create_builder_heading_element(
        page=seeded.page, value="'Title'"
    )

    result = update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate(element_id=heading.id, value="New title"),
        thought="Rename the heading.",
    )

    assert result == {
        "status": "ok",
        "element_id": heading.id,
        "element_type": "heading",
        "updated_fields": ["value"],
    }
    heading.refresh_from_db()
    assert heading.value["formula"] == "'New title'"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "properties",
    [
        {"value": "New title", "link_target": "blank"},
        {"value": "$formula: a changed heading"},
    ],
    ids=["unsupported-property", "formula"],
)
def test_a_user_who_cannot_update_a_heading_gets_the_permission_error_first(
    seeded: SeededPage,
    data_fixture: Fixtures,
    enterprise_data_fixture: Any,
    enable_enterprise: None,
    synced_roles: None,
    properties: dict[str, str],
) -> None:
    workspace = seeded.ctx.deps.workspace
    heading = data_fixture.create_builder_heading_element(
        page=seeded.page, value="'Title'"
    )
    user = enterprise_data_fixture.create_user()
    enterprise_data_fixture.create_user_workspace(
        user=user, workspace=workspace, permissions="NO_ACCESS"
    )
    role = Role.objects.create(
        name="Read elements without updates", workspace=workspace
    )
    role.operations.set(
        Role.objects.get(uid="BUILDER").operations.exclude(
            name=UpdateElementOperationType.type
        )
    )
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(
        user, workspace, role=role, scope=seeded.page.builder.application_ptr
    )

    with pytest.raises(PermissionDenied):
        update_element(
            make_test_ctx(user, workspace),
            page_id=seeded.page.id,
            element=ElementUpdate.model_validate(
                {"element_id": heading.id, **properties}
            ),
            thought="Change the heading.",
        )

    heading.refresh_from_db()
    assert heading.value["formula"] == "'Title'"
