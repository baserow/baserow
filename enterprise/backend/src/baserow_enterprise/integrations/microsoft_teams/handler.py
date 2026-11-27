"""
The team, channel and chat pickers of the Teams actions. They ask Microsoft
Graph live, as the integration's account, so they aren't part of the
integration's context data, which every editor load reads.
"""

from typing import Any

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache

from baserow.contrib.integrations.microsoft.models import MicrosoftIntegration
from baserow.contrib.integrations.microsoft.service_types import graph_url
from baserow.contrib.integrations.oauth_account.exceptions import ProviderAPIError
from baserow.contrib.integrations.oauth_account.service_types import (
    BUSY_STATUS_CODES,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.operations import ReadIntegrationOperationType
from baserow.core.services.exceptions import DispatchException
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.integrations.microsoft_teams.exceptions import (
    MicrosoftTeamsPickerError,
)
from baserow_enterprise.integrations.microsoft_teams.service_types import (
    PERSONAL_ACCOUNT_MESSAGE,
    MicrosoftTeamsWriteMessageServiceType,
)

# Long enough for opening the dropdowns of one form, short enough that a new
# team or chat shows up soon.
PICKER_CACHE_SECONDS = 60
# The most recent chats, the most Graph lists in one page.
CHATS_LIMIT = 50


class MicrosoftTeamsHandler:
    def get_integration(
        self, user: AbstractUser, integration_id: int
    ) -> MicrosoftIntegration:
        """
        :param user: Who asks.
        :param integration_id: The Microsoft integration.
        :raises IntegrationDoesNotExist: When it doesn't exist or isn't a
            Microsoft integration.
        :raises PermissionDenied: When the user can't read it.
        :raises FeaturesNotAvailableError: When the workspace can't send Teams
            messages.
        :return: The integration.
        """

        integration = IntegrationHandler().get_integration(integration_id).specific
        if not isinstance(integration, MicrosoftIntegration):
            raise IntegrationDoesNotExist()
        workspace = integration.application.workspace
        CoreHandler().check_permissions(
            user,
            ReadIntegrationOperationType.type,
            workspace=workspace,
            context=integration,
        )
        self.get_service_type().raise_if_deactivated(workspace)
        return integration

    def get_service_type(self) -> MicrosoftTeamsWriteMessageServiceType:
        return service_type_registry.get(MicrosoftTeamsWriteMessageServiceType.type)

    def list_teams(self, integration: MicrosoftIntegration) -> list[dict]:
        """
        :return: The teams the account is a member of, by name.
        """

        # `joinedTeams` takes no query parameters, and lists them all at once.
        answer = self._get(integration, "me", "joinedTeams")
        teams = [
            {"id": team["id"], "name": team.get("displayName") or ""}
            for team in self._values(answer)
        ]
        return sorted(teams, key=lambda team: team["name"].lower())

    def list_channels(
        self, integration: MicrosoftIntegration, team_id: str
    ) -> list[dict]:
        """
        :param team_id: The team, as Graph names it.
        :return: The channels of the team the account can see, by name.
        """

        answer = self._get(
            integration,
            "teams",
            team_id,
            "channels",
            params={"$select": "id,displayName,membershipType"},
        )
        channels = [
            {
                "id": channel["id"],
                "name": channel.get("displayName") or "",
                "membership_type": channel.get("membershipType") or "",
            }
            for channel in self._values(answer)
        ]
        return sorted(channels, key=lambda channel: channel["name"].lower())

    def list_chats(self, integration: MicrosoftIntegration) -> list[dict]:
        """
        :return: The account's most recent chats, the latest first. A chat
            without a topic is named after its other members.
        """

        answer = self._get(
            integration,
            "me",
            "chats",
            params={
                "$top": str(CHATS_LIMIT),
                "$orderby": "lastMessagePreview/createdDateTime desc",
                "$expand": "members",
            },
        )
        return [
            {
                "id": chat["id"],
                "name": self._chat_name(integration, chat),
                "chat_type": chat.get("chatType") or "",
            }
            for chat in self._values(answer)
        ]

    def _chat_name(self, integration: MicrosoftIntegration, chat: dict) -> str:
        if chat.get("topic"):
            return chat["topic"]
        members = chat.get("members") if isinstance(chat.get("members"), list) else []
        others = [
            member.get("displayName") or member.get("email") or ""
            for member in members
            if isinstance(member, dict)
            and member.get("userId") != integration.account_id
        ]
        return ", ".join(name for name in others if name)

    @staticmethod
    def _values(answer: Any) -> list[dict]:
        values = answer.get("value") if isinstance(answer, dict) else None
        if not isinstance(values, list):
            return []
        return [
            value
            for value in values
            if isinstance(value, dict) and isinstance(value.get("id"), str)
        ]

    def _get(
        self, integration: MicrosoftIntegration, *segments: str, params=None
    ) -> Any:
        """
        A cached Graph read as the integration's account. The cache key holds
        the integration's generation, so signing in again or out starts afresh.

        :raises MicrosoftTeamsPickerError: With a message safe to show.
        """

        if integration.is_personal_account:
            raise MicrosoftTeamsPickerError(PERSONAL_ACCOUNT_MESSAGE)

        try:
            key = ":".join(
                [
                    "microsoft_teams_picker",
                    str(integration.id),
                    str(integration.generation),
                    # Quoted like the request, so ids can't collide.
                    graph_url(*segments),
                ]
            )
        except ValueError as exc:
            raise MicrosoftTeamsPickerError("This id is empty or invalid.") from exc

        cached = cache.get(key)
        if cached is not None:
            return cached
        service_type = self.get_service_type()
        # Never saved: it only says which account to act as, so the picker
        # gets the token refresh and the safe messages of the action itself.
        service = service_type.model_class(integration=integration)
        try:
            answer = service_type.graph_request(
                service, "GET", *segments, params=params
            )
        except DispatchException as exc:
            if isinstance(exc.__cause__, ProviderAPIError):
                message = self._api_error_message(exc.__cause__)
            else:
                message = str(exc)
            raise MicrosoftTeamsPickerError(message) from exc
        cache.set(key, answer, PICKER_CACHE_SECONDS)
        return answer

    @staticmethod
    def _api_error_message(exc: ProviderAPIError) -> str:
        if exc.status_code in BUSY_STATUS_CODES:
            return "Microsoft asked for this to be asked again later."
        if exc.status_code == 403:
            return "The connected Microsoft account isn't allowed to list these."
        if exc.status_code == 404:
            return "The team wasn't found."
        return f"Microsoft refused the request: {exc.code or exc.status_code}."
