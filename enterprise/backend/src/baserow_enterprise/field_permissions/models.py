from enum import Enum

from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin


class FieldPermissionsRoleEnum(Enum):
    EDITOR = "EDITOR"
    BUILDER = "BUILDER"
    ADMIN = "ADMIN"
    CUSTOM = "CUSTOM"
    NOBODY = "NOBODY"


class FieldPermissions(CreatedAndUpdatedOnMixin):
    """
    Specifies the minimum role required to add or update field's data. "CUSTOM" allows
    actor-specific permissions via RoleAssignments. "NOBODY" blocks all updates. Other
    roles permit to add or update data to users with that role or higher.
    """

    field = models.OneToOneField(
        "database.Field",
        on_delete=models.CASCADE,
        related_name="permission",
        help_text="The field that this permission applies to.",
    )
    role = models.TextField(
        help_text=(
            "The minimum role required to update the data of this field. "
            "EDITOR is the default role for a field, so it is not "
            "necessary to set it, and when reset the field permission "
            "will be set to EDITOR. "
        ),
        choices=[
            (FieldPermissionsRoleEnum.BUILDER.value, "Builder"),
            (FieldPermissionsRoleEnum.ADMIN.value, "Admin"),
            (FieldPermissionsRoleEnum.CUSTOM.value, "Custom"),
            (FieldPermissionsRoleEnum.NOBODY.value, "Nobody"),
        ],
    )
    allow_in_forms = models.BooleanField(
        default=False,
        help_text=(
            "Whether this field can be updated in forms, no matter the "
            "permissions set for the field. This is useful for fields "
            "that are not editable in the table view, but should be "
            "editable in forms."
        ),
    )
