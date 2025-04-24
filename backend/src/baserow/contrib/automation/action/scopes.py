from typing import Optional, cast

from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from baserow.core.action.registries import ActionScopeStr, ActionScopeType

AUTOMATION_ACTION_CONTEXT = _('in automation "%(automation_name)s" (%(automation_id)s).')

NODE_ACTION_CONTEXT = _(
    'in node (%(node_id)s) '
    'of automation "%(automation_name)s" (%(automation_id)s).'
)


class NodeActionScopeType(ActionScopeType):
    type = "node"

    @classmethod
    def value(cls, node_id: int) -> ActionScopeStr:
        return cast(ActionScopeStr, cls.type + str(node_id))

    def get_request_serializer_field(self) -> serializers.Field:
        return serializers.IntegerField(
            min_value=0,
            allow_null=True,
            required=False,
            help_text="If set to a node id then any actions directly related "
            "to that node will be be included when undoing or redoing.",
        )

    def valid_serializer_value_to_scope_str(
        self, value: int
    ) -> Optional[ActionScopeStr]:
        return self.value(value)
