from typing import Any

from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body_custom_fields,
)
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    validate_data_custom_fields,
)
from baserow.contrib.agent.api.views import AGENT_ID_PATH_PARAMETER
from baserow.contrib.agent.channels.actions import (
    CreateAgentChannelActionType,
    DeleteAgentChannelActionType,
    UpdateAgentChannelActionType,
)
from baserow.contrib.agent.channels.exceptions import (
    AgentChannelDoesNotExist,
    AgentChannelTypeNotAvailable,
)
from baserow.contrib.agent.channels.registries import agent_channel_type_registry
from baserow.contrib.agent.channels.service import AgentChannelService
from baserow.contrib.agent.models import AgentChannel
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import ApplicationDoesNotExist

from .errors import (
    ERROR_AGENT_CHANNEL_DOES_NOT_EXIST,
    ERROR_AGENT_CHANNEL_TYPE_NOT_AVAILABLE,
)
from .serializers import (
    AgentChannelSerializer,
    CreateAgentChannelSerializer,
    UpdateAgentChannelSerializer,
)

CHANNEL_ID_PATH_PARAMETER = OpenApiParameter(
    name="channel_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the channel.",
)
CHANNEL_EXCEPTIONS = {
    ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
    AgentChannelDoesNotExist: ERROR_AGENT_CHANNEL_DOES_NOT_EXIST,
    AgentChannelTypeNotAvailable: ERROR_AGENT_CHANNEL_TYPE_NOT_AVAILABLE,
}
AGENT_ERRORS = {
    401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
    404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
}
CHANNEL_ERRORS = {
    **AGENT_ERRORS,
    404: get_error_schema(
        ["ERROR_APPLICATION_DOES_NOT_EXIST", "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST"]
    ),
}
WRITE_ERRORS = {
    400: get_error_schema(
        ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_AGENT_CHANNEL_TYPE_NOT_AVAILABLE"]
    ),
}
CHANNEL_RESPONSE = DiscriminatorCustomFieldsMappingSerializer(
    agent_channel_type_registry, AgentChannelSerializer
)


def serialize_channel(channel: AgentChannel) -> dict[str, Any]:
    """
    :param channel: A channel of its type.
    :return: The channel with the fields its type shows.
    """

    return agent_channel_type_registry.get_serializer(
        channel, AgentChannelSerializer
    ).data


class AgentChannelsView(APIView):
    """Lists an agent's channels and adds new ones."""

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER],
        tags=["Agent applications"],
        operation_id="list_agent_channels",
        description=(
            "Lists the channels of the agent, each with the fields of its type. "
            "Requires permission to read the agent's configuration."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                agent_channel_type_registry, AgentChannelSerializer, many=True
            ),
            **AGENT_ERRORS,
        },
    )
    @map_exceptions(CHANNEL_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        """Responds with the channels if the user can read the configuration."""

        channels = AgentChannelService().list_channels(request.user, agent_id)
        return Response([serialize_channel(channel) for channel in channels])

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=["Agent applications"],
        operation_id="create_agent_channel",
        description=(
            "Adds a channel of a type the workspace's license covers to the agent. "
            "Requires permission to update the agent and read its configuration."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            agent_channel_type_registry, CreateAgentChannelSerializer, request=True
        ),
        responses={200: CHANNEL_RESPONSE, **WRITE_ERRORS, **AGENT_ERRORS},
    )
    @transaction.atomic
    @map_exceptions(CHANNEL_EXCEPTIONS)
    @require_request_data_type(dict)
    @validate_body_custom_fields(
        agent_channel_type_registry,
        base_serializer_class=CreateAgentChannelSerializer,
        return_validated=True,
    )
    def post(self, request: Request, agent_id: int, data: dict[str, Any]) -> Response:
        """Validates the payload against the fields of the type it names."""

        channel = action_type_registry.get_by_type(CreateAgentChannelActionType).do(
            request.user, agent_id, data.pop("type"), **data
        )
        return Response(serialize_channel(channel))


class AgentChannelView(APIView):
    """Changes or trashes one of an agent's channels."""

    @extend_schema(
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            CHANNEL_ID_PATH_PARAMETER,
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent applications"],
        operation_id="update_agent_channel",
        description=(
            "Updates the provided fields of the channel. A channel whose type the "
            "workspace's license doesn't cover can only be switched off. Requires "
            "permission to update the agent and read its configuration."
        ),
        request=CustomFieldRegistryMappingSerializer(
            agent_channel_type_registry,
            UpdateAgentChannelSerializer,
            request=True,
            partial_request=True,
        ),
        responses={200: CHANNEL_RESPONSE, **WRITE_ERRORS, **CHANNEL_ERRORS},
    )
    @transaction.atomic
    @map_exceptions(CHANNEL_EXCEPTIONS)
    @require_request_data_type(dict)
    def patch(self, request: Request, agent_id: int, channel_id: int) -> Response:
        """Validates the payload against the fields of the channel's type."""

        channel = AgentChannelService().get_channel(request.user, agent_id, channel_id)
        data = validate_data_custom_fields(
            agent_channel_type_registry.get_for_channel(channel).type,
            agent_channel_type_registry,
            request.data,
            base_serializer_class=UpdateAgentChannelSerializer,
            partial=True,
            return_validated=True,
        )
        channel = action_type_registry.get_by_type(UpdateAgentChannelActionType).do(
            request.user, agent_id, channel_id, **data
        )
        return Response(serialize_channel(channel))

    @extend_schema(
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            CHANNEL_ID_PATH_PARAMETER,
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent applications"],
        operation_id="delete_agent_channel",
        description=(
            "Moves the channel to the trash, where it can be restored. Requires "
            "permission to update the agent and read its configuration."
        ),
        responses={
            204: None,
            **CHANNEL_ERRORS,
        },
    )
    @transaction.atomic
    @map_exceptions(CHANNEL_EXCEPTIONS)
    def delete(self, request: Request, agent_id: int, channel_id: int) -> Response:
        """Trashes the channel if the user can update the agent."""

        action_type_registry.get_by_type(DeleteAgentChannelActionType).do(
            request.user, agent_id, channel_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
