"""The shared tools that create and update application builders (B18)."""

import pydantic
import pytest

from baserow.contrib.automation.models import Automation
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database
from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.integrations.models import Integration
from baserow.core.integrations.service import IntegrationService
from baserow.core.service import CoreService
from baserow.core.tools.errors import ToolInputError, tool_error_message
from baserow_enterprise.builder.tools import applications
from baserow_enterprise.builder.tools.themes import builder_uses_theme


@pytest.mark.django_db
def test_create_builder_makes_one_builder_with_its_theme_and_integration(builder_ctx):
    result = applications.create_builder(builder_ctx["ctx"], "Portal", theme="eclipse")

    portal = Builder.objects.get(id=result["created_builder"]["id"])
    assert result == {"created_builder": {"id": portal.id, "name": "Portal"}}
    assert portal.workspace_id == builder_ctx["workspace"].id
    assert builder_uses_theme(portal, "eclipse")
    integration = Integration.objects.get(application=portal)
    assert integration.get_type().type == "local_baserow"


@pytest.mark.django_db
def test_create_builder_defaults_to_the_baserow_theme(builder_ctx):
    result = applications.create_builder(builder_ctx["ctx"], "Plain")

    plain = Builder.objects.get(id=result["created_builder"]["id"])
    assert builder_uses_theme(plain, "baserow")


@pytest.mark.django_db
def test_create_builder_creates_only_a_builder(builder_ctx):
    applications.create_builder(builder_ctx["ctx"], "Portal")

    workspace = builder_ctx["workspace"]
    assert not Automation.objects.filter(workspace=workspace).exists()
    assert not Dashboard.objects.filter(workspace=workspace).exists()
    assert not Database.objects.filter(workspace=workspace, name="Portal").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["", "x" * 161])
def test_create_builder_rejects_an_invalid_name(builder_ctx, name):
    with pytest.raises(pydantic.ValidationError):
        applications.create_builder(builder_ctx["ctx"], name)

    assert not Builder.objects.filter(name=name).exists()


@pytest.mark.django_db
def test_create_builder_keeps_nothing_when_denied(builder_ctx, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(IntegrationService, "create_integration", denied)

    with pytest.raises(PermissionException):
        applications.create_builder(builder_ctx["ctx"], "Portal")

    assert not Builder.objects.filter(name="Portal").exists()


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
        },
        "changed": True,
    }
    builder.refresh_from_db()
    assert builder.name == "Renamed"
    assert builder.login_page_id == page.id


@pytest.mark.django_db
def test_update_builder_with_nothing_to_change_reports_no_change(builder_ctx):
    builder = builder_ctx["builder"]

    result = applications.update_builder(
        builder_ctx["ctx"], builder.id, name=builder.name
    )

    assert result["changed"] is False


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


@pytest.mark.django_db
def test_update_builder_reports_a_hidden_builder_as_not_found(builder_ctx, monkeypatch):
    builder = Builder.objects.create(
        workspace=builder_ctx["workspace"], name="Portal", order=1
    )

    def deny(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(CoreService, "get_application", deny)

    with pytest.raises(ApplicationDoesNotExist):
        applications.get_builder_in_workspace(builder_ctx["ctx"], builder.id)
