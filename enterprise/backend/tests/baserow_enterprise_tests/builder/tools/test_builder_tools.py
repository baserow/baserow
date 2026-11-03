"""The shared tools that create and update application builders (B18)."""

import pytest

from baserow.contrib.builder.models import Builder
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.integrations.models import Integration
from baserow.core.tools.errors import ToolInputError, tool_error_message
from baserow_enterprise.builder.tools import applications
from baserow_enterprise.builder.tools.themes import builder_uses_theme
from baserow_enterprise.builder.tools.types import BuilderCreate


def test_builder_create_has_no_type():
    assert "type" not in BuilderCreate.model_fields


@pytest.mark.django_db
def test_create_builders_makes_builders_with_their_theme_and_integration(builder_ctx):
    result = applications.create_builders(
        builder_ctx["ctx"],
        [BuilderCreate(name="Portal", theme="eclipse"), BuilderCreate(name="Plain")],
    )

    assert "errors" not in result
    assert [b["name"] for b in result["created_builders"]] == ["Portal", "Plain"]
    portal = Builder.objects.get(id=result["created_builders"][0]["id"])
    assert portal.workspace_id == builder_ctx["workspace"].id
    assert result["created_builders"][0]["type"] == "builder"
    assert builder_uses_theme(portal, "eclipse")
    plain = Builder.objects.get(id=result["created_builders"][1]["id"])
    assert builder_uses_theme(plain, "baserow")
    integration = Integration.objects.get(application=portal)
    assert integration.get_type().type == "local_baserow"


@pytest.mark.django_db
def test_update_builder_changes_the_name_and_login_page(builder_ctx):
    builder = builder_ctx["builder"]
    page = builder_ctx["page"]

    result = applications.update_builder(
        builder_ctx["ctx"], builder.id, name="Renamed", login_page_id=page.id
    )

    assert result == {
        "updated_builder": {
            "id": builder.id,
            "name": "Renamed",
            "login_page_id": page.id,
        }
    }
    builder.refresh_from_db()
    assert builder.name == "Renamed"
    assert builder.login_page_id == page.id


@pytest.mark.django_db
def test_update_builder_refuses_a_login_page_of_another_builder(
    data_fixture, builder_ctx
):
    builder = builder_ctx["builder"]
    other = data_fixture.create_builder_application(workspace=builder_ctx["workspace"])
    other_page = data_fixture.create_builder_page(builder=other)

    with pytest.raises(ToolInputError, match="doesn't exist"):
        applications.update_builder(
            builder_ctx["ctx"], builder.id, login_page_id=other_page.id
        )

    builder.refresh_from_db()
    assert builder.login_page_id is None


@pytest.mark.django_db
def test_update_builder_with_an_id_of_another_application_type_is_not_found(
    data_fixture, builder_ctx
):
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )

    with pytest.raises(ApplicationDoesNotExist) as exc:
        applications.update_builder(builder_ctx["ctx"], database.id, name="Renamed")
    assert tool_error_message(exc.value) == "Not found in this workspace."
    database.refresh_from_db()
    assert database.name != "Renamed"
