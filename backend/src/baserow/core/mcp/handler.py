from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.core.handler import CoreHandler
from baserow.core.utils import random_string

from ..models import Workspace
from .exceptions import (
    MaximumUniqueEndpointTriesError,
    MCPEndpointDoesNotBelongToUser,
    MCPEndpointDoesNotExist,
)
from .models import MCPEndpoint
from .operations import (
    CreateMCPEndpointOperationType,
    DeleteMCPEndpointOperationType,
    ReadMCPEndpointOperationType,
    UpdateMCPEndpointOperationType,
)


class MCPEndpointHandler:
    def get_by_key(self, key: str) -> MCPEndpoint:
        """
        Fetches a single MCP endpoint instance based on the key.

        :param key: The unique endpoint key.
        :raises MCPEndpointDoesNotExist: Raised when the requested endpoint was not
            found.
        :return: The fetched endpoint matching the provided key.
        """

        try:
            endpoint = MCPEndpoint.objects.select_related("workspace", "user").get(
                key=key
            )
        except MCPEndpoint.DoesNotExist:
            raise MCPEndpointDoesNotExist(
                f"The MCP endpoint with key {key} does not exist."
            )

        return endpoint

    def get_endpoint(
        self, user: AbstractUser, endpoint_id: int, base_queryset: QuerySet = None
    ) -> MCPEndpoint:
        """
        Fetches a single MCP endpoint and checks if the user belongs to the workspace.

        :param user: The user on whose behalf the endpoint is requested.
        :type user: User
        :param endpoint_id: The id of the requested endpoint.
        :type endpoint_id: int
        :param base_queryset: The base queryset from where to select the endpoint
            object from. This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises MCPEndpointDoesNotExist: Raised when the requested endpoint was not
            found or if it does not belong to the user.
        :return: The fetched endpoint.
        :rtype: MCPEndpoint
        """

        if base_queryset is None:
            base_queryset = MCPEndpoint.objects

        try:
            endpoint = base_queryset.select_related("workspace").get(
                id=endpoint_id, user=user
            )
        except MCPEndpoint.DoesNotExist:
            raise MCPEndpointDoesNotExist(
                f"The MCP endpoint with id {endpoint_id} does not exist."
            )

        workspace = endpoint.workspace
        CoreHandler().check_permissions(
            user,
            ReadMCPEndpointOperationType.type,
            workspace=workspace,
            context=endpoint,
        )

        return endpoint

    def generate_unique_key(self, length: int = 32, max_tries: int = 1000) -> str:
        """
        Generates a unique MCP endpoint key.

        :param length: Indicates the amount of characters that the endpoint key must
            contain.
        :param max_tries: The maximum amount of tries to check if an endpoint with the
            key already exists.
        :raises MaximumUniqueEndpointTriesError: When the maximum amount of tries has
            been exceeded. A new generated endpoint key is tried every time the key
            already exists.
        :return: A unique endpoint key
        """

        i = 0

        while True:
            if i > max_tries:
                raise MaximumUniqueEndpointTriesError(
                    f"Tried {max_tries} endpoint keys, but none of them are unique."
                )

            i += 1
            key = random_string(length)

            if not MCPEndpoint.objects.filter(key=key).exists():
                return key

    def create_endpoint(
        self, user: AbstractUser, workspace: Workspace, name: str
    ) -> MCPEndpoint:
        """
        Creates a new MCP endpoint.

        :param user: The user of whose behalf the endpoint is created.
        :type user: User
        :param workspace: The workspace object of which the endpoint is related to.
        :type workspace: Workspace
        :param name: The name of the endpoint.
        :type name: str
        :return: The created endpoint instance.
        :rtype: MCPEndpoint
        """

        CoreHandler().check_permissions(
            user,
            CreateMCPEndpointOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        endpoint = MCPEndpoint.objects.create(
            name=name, key=self.generate_unique_key(), user=user, workspace=workspace
        )

        return endpoint

    def update_endpoint(
        self, user: AbstractUser, endpoint: MCPEndpoint, name: str
    ) -> MCPEndpoint:
        """
        Updates an existing MCP endpoint.

        :param user: The user on whose behalf the endpoint is updated.
        :param endpoint: The endpoint object that needs to be updated.
        :param name: The new name of the endpoint.
        :raises MCPEndpointDoesNotBelongToUser: When the provided endpoint does not
            belong the provided user.
        :return: The updated endpoint instance.
        :rtype: MCPEndpoint
        """

        if not user.id == endpoint.user_id:
            raise MCPEndpointDoesNotBelongToUser(
                "The user is not authorized to update the endpoint."
            )

        CoreHandler().check_permissions(
            user,
            UpdateMCPEndpointOperationType.type,
            workspace=endpoint.workspace,
            context=endpoint,
        )

        endpoint.name = name
        endpoint.save()

        return endpoint

    def delete_endpoint(self, user: AbstractUser, endpoint: MCPEndpoint):
        """
        Deletes an existing MCP endpoint

        :param user: The user on whose behalf the endpoint is deleted.
        :param endpoint: The endpoint object that needs to be deleted.
        :raises MCPEndpointDoesNotBelongToUser: When the provided endpoint does not
            belong the provided user.
        """

        if not user.id == endpoint.user_id:
            raise MCPEndpointDoesNotBelongToUser(
                "The user is not authorized to delete the endpoint."
            )

        CoreHandler().check_permissions(
            user,
            DeleteMCPEndpointOperationType.type,
            workspace=endpoint.workspace,
            context=endpoint,
        )

        endpoint.delete()
