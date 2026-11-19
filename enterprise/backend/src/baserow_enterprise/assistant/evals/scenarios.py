from __future__ import annotations

from uuid import uuid4

from django.contrib.auth.models import AbstractUser

from faker import Faker

from baserow.contrib.builder.models import Builder
from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table
from baserow.core.cache import local_cache
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
from baserow_premium.license.cache import invalidate_cached_instance_wide_licenses
from baserow_premium.license.models import License


class EvalFixtures(Fixtures):
    """The fixtures of one eval case."""

    _added_licence_id: int | None = None

    def enable_enterprise(self) -> None:
        """
        Give the instance the enterprise licence of the enterprise tests until the
        case ends. The eval database runs with the debug licence key, which that
        licence is signed for.
        """

        from baserow_enterprise_tests.enterprise_fixtures import EnterpriseFixtures

        had_licence = License.objects.filter(
            cached_untrusted_instance_wide=True
        ).exists()
        licence = EnterpriseFixtures().enable_enterprise()
        if not had_licence:
            self._added_licence_id = licence.id
        invalidate_cached_instance_wide_licenses()

    def remove_added_licence(self) -> None:
        """Remove the licence this case added, so no later case runs with it."""

        if self._added_licence_id is None:
            return
        License.objects.filter(id=self._added_licence_id).delete()
        self._added_licence_id = None
        invalidate_cached_instance_wide_licenses()
        local_cache.clear()

    def create_user(self, **kwargs) -> AbstractUser:
        # Faker's uniqueness cache belongs to one fixture instance, while eval
        # users persist across scenarios and runs in the same database.
        kwargs.setdefault("email", f"kuma-eval-{uuid4().hex}@example.com")
        return super().create_user(**kwargs)

    def create_select_option(
        self, user: AbstractUser | None = None, **kwargs
    ) -> SelectOption:
        # Kuma shows stored colors as they are, so a fake name would reach the model.
        kwargs.setdefault("color", "blue")
        return super().create_select_option(user=user, **kwargs)


def make_fixtures() -> EvalFixtures:
    """Build a ``Fixtures`` instance usable outside pytest, e.g. by scenario builders."""

    return EvalFixtures(Faker())


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
