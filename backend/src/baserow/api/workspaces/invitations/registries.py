from typing import TYPE_CHECKING, Dict, List

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class InvitationDataType(Instance):
    """
    Adds a payload to the workspace invitations returned to the people who manage
    them. The data is added to every serialized invitation under the key containing
    the type name, so that a plugin can tell what an invitation carries next to its
    workspace role.
    """

    def get_serializer_field(self) -> serializers.Field:
        """
        Returns the serializer field describing the data, used to document the
        response.
        """

        raise NotImplementedError(
            "The get_serializer_field must be implemented and should return a Field."
        )

    def annotate_serialized_workspace_invitations_data(
        self,
        workspace: "Workspace",
        serialized_data: List[Dict],
        user: AbstractUser,
    ) -> List[Dict]:
        """
        Adds the data of this type to every serialized invitation, under the key
        containing the type name. The data is shown to the given user, so it should
        only contain what they may read.

        :param workspace: The workspace the invitations belong to.
        :param serialized_data: The serialized invitations, changed in place.
        :param user: The user the invitations are returned to.
        :return: The same serialized invitations.
        """

        raise NotImplementedError(
            "The annotate_serialized_workspace_invitations_data must be implemented."
        )


class InvitationDataRegistry(Registry[InvitationDataType]):
    name = "api_invitation_data"


invitation_data_registry: InvitationDataRegistry = InvitationDataRegistry()
