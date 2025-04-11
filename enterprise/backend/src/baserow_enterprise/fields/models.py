from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin
from baserow_enterprise.role.constants import ADMIN_ROLE_UID, BUILDER_ROLE_UID


class FieldPermission(CreatedAndUpdatedOnMixin):
    """
    Specifies the minimum role required to add or update field's data. "CUSTOM" allows
    actor-specific permissions via RoleAssignments. "NOBODY" blocks all updates. Other
    roles permit to add or update data to users with that role or higher.
    """

    NOBDOY_ROLE_UID = "NOBODY"
    CUSTOM_ROLE_UID = "CUSTOM"

    field = models.OneToOneField(
        "database.Field",
        on_delete=models.CASCADE,
        related_name="permission",
        help_text="The field that this permission applies to.",
    )
    role = models.TextField(
        help_text="The minimum role required to update the data of this field.",
        choices=[
            (ADMIN_ROLE_UID, "Admin"),
            (BUILDER_ROLE_UID, "Builder"),
            (CUSTOM_ROLE_UID, "Custom"),
            (NOBDOY_ROLE_UID, "Nobody"),
        ],
    )
