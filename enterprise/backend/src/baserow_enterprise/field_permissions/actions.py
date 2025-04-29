import dataclasses

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import (
    TABLE_ACTION_CONTEXT,
    TableActionScopeType,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)

from .handler import FieldPermissionsHandler, FieldPermissionUpdated


class UpdateFieldPermissionsActionType(UndoableActionType):
    type = "update_field_permissions"
    description = ActionTypeDescription(
        _("Update field permissions"),
        _(
            'Field "%(field_name)s" (%(field_id)s): permissions updated to role "%(role)s" and "allow in forms" set to "%(allow_in_forms)s"'
        ),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "database_id",
        "table_id",
        "field_id",
        "role",
        "allow_in_forms",
        "original_role",
        "original_allow_in_forms",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        field_id: int
        field_name: str
        role: str
        allow_in_forms: bool
        original_role: str
        original_allow_in_forms: bool

    @classmethod
    def get_field_for_update(cls, field_id: int) -> Field:
        """
        Retrieves the field instance for the given field ID.

        :param field_id: The ID of the field to retrieve.
        :return: The field instance.
        """

        return FieldHandler().get_field(
            field_id, base_queryset=Field.objects.select_for_update(of=("self",))
        )

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        field: Field,
        role: str,
        allow_in_forms: bool = False,
    ) -> FieldPermissionUpdated:
        """
        Updates the field permissions for a given field, setting the role and whether
        the field is allowed in forms.

        :param user: The user on whose behalf the table is updated.
        :param field: The field instance that needs to be updated.
        :param role: The role to set for the field.
        :param allow_in_forms: Whether the field is allowed in forms.
        """

        original_field_permissions = FieldPermissionsHandler._get_field_permissions(
            field
        )
        original_role = original_field_permissions.role
        original_allow_in_forms = original_field_permissions.allow_in_forms

        field_permissions = FieldPermissionsHandler.update_field_permissions(
            user, field, role, allow_in_forms
        )

        table = field.table
        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            field.id,
            field.name,
            role,
            allow_in_forms,
            original_role,
            original_allow_in_forms,
        )
        workspace = table.database.workspace
        cls.register_action(user, params, cls.scope(table.id), workspace)

        return field_permissions

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_being_undone: Action,
    ):
        field = cls.get_field_for_update(params.field_id)
        FieldPermissionsHandler.update_field_permissions(
            user, field, params.original_role, params.original_allow_in_forms
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        field = cls.get_field_for_update(params.field_id)
        FieldPermissionsHandler.update_field_permissions(
            user, field, params.role, params.allow_in_forms
        )
