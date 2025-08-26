from typing import TYPE_CHECKING, Any, Dict, List, Union

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class UserDataType(Instance):
    """
    The user data type can be used to inject an additional payload to the API
    JWT response. This is the response when a user authenticates or refreshes his
    token. The returned dict of the `get_user_data` method is added to the payload
    under the key containing the type name.

    Example:

    class TestUserDataType(UserDataType):
        type = "test"

        def get_user_data(user, request):
            return {"test": "value"}

    user_data_registry.register(TestUserDataType())

    Will result into the following response when the user authenticates:
    {
      "token": "eyJ....",
      "user: {
        "id": 1,
        ...
      },
      "test": {
        "test": "value"
      }
    }
    """

    def get_user_data(self, user, request) -> dict:
        """
        Should return a dict containing the additional information that must be added
        to the response payload after the user authenticates.

        :param user: The related user that just authenticated.
        :type user: User
        :param request: The request when the user authenticated.
        :type request: Request
        :return: a dict containing the user data that must be added to the response.
        """

        raise NotImplementedError(
            "The get_user_data must be implemented and should return a dict."
        )

    @classmethod
    def realtime_message_to_update_user_data(
        cls, user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"type": "user_data_updated", "user_data": user_data}


class UserDataRegistry(Registry[UserDataType]):
    name = "api_user_data"

    def get_all_user_data(self, user, request) -> dict:
        """
        Collects the additional user data of all the registered user data type
        instances.

        :param user: The user that just authenticated.
        :type user: User
        :param request: The request when the user authenticated.
        :type request: Request
        :return: a dict containing all additional user data payload for all the
            registered instances.
        """

        return {
            key: value.get_user_data(user, request)
            for key, value in self.registry.items()
        }


class MemberDataType(Instance):
    """
    The member data type can be used to inject an additional payload to the API
    workspace user list responses. The returned dict of the
    `annotate_serialized_workspace_members_data` method is added to the payload under
    the key containing the type name.
    """

    def get_request_serializer_field(
        self,
    ) -> Union[serializers.Field, Dict[str, serializers.Field]]:
        """
        Should be given a `serializers.Field` object, which the `MemberDataType`
        will annotate on `WorkspaceUserSerializer`.
        """

        raise NotImplementedError(
            "The get_request_serializer_field must be implemented and should return a Field."
        )

    def annotate_serialized_workspace_members_data(
        self, workspace: "Workspace", serialized_data: dict, user: AbstractUser
    ) -> dict:
        """
        Should be given a `Serializer.data` object, which the `MemberDataType`
        implementation will annotate with its own data. Should return the same
        `serialized_dat` dict. This data is used on the workspace members listing page.
        """

    def annotate_serialized_admin_users_data(
        self, user_ids: List[int], serialized_data: dict, user: AbstractUser
    ) -> dict:
        """
        Should be given a `Serializer.data` object, which the `MemberDataType`
        implementation will annotate with its own data. Should return the same
        `serialized_dat` dict. This data is used on the admin users listing page.
        """


class MemberDataRegistry(Registry):
    name = "api_member_data"


user_data_registry: UserDataRegistry = UserDataRegistry()
member_data_registry = MemberDataRegistry()
