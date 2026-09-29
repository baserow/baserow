from typing import List, Optional, cast

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from baserow.core.action.registries import ActionScopeStr, ActionScopeType
from baserow.core.models import WorkspaceUser

WORKSPACE_ACTION_CONTEXT = _('in group "%(group_name)s" (%(group_id)s).')


class RootActionScopeType(ActionScopeType):
    type = "root"

    @classmethod
    def value(cls) -> ActionScopeStr:
        return cast(ActionScopeStr, cls.type)

    def get_request_serializer_field(self) -> serializers.Field:
        return serializers.BooleanField(
            allow_null=True,
            required=False,
            help_text="If set to true then actions registered in the root scope "
            "will be included when undoing or redoing.",
        )

    def valid_serializer_value_to_scope_str(self, value) -> Optional[ActionScopeStr]:
        return self.value() if value else None


class WorkspaceActionScopeType(ActionScopeType):
    type = "workspace"

    @classmethod
    def value(cls, workspace_id: int) -> ActionScopeStr:
        return cast(ActionScopeStr, cls.type + str(workspace_id))

    def get_request_serializer_field(self) -> serializers.Field:
        return serializers.IntegerField(
            min_value=0,
            allow_null=True,
            required=False,
            help_text="If set to a workspaces id then any actions directly related "
            "to that workspace will be be included when undoing or redoing.",
        )

    def valid_serializer_value_to_scope_str(
        self, value: int
    ) -> Optional[ActionScopeStr]:
        return self.value(value)


class AllWorkspacesActionScopeType(ActionScopeType):
    """
    Requested by a surface that shows the applications of every workspace of the user
    without one being selected, like the all workspaces homepage. It stands for the
    workspace scope of each workspace the user is a member of, so actions performed
    on that surface (which register in their workspace scope as usual) can be undone
    from it, while a workspace only ever sees its own actions.
    """

    type = "all_workspaces"

    @classmethod
    def value(cls) -> ActionScopeStr:
        return cast(ActionScopeStr, cls.type)

    def get_request_serializer_field(self) -> serializers.Field:
        return serializers.BooleanField(
            allow_null=True,
            required=False,
            help_text="If set to true then actions registered in the workspace scope "
            "of every workspace the user is a member of will be included when "
            "undoing or redoing.",
        )

    def valid_serializer_value_to_scope_str(self, value) -> Optional[ActionScopeStr]:
        return self.value() if value else None

    def resolve(self, user: AbstractUser, scope_str: ActionScopeStr) -> List[str]:
        workspace_ids = WorkspaceUser.objects.filter(user=user).values_list(
            "workspace_id", flat=True
        )
        return [
            WorkspaceActionScopeType.value(workspace_id)
            for workspace_id in workspace_ids
        ]


class ApplicationActionScopeType(ActionScopeType):
    type = "application"

    @classmethod
    def value(cls, application_id: int) -> ActionScopeStr:
        return cast(ActionScopeStr, cls.type + str(application_id))

    def get_request_serializer_field(self) -> serializers.Field:
        return serializers.IntegerField(
            min_value=0,
            allow_null=True,
            required=False,
            help_text="If set to an applications id then any actions directly related "
            "to that application will be be included when undoing or redoing.",
        )

    def valid_serializer_value_to_scope_str(
        self, value: int
    ) -> Optional[ActionScopeStr]:
        return self.value(value)
