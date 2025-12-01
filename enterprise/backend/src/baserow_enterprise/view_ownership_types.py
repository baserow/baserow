from django.contrib.auth.models import AbstractUser

from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import ViewOwnershipType
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import Workspace
from baserow_enterprise.features import RBAC


class RestrictedViewOwnershipType(ViewOwnershipType):
    """
    Represents view that are shared between all users, but users without the
    permissions to create/update/delete filters will not be able to see the rows not
    matching the filters. This is used to give some users only access to part of the
    rows in a table.
    """

    type = "restricted"

    def change_ownership_type(self, user: AbstractUser, view: View) -> View:
        # It's not possible to change to and from restricted view type because that
        # could accidentally expose or restrict data.
        raise PermissionDenied()

    def view_created(self, user: AbstractUser, view: "View", workspace: Workspace):
        LicenseHandler.raise_if_user_doesnt_have_feature(RBAC, user, workspace)
