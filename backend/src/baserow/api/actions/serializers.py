from typing import List, Type

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.core.action.models import Action
from baserow.core.action.registries import ActionScopeStr, action_scope_registry
from baserow.core.action.scopes import ApplicationActionScopeType


def get_action_scopes_request_serializer() -> Type[serializers.Serializer]:
    attrs = {
        "applications": serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            allow_empty=False,
            required=False,
            help_text="IDs of additional applications whose actions can be undone or redone.",
        ),
    }

    for scope_type in action_scope_registry.get_all():
        attrs[scope_type.type] = scope_type.get_request_serializer_field()

    # noinspection PyTypeChecker
    return type(
        "ActionScopesSerializer",
        (UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer),
        attrs,
    )


# noinspection PyPep8Naming
def get_undo_request_serializer() -> Type[serializers.Serializer]:
    """
    Returns a serializer that can be used to validate requests made to undo/redo
    view endpoints.

    We construct the serializer in a function because this serializer's fields in
    the ActionScopesSerializer depend on the contents of the `action_scope_registry`.
    So by putting the construction of this serializer in a function we can be sure
    to only call this when we know this registry has been fully populated (for example
    in a views.py which will only have been imported after all app.ready methods
    have been called and registries setup).
    """

    ActionScopesSerializer = get_action_scopes_request_serializer()

    class UndoRedoRequestSerializer(serializers.Serializer):
        scopes = ActionScopesSerializer(
            required=True,
            help_text="A JSON object with keys and values representing the various "
            "action scopes to include when undoing or redoing. Every action in "
            "Baserow will be associated with a action scope, when undoing/redoing "
            "only actions which match any of the provided scope key:value pairs will "
            "included when this endpoint picks the next action to undo/redo. If no "
            "scopes are provided then all actions performed in the client session "
            "will be included when undoing/redoing.",
        )

        @property
        def data(self) -> List[ActionScopeStr]:
            scope_list = []
            scopes = self.validated_data["scopes"].copy()
            for application_id in scopes.pop("applications", []):
                scope_list.append(ApplicationActionScopeType.value(application_id))
            for scope_type_str, scope_value in scopes.items():
                if scope_value:
                    scope_type = action_scope_registry.get(scope_type_str)
                    scope_str = scope_type.valid_serializer_value_to_scope_str(
                        scope_value
                    )
                    if scope_str is not None:
                        scope_list.append(scope_str)
            return scope_list

    return UndoRedoRequestSerializer


@extend_schema_field(OpenApiTypes.STR)
class UndoRedoResultCodeField(serializers.Field):
    # Please keep code values in sync with
    # web-frontend/modules/core/utils/undoRedoConstants.js:UNDO_REDO_RESULT_CODES
    NOTHING_TO_DO = "NOTHING_TO_DO"
    SUCCESS = "SUCCESS"
    SKIPPED_DUE_TO_ERROR = "SKIPPED_DUE_TO_ERROR"

    def __init__(self, *args, **kwargs):
        kwargs["help_text"] = (
            "Indicates the result of the undo/redo operation. Will be "
            f"'{self.SUCCESS}' on success, '{self.NOTHING_TO_DO}' when "
            "there is no action to undo/redo and "
            f"'{self.SKIPPED_DUE_TO_ERROR}' when the undo/redo failed due "
            "to a conflict or error and was skipped over."
        )
        super().__init__(*args, **kwargs)

    def get_attribute(self, instance):
        return instance["actions"]

    def to_representation(self, actions):
        if not actions:
            return self.NOTHING_TO_DO
        if actions[0].has_error():
            return self.SKIPPED_DUE_TO_ERROR
        else:
            return self.SUCCESS


class UndoRedoActionSerializer(serializers.ModelSerializer):
    action_type = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        source="type",
        initial=None,
        help_text="If an action was undone/redone/skipped due to an error this field "
        "will contain the type of the action that was undone/redone.",
    )
    action_scope = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        source="scope",
        initial=None,
        help_text="If an action was undone/redone/skipped due to an error this field "
        "will contain the scope of the action that was undone/redone.",
    )

    class Meta:
        model = Action
        fields = ("action_type", "action_scope")


class UndoRedoResponseSerializer(serializers.Serializer):
    actions = UndoRedoActionSerializer(many=True)
    result_code = UndoRedoResultCodeField()
