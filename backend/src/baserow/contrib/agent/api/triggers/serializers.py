from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.services.serializers import (
    PolymorphicServiceRequestSerializer,
    PolymorphicServiceSerializer,
)
from baserow.contrib.agent.constants import AGENT_TRIGGER_NAME_MAX_LENGTH
from baserow.contrib.agent.models import AgentTrigger
from baserow.core.formula.serializers import FormulaSerializerField

MESSAGE_HELP_TEXT = (
    "The formula, resolved against the trigger's payload, whose text opens each "
    "conversation the trigger starts. Empty opens it with the payload itself."
)
SERVICE_HELP_TEXT = "The service producing the trigger's events."
NAME_HELP_TEXT = (
    "The trigger's name, trimmed. Blank shows a default worded by its type, such "
    "as its schedule."
)
ON_OVERLAP_HELP_TEXT = (
    "What a firing does while a reply of the trigger is still going: `skip` "
    "starts nothing, `wait` queues its conversation until that reply ends, "
    "`parallel` starts it alongside, up to a cap, then queues it."
)


class AgentTriggerSerializer(serializers.ModelSerializer):
    """A trigger with its service, whose schema describes its payload, and message."""

    type = serializers.SerializerMethodField(
        help_text="The service type of the trigger."
    )
    # A ModelSerializer would render the TextField-based formula as a plain string.
    message = FormulaSerializerField(help_text=MESSAGE_HELP_TEXT)
    service = PolymorphicServiceSerializer(help_text=SERVICE_HELP_TEXT)
    # Read-only model fields lose allow_blank, so the schema would reject "".
    last_skipped_reason = serializers.ChoiceField(
        choices=AgentTrigger.SkipReason.choices,
        allow_blank=True,
        read_only=True,
        help_text="Why the last skipped firing started nothing, empty until one is.",
    )

    class Meta:
        model = AgentTrigger
        fields = (
            "id",
            "type",
            "name",
            "enabled",
            "message",
            "on_overlap",
            "service",
            "last_fired_on",
            "last_skipped_on",
            "last_skipped_reason",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "name": {"help_text": NAME_HELP_TEXT},
            "on_overlap": {"help_text": ON_OVERLAP_HELP_TEXT},
            "last_fired_on": {
                "read_only": True,
                "help_text": "When a firing last started or queued a conversation.",
            },
            "last_skipped_on": {
                "read_only": True,
                "help_text": "When a firing was last skipped.",
            },
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance: AgentTrigger) -> str:
        """
        Name the service type of the trigger.

        :param instance: The trigger being serialized.
        :return: The service type name, such as ``periodic``.
        """

        return instance.service.get_type().type


class TriggerServiceFieldMixin:
    """Adds a `service` field of the trigger's own service type."""

    def get_fields(self) -> dict[str, serializers.Field]:
        """
        Add the service field pinned to the service type named in the context, so
        the payload may leave `type` out and may not name another.

        :return: The declared fields plus `service`.
        """

        fields = super().get_fields()
        fields["service"] = PolymorphicServiceRequestSerializer(
            default_type_name=self.context.get("service_type_name"),
            required=False,
            help_text=SERVICE_HELP_TEXT,
        )
        return fields


class CreateAgentTriggerSerializer(
    TriggerServiceFieldMixin,
    UnknownFieldRaisesExceptionSerializerMixin,
    serializers.Serializer,
):
    """A new trigger: its type, message, switch and initial service values."""

    type = serializers.CharField(
        max_length=255,
        help_text="The service type of the trigger, one of the configuration's "
        "available_trigger_types.",
    )
    name = serializers.CharField(
        max_length=AGENT_TRIGGER_NAME_MAX_LENGTH,
        allow_blank=True,
        required=False,
        default="",
        help_text=NAME_HELP_TEXT,
    )
    message = FormulaSerializerField(help_text=MESSAGE_HELP_TEXT)
    enabled = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether the trigger starts conversations right away.",
    )
    on_overlap = serializers.ChoiceField(
        choices=AgentTrigger.OnOverlap.choices,
        required=False,
        default=AgentTrigger.OnOverlap.SKIP,
        help_text=ON_OVERLAP_HELP_TEXT,
    )


class UpdateAgentTriggerSerializer(
    TriggerServiceFieldMixin,
    UnknownFieldRaisesExceptionSerializerMixin,
    serializers.Serializer,
):
    """The parts of a trigger to change; the ones left out keep their value."""

    type = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Another service type for the trigger, one of the "
        "configuration's available_trigger_types: its service is replaced by a "
        "new one of that type, set from `service`. The trigger keeps its id, "
        "name, switch and other settings.",
    )
    name = serializers.CharField(
        max_length=AGENT_TRIGGER_NAME_MAX_LENGTH,
        allow_blank=True,
        required=False,
        help_text=NAME_HELP_TEXT,
    )
    enabled = serializers.BooleanField(
        required=False,
        help_text="Whether the trigger starts conversations when its event happens.",
    )
    message = FormulaSerializerField(help_text=MESSAGE_HELP_TEXT)
    on_overlap = serializers.ChoiceField(
        choices=AgentTrigger.OnOverlap.choices,
        required=False,
        help_text=ON_OVERLAP_HELP_TEXT,
    )
