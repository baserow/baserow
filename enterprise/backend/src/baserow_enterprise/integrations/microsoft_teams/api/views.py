from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.integrations.errors import ERROR_INTEGRATION_DOES_NOT_EXIST
from baserow.api.schemas import get_error_schema
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow_enterprise.integrations.microsoft_teams.exceptions import (
    MicrosoftTeamsPickerError,
)
from baserow_enterprise.integrations.microsoft_teams.handler import (
    MicrosoftTeamsHandler,
)

from .errors import ERROR_MICROSOFT_TEAMS_PICKER
from .serializers import (
    MicrosoftTeamsChannelSerializer,
    MicrosoftTeamsChatSerializer,
    MicrosoftTeamsTeamSerializer,
)

INTEGRATION_ID_PARAMETER = OpenApiParameter(
    name="integration_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the Microsoft integration.",
)

EXCEPTIONS = {
    IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
    UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
    MicrosoftTeamsPickerError: ERROR_MICROSOFT_TEAMS_PICKER,
}

ERROR_RESPONSES = {
    400: get_error_schema(["ERROR_USER_NOT_IN_GROUP", "ERROR_MICROSOFT_TEAMS_PICKER"]),
    402: get_error_schema(["ERROR_FEATURE_NOT_AVAILABLE"]),
    404: get_error_schema(["ERROR_INTEGRATION_DOES_NOT_EXIST"]),
}


class MicrosoftTeamsTeamsView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_ID_PARAMETER],
        tags=["Integrations"],
        operation_id="list_microsoft_teams_teams",
        description="Lists the teams the account of a Microsoft integration is a "
        "member of, to pick where a Teams action sends.",
        responses={200: MicrosoftTeamsTeamSerializer(many=True), **ERROR_RESPONSES},
    )
    @map_exceptions(EXCEPTIONS)
    def get(self, request, integration_id: int):
        handler = MicrosoftTeamsHandler()
        integration = handler.get_integration(request.user, integration_id)
        teams = handler.list_teams(integration)
        return Response(MicrosoftTeamsTeamSerializer(teams, many=True).data)


class MicrosoftTeamsChannelsView(APIView):
    @extend_schema(
        parameters=[
            INTEGRATION_ID_PARAMETER,
            OpenApiParameter(
                name="team_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The id of the team.",
            ),
        ],
        tags=["Integrations"],
        operation_id="list_microsoft_teams_channels",
        description="Lists the channels of a team that the account of a Microsoft "
        "integration can see.",
        responses={
            200: MicrosoftTeamsChannelSerializer(many=True),
            **ERROR_RESPONSES,
        },
    )
    @map_exceptions(EXCEPTIONS)
    def get(self, request, integration_id: int, team_id: str):
        handler = MicrosoftTeamsHandler()
        integration = handler.get_integration(request.user, int(integration_id))
        channels = handler.list_channels(integration, team_id)
        return Response(MicrosoftTeamsChannelSerializer(channels, many=True).data)


class MicrosoftTeamsChatsView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_ID_PARAMETER],
        tags=["Integrations"],
        operation_id="list_microsoft_teams_chats",
        description="Lists the most recent chats of the account of a Microsoft "
        "integration, the latest first.",
        responses={200: MicrosoftTeamsChatSerializer(many=True), **ERROR_RESPONSES},
    )
    @map_exceptions(EXCEPTIONS)
    def get(self, request, integration_id: int):
        handler = MicrosoftTeamsHandler()
        integration = handler.get_integration(request.user, integration_id)
        chats = handler.list_chats(integration)
        return Response(MicrosoftTeamsChatSerializer(chats, many=True).data)
