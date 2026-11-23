from django.contrib.contenttypes.models import ContentType

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow_enterprise.agent_permissions.models import (
    DEFAULT_ROLE,
    AgentParticipationRule,
)
from baserow_enterprise.api.field_permissions.serializers import (
    FieldPermissionSubjectRequestSerializer,
    FieldPermissionSubjectResponseSerializer,
)
from baserow_enterprise.field_permissions.models import FieldPermissionsRoleEnum


class AgentParticipationRuleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[role.value for role in FieldPermissionsRoleEnum],
        help_text="The lowest role allowed, `CUSTOM` for the chosen people and "
        "teams, or `NOBODY`.",
    )
    subjects = FieldPermissionSubjectRequestSerializer(
        many=True,
        required=False,
        default=list,
        help_text="The people and teams of a `CUSTOM` rule.",
    )


class AgentParticipationRuleResponseSerializer(AgentParticipationRuleSerializer):
    subjects = serializers.SerializerMethodField()

    @extend_schema_field(FieldPermissionSubjectResponseSerializer(many=True))
    def get_subjects(self, rule: AgentParticipationRule) -> list[dict]:
        return FieldPermissionSubjectResponseSerializer(
            [
                {
                    "subject_type": ContentType.objects.get_for_model(subject),
                    "subject_id": subject.id,
                    "subject": subject,
                }
                for subject in [*rule.users.all(), *rule.teams.all()]
            ],
            many=True,
        ).data


class AgentParticipationRulesResponseSerializer(serializers.Serializer):
    chat = AgentParticipationRuleResponseSerializer()
    approve = AgentParticipationRuleResponseSerializer()
    continue_ = AgentParticipationRuleResponseSerializer()

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        # `continue` is a Python keyword, so it can't name the class attribute.
        fields["continue"] = fields.pop("continue_")
        return fields


def serialize_rule(rule: AgentParticipationRule | None, capability: str) -> dict:
    """
    :param rule: The stored rule, as `AgentParticipationHandler.get_rules` returns
        it, or None where the default applies.
    :param capability: The capability the rule controls.
    :return: The role, with the people and teams of a `CUSTOM` rule.
    """

    if rule is None:
        return {"role": DEFAULT_ROLE[capability], "subjects": []}
    return AgentParticipationRuleResponseSerializer(rule).data
