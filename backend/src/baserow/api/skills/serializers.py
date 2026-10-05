from rest_framework import serializers

from baserow.core.skills.models import (
    SKILL_CONTENT_MAX_LENGTH,
    SKILL_DESCRIPTION_MAX_LENGTH,
    SKILL_NAME_MAX_LENGTH,
    WorkspaceSkill,
)


class WorkspaceSkillSerializer(serializers.ModelSerializer):
    workspace_id = serializers.IntegerField(read_only=True)
    created_by_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = WorkspaceSkill
        fields = (
            "id",
            "workspace_id",
            "name",
            "description",
            "content",
            "created_by_id",
            "created_on",
            "updated_on",
        )
        read_only_fields = fields


class WorkspaceSkillRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=SKILL_NAME_MAX_LENGTH)
    description = serializers.CharField(
        max_length=SKILL_DESCRIPTION_MAX_LENGTH, required=False, allow_blank=True
    )
    content = serializers.CharField(
        max_length=SKILL_CONTENT_MAX_LENGTH, required=False, allow_blank=True
    )


class UpdateWorkspaceSkillRequestSerializer(WorkspaceSkillRequestSerializer):
    name = serializers.CharField(max_length=SKILL_NAME_MAX_LENGTH, required=False)
