"""
Login for an application builder: a user source on a table of users and a login
page with an auth form. The user source and the auth form come from enterprise, so
these helpers live here and not with the shared builder tools.
"""

import re
from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.elements.actions import (
    CreateElementActionType,
    UpdateElementActionType,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.actions import CreatePageActionType
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.action.context import without_undo_redo_registration
from baserow.core.actions import UpdateApplicationActionType
from baserow.core.integrations.models import Integration
from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow.core.tools.errors import ToolInputError
from baserow.core.user_sources.actions import CreateUserSourceActionType
from baserow_enterprise.builder.elements.models import AuthFormElement


def create_users_table(
    user: AbstractUser,
    database_id: int,
    workspace: Workspace,
    roles: list[str],
):
    """
    Create a new users table with Name, Email, Password, and Role fields.

    :returns: (table, field_map) where field_map has keys
              "name", "email", "password", "role".
    """

    from baserow.contrib.database.fields.actions import CreateFieldActionType
    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.models import Database
    from baserow.contrib.database.table.actions import CreateTableActionType

    database = (
        CoreService()
        .list_applications_in_workspace(
            user, workspace, base_queryset=Database.objects.filter(id=database_id)
        )
        .first()
    )
    if not database:
        raise ToolInputError(
            f"Database with ID {database_id} not found in this workspace."
        )
    table, _ = CreateTableActionType.do(user, database, "Users", fill_example=False)

    # The table comes with a primary "Name" text field already
    name_field = Field.objects.get(table=table, primary=True)

    email_field = CreateFieldActionType.do(user, table, "email", name="Email")
    password_field = CreateFieldActionType.do(user, table, "password", name="Password")
    role_field = CreateFieldActionType.do(
        user,
        table,
        "single_select",
        name="Role",
        select_options=[{"value": r, "color": "blue"} for r in roles],
    )

    # Add example users, one per role
    from baserow.contrib.database.rows.actions import CreateRowsActionType

    role_options = {opt.value: opt.id for opt in role_field.select_options.all()}
    example_rows = []
    for i, role_name in enumerate(roles, start=1):
        local_part = re.sub(r"[^a-z0-9]+", "-", role_name.lower()).strip("-")
        local_part = local_part or f"user-{i}"
        example_rows.append(
            {
                name_field.db_column: role_name,
                email_field.db_column: f"{local_part}@example.com",
                role_field.db_column: role_options.get(role_name),
            }
        )
    if example_rows:
        CreateRowsActionType.do(user, table, example_rows, model=table.get_model())

    return table, {
        "name": name_field,
        "email": email_field,
        "password": password_field,
        "role": role_field,
        "hint": "Remember to set a password for each user to enable login!",
    }


def resolve_existing_table(
    user: AbstractUser,
    workspace: Workspace,
    table_id: int,
):
    """
    Validate an existing table for use as a user source.

    Auto-detects email, name, password, and role fields by type and name.
    Creates a password field if one doesn't exist.

    :returns: (table, field_map) with keys "name", "email", "password",
              and optionally "role".
    :raises ToolInputError: If the table is missing, or required fields can't be
        detected.
    """

    from baserow.contrib.database.fields.actions import CreateFieldActionType
    from baserow.contrib.database.fields.models import (
        EmailField,
        Field,
        LongTextField,
        PasswordField,
        SingleSelectField,
        TextField,
    )
    from baserow.contrib.database.table.handler import TableHandler
    from baserow.core.db import specific_iterator
    from baserow.core.user_sources.registries import user_source_type_registry

    table = (
        TableHandler()
        .list_workspace_tables(user, workspace)
        .filter(id=table_id)
        .first()
    )
    if table is None:
        raise ToolInputError(f"Table with id {table_id} not found.")

    fields_qs = Field.objects.filter(table=table).order_by("order", "id")
    fields = list(specific_iterator(fields_qs.select_related("content_type")))

    field_map: dict[str, Any] = {}

    for field in fields:
        name_lower = field.name.lower()

        if "email" not in field_map:
            if isinstance(field, EmailField):
                field_map["email"] = field
            elif (
                isinstance(field, (TextField, LongTextField)) and "email" in name_lower
            ):
                field_map["email"] = field

        if "name" not in field_map:
            if isinstance(field, TextField) and "name" in name_lower:
                field_map["name"] = field

        if "password" not in field_map:
            if isinstance(field, PasswordField):
                field_map["password"] = field

        if "role" not in field_map:
            if isinstance(field, SingleSelectField) and "role" in name_lower:
                field_map["role"] = field
            elif isinstance(field, TextField) and "role" in name_lower:
                field_map["role"] = field

    # Fall back to primary field for name
    if "name" not in field_map:
        name_types = user_source_type_registry.get(
            "local_baserow"
        ).field_types_allowed_as_name
        for field in fields:
            if field.primary and field.get_type().type in name_types:
                field_map["name"] = field
                break

    missing = []
    if "email" not in field_map:
        missing.append("email (EmailField or TextField with 'email' in name)")
    if "name" not in field_map:
        missing.append(
            "name (TextField with 'name' in name, or a text, long text, email, "
            "number or uuid primary field)"
        )
    if missing:
        raise ToolInputError(
            f"Table '{table.name}' is missing required fields: {', '.join(missing)}. "
            "Add them or change a field to fit, then call this again. No changes were "
            "applied."
        )

    # Create password field if missing
    if "password" not in field_map:
        taken = next((field for field in fields if field.name == "Password"), None)
        if taken is not None:
            raise ToolInputError(
                f"Table '{table.name}' has a field named 'Password' of type "
                f"{taken.get_type().type}, which can't hold login passwords. Rename "
                "it or change it to a password field, then call this again. No "
                "changes were applied."
            )
        field_map["password"] = CreateFieldActionType.do(
            user, table, "password", name="Password"
        )

    return table, field_map


def create_user_source(
    user: AbstractUser,
    application: Builder,
    name: str,
    table,
    field_map: dict,
    integration: Integration,
):
    """
    Create a Local Baserow user source with password authentication.

    :param field_map: Must have "name", "email", "password"; optionally "role".
    :returns: The created user source.
    """

    from baserow.core.user_sources.registries import user_source_type_registry

    us_type = user_source_type_registry.get("local_baserow")

    kwargs: dict[str, Any] = {
        "name": name,
        "table_id": table.id,
        "integration": integration,
        "email_field_id": field_map["email"].id,
        "name_field_id": field_map["name"].id,
        "auth_providers": [
            {
                "type": "local_baserow_password",
                "password_field_id": field_map["password"].id,
            }
        ],
    }

    if "role" in field_map:
        kwargs["role_field_id"] = field_map["role"].id

    return CreateUserSourceActionType.do(user, us_type, application, **kwargs)


def find_public_login_page(builder: Builder) -> Page | None:
    """The page at /login, when anonymous visitors can see it."""

    return Page.objects.filter(
        builder=builder,
        path="/login",
        shared=False,
        visibility=Page.VISIBILITY_TYPES.ALL,
    ).first()


def create_login_page(
    user: AbstractUser, builder: Builder, user_source_id: int
) -> Page:
    """
    Set up the builder's login page with an auth_form element for the user
    source. A page the model already created at /login is used when anonymous
    visitors can see it, so links to it keep working. Otherwise a Login page is
    created at the first free /login path.
    """

    page = find_public_login_page(builder)
    if page is None:
        path = "/login"
        suffix = 0
        while not PageHandler().is_page_path_unique(builder, path):
            suffix += 1
            path = f"/login-{suffix}"
        # Builders skip update actions, so undo would orphan login_page_id. The
        # audit log still records the page.
        with without_undo_redo_registration(user):
            page = CreatePageActionType.do(user, builder, "Login", path)

    add_auth_form(user, page, user_source_id)
    UpdateApplicationActionType.do(user, builder, login_page_id=page.id)
    return page


def add_auth_form(user: AbstractUser, page: Page, user_source_id: int) -> None:
    """Make sure a form on the page logs people in through the user source."""

    auth_forms = AuthFormElement.objects.filter(page=page)
    # A form without a user source can't log anyone in, so it gets this one.
    for auth_form in auth_forms.filter(user_source__isnull=True):
        UpdateElementActionType.do(user, auth_form, {"user_source_id": user_source_id})
    if not auth_forms.filter(user_source_id=user_source_id).exists():
        auth_form_type = element_type_registry.get("auth_form")
        CreateElementActionType.do(
            user, auth_form_type, page, {"user_source_id": user_source_id}
        )
