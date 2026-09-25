from __future__ import annotations

from django.contrib.auth.models import AbstractUser

from faker import Faker

from baserow.contrib.builder.models import Builder
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table
from baserow.core.models import Workspace
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.registry import register_scenario
from baserow_enterprise.assistant.evals.types import EvalScenario
from baserow_enterprise.assistant.types import (
    ApplicationUIContext,
    TableUIContext,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)


def make_fixtures() -> Fixtures:
    """Build a ``Fixtures`` instance usable outside pytest, e.g. by scenario builders."""

    return Fixtures(Faker())


def build_database_ui_context(
    user: AbstractUser,
    workspace: Workspace,
    database: Database | None = None,
    table: Table | None = None,
) -> str:
    """Build a UIContext for a database/table, formatted as JSON."""

    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        database=ApplicationUIContext(id=str(database.id), name=database.name)
        if database
        else None,
        table=TableUIContext(id=table.id, name=table.name) if table else None,
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


def build_builder_ui_context(
    user: AbstractUser,
    workspace: Workspace,
    builder: Builder | None = None,
) -> str:
    """Build a UIContext for an application builder, setting the application slot."""

    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        application=ApplicationUIContext(id=str(builder.id), name=builder.name)
        if builder
        else None,
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


def build_workspace_ui_context(user: AbstractUser, workspace: Workspace) -> str:
    """Build a UIContext scoped to just the workspace, with no app open."""

    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


@register_scenario("empty-workspace")
def _empty_workspace_scenario(fx: Fixtures) -> EvalScenario:
    """Bare workspace: the default starting state for UI-added examples."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_workspace_ui_context(user, workspace),
    )
