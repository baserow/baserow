import uuid
from typing import Any

from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from baserow.core.agents.exceptions import AgentDoesNotExist
from baserow.core.agents.registries import agent_extension_type_registry
from baserow.core.cache import global_cache
from baserow.core.models import User, UserProfile, Workspace, WorkspaceUser
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.identity import is_agent_user

AGENT_LAST_ACTIVE_CACHE_TTL_SECONDS = 60
AGENT_LAST_ACTIVE_CACHE_KEY = "agent_{agent_id}_last_active"


class AgentHandler:
    """Handles agent identities and their single workspace membership."""

    @staticmethod
    def get_workspace_user(agent: User) -> WorkspaceUser:
        prefetched = getattr(agent, "_prefetched_objects_cache", {})
        memberships = prefetched.get("workspaceuser_set")
        if memberships is None:
            memberships = WorkspaceUser.objects_and_trash.filter(
                user_id=agent.id
            ).select_related("workspace")[:2]
        memberships = list(memberships)
        if not is_agent_user(agent) or len(memberships) != 1:
            raise AgentDoesNotExist()
        return memberships[0]

    @classmethod
    def get_workspace(cls, agent: User) -> Workspace:
        return cls.get_workspace_user(agent).workspace

    @classmethod
    def get_role_uid(cls, agent: User) -> str:
        return cls.get_workspace_user(agent).permissions

    def get_queryset(self, workspace: Workspace) -> QuerySet[User]:
        """
        Returns the agents in the workspace with all registered extensions applied.

        :param workspace: The workspace whose agents should be returned.
        :return: A queryset containing the workspace agents.
        """

        queryset = (
            User.objects_and_agents.filter(
                profile__identity_type=UserProfile.IdentityType.AGENT,
                profile__trashed=False,
                workspaceuser__workspace=workspace,
            )
            .select_related("profile")
            .prefetch_related(
                Prefetch(
                    "workspaceuser_set",
                    queryset=WorkspaceUser.objects_and_trash.select_related(
                        "workspace"
                    ),
                )
            )
            .order_by("first_name", "id")
        )
        return agent_extension_type_registry.enhance_queryset(queryset, workspace)

    def get_agent(
        self, agent_id: int, base_queryset=None, for_update: bool = False
    ) -> User:
        """
        Returns the agent with the given ID.

        :param agent_id: The ID of the agent to return.
        :param base_queryset: An optional queryset to use when retrieving the agent.
        :param for_update: Lock the agent until the surrounding transaction ends.
        :raises AgentDoesNotExist: If an agent with the given ID does not exist in
            the queryset.
        :return: The requested agent.
        """

        queryset = (
            base_queryset
            if base_queryset is not None
            else (
                User.objects_and_agents.filter(
                    profile__identity_type=UserProfile.IdentityType.AGENT,
                    profile__trashed=False,
                ).select_related("profile")
            )
        )
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        try:
            agent = queryset.get(id=agent_id)
        except User.DoesNotExist as exc:
            raise AgentDoesNotExist() from exc
        self.get_workspace_user(agent)
        return agent

    @transaction.atomic
    def create_agent(self, workspace: Workspace, **values: Any) -> User:
        """
        Creates an agent identity with its single membership in the workspace.

        :param workspace: The workspace in which to create the agent.
        :param values: The agent field values.
        :return: The newly created agent.
        """

        email = f"agent-{uuid.uuid4().hex}@agents.invalid"
        agent = User(
            username=email, email=email, first_name=values["name"], is_active=True
        )
        agent.set_unusable_password()
        agent.save()
        UserProfile.objects.create(
            user=agent,
            identity_type=UserProfile.IdentityType.AGENT,
            timezone="UTC",
            email_notification_frequency=UserProfile.EmailNotificationFrequencyOptions.NEVER,
        )
        WorkspaceUser.objects.create(
            user=agent,
            workspace=workspace,
            order=0,
            permissions=values.get(
                "role_uid",
                agent_extension_type_registry.get_default_role_uid(workspace),
            ),
        )
        return agent

    @transaction.atomic
    def update_agent(self, agent: User, **values: Any) -> User:
        """
        Updates the agent's name and workspace role.

        :param agent: The agent to update.
        :param values: The agent field values to update.
        :return: The updated agent.
        """

        membership = self.get_workspace_user(agent)
        if "name" in values:
            agent.first_name = values["name"]
            agent.save(update_fields=["first_name"])
        if "role_uid" in values:
            membership.permissions = values["role_uid"]
            membership.save(update_fields=["permissions", "updated_on"])
        return agent

    def update_last_active(self, agent: User) -> User:
        """
        Sets the agent's last active time at most once per cache interval.

        :param agent: The agent whose last active time should be updated.
        :return: The updated agent.
        """

        def update_timestamp():
            agent.profile.last_active = timezone.now()
            UserProfile.objects_and_trash.filter(user_id=agent.id).update(
                last_active=agent.profile.last_active
            )
            return True

        global_cache.get(
            AGENT_LAST_ACTIVE_CACHE_KEY.format(agent_id=agent.id),
            default=update_timestamp,
            timeout=AGENT_LAST_ACTIVE_CACHE_TTL_SECONDS,
        )
        return agent

    def delete_agent(self, user, agent: User) -> None:
        """
        Moves an agent to the trash.

        :param user: The user deleting the agent.
        :param agent: The agent to delete.
        """

        TrashHandler.trash(user, self.get_workspace(agent), None, agent.profile)
