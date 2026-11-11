"""
Application builder user source tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.service import UserSourceService

from . import helpers
from .lookups import get_builder_in_workspace, workspace_pages
from .types import PageItem
from .types.user_source import UserSourceSetup


def _local_baserow_user_source_on(
    user: AbstractUser, builder: Builder, table_id: int | None
) -> UserSource | None:
    """The builder's Local Baserow user source on a table, if it has one."""

    if table_id is None:
        return None
    for user_source in UserSourceService().get_user_sources(user, builder):
        if (
            user_source.get_type().type == "local_baserow"
            and user_source.specific.table_id == table_id
        ):
            return user_source.specific
    return None


def _raise_unless_password_login_works(user_source: UserSource) -> None:
    """
    :raises ToolInputError: When members couldn't log in with a password through
        the user source, so a login form for it would only fail.
    """

    from baserow_enterprise.integrations.local_baserow.models import (
        LocalBaserowPasswordAppAuthProvider,
    )

    provider = LocalBaserowPasswordAppAuthProvider.objects.filter(
        user_source=user_source.id
    ).first()
    if (
        user_source.get_type().is_configured(user_source)
        and provider is not None
        and provider.get_type().is_configured(provider)
    ):
        return
    raise ToolInputError(
        f"User source {user_source.id} on that table isn't set up for password "
        "login, so nobody could log in through it. Finish its settings in the editor, "
        "or use another table. No changes were applied."
    )


def _user_source_item(user_source: UserSource, table_id: int) -> dict[str, Any]:
    return {"id": user_source.id, "name": user_source.name, "table_id": table_id}


def setup_user_source(
    ctx: ToolContext,
    builder_id: Annotated[
        int, Field(description="The ID of the application builder, from list_builders.")
    ],
    setup: Annotated[
        UserSourceSetup,
        Field(description="The users table, or the database to create it in."),
    ],
) -> dict[str, Any]:
    """
    Let people log in to an application builder: set up a user source with password
    login on a table of users, and a login page with an auth_form. This also writes
    to a database: it can create a Users table with example rows, or add a Password
    field to an existing table.

    With database_id, a new Users table is created with example users, one per role.
    With table_id, the table needs an email field and a name or primary field; a
    password field is added if it has none, unless another type of field is already
    named Password, which is refused. A user source already on that table is
    reused, and returned as reused_user_source instead of created_user_source; one
    that isn't set up for password login is refused. Calling this again with
    database_id creates a second table and user source.

    The login page is the one already set, or a page at /login that anyone can see, or
    a new one, which created_pages lists. One already set must be visible to everyone,
    or this is refused. The login page gets an auth_form for the user source if it has
    none, beside any form for another user source, and a form with no user source is
    wired to it. Set a password for each user before they can log in.
    If a step fails, no table, field, user source or page is saved.
    """

    builder = get_builder_in_workspace(ctx, builder_id)
    ctx.update_status(_("Setting up user source..."))

    existing = _local_baserow_user_source_on(ctx.user, builder, setup.table_id)
    if existing is not None:
        _raise_unless_password_login_works(existing)
    # A login page that was undone is in the trash, so it counts as none.
    set_login_page = (
        workspace_pages(ctx.workspace).filter(id=builder.login_page_id).first()
    )
    if set_login_page and set_login_page.visibility != Page.VISIBILITY_TYPES.ALL:
        raise ToolInputError(
            f"Login page {set_login_page.id} is only for logged-in visitors, so nobody "
            "could reach it to log in. Make it visible to everyone with update_page, "
            "or set another login page with update_builder. No changes were applied."
        )
    login_page_id = set_login_page.id if set_login_page else None
    creates_page = not login_page_id and not helpers.find_public_login_page(builder)

    field_map: dict[str, Any] = {}
    with transaction.atomic():
        if existing is not None:
            user_source, table_id = existing, setup.table_id
        else:
            if setup.table_id:
                ctx.update_status(_("Validating existing table..."))
                table, field_map = helpers.resolve_existing_table(
                    ctx.user, ctx.workspace, setup.table_id
                )
            else:
                ctx.update_status(_("Creating users table..."))
                table, field_map = helpers.create_users_table(
                    ctx.user, setup.database_id, ctx.workspace, setup.get_roles()
                )
            ctx.update_status(_("Creating user source..."))
            integration = helpers.get_local_baserow_integration(ctx.user, builder)
            user_source = helpers.create_user_source(
                ctx.user, builder, setup.name, table, field_map, integration
            )
            table_id = table.id

        login_page = None
        if not login_page_id:
            ctx.update_status(_("Creating login page..."))
            login_page = helpers.create_login_page(ctx.user, builder, user_source.id)
            login_page_id = login_page.id
        else:
            helpers.add_auth_form(ctx.user, set_login_page, user_source.id)

    key = "created_user_source" if existing is None else "reused_user_source"
    result: dict[str, Any] = {
        key: _user_source_item(user_source, table_id),
        "table_id": table_id,
        "roles": UserSourceHandler().get_all_roles_for_application(builder),
        "login_page_id": login_page_id,
    }
    if creates_page:
        result["created_pages"] = [PageItem.from_orm(login_page).model_dump()]
    if "hint" in field_map:
        result["hint"] = field_map["hint"]
    return result
