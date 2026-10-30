from django.contrib.auth import get_user_model

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.templates.serializers import TemplateSerializer
from baserow.core.user_templates.constants import (
    USER_TEMPLATE_ADMIN_STATES,
    UserTemplateState,
)
from baserow.core.user_templates.handler import UserTemplateHandler

User = get_user_model()


class AdminUserTemplateAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "email")


class AdminUserTemplateSerializer(TemplateSerializer):
    """
    The latest revision of a user template in the admin templates list, see
    `UserTemplateHandler.list_templates_for_admin`. The author, state and update
    date are the template's.
    """

    author = AdminUserTemplateAuthorSerializer(
        source="get_root.author",
        read_only=True,
        allow_null=True,
        help_text="The author of the template. Null if they were deleted.",
    )
    state = serializers.SerializerMethodField(
        help_text="The state of the template, as shown to its author."
    )
    reason = serializers.SerializerMethodField(
        help_text="Why the template was rejected or blocked, if given."
    )
    listed = serializers.SerializerMethodField(
        help_text="Whether a revision of the template is listed for everybody, "
        "also while a later one is in review or rejected."
    )
    updated_on = serializers.DateTimeField(
        source="template_updated_on",
        read_only=True,
        help_text="When the template was last updated.",
    )

    class Meta(TemplateSerializer.Meta):
        fields = (
            "id",
            "revision_id",
            "name",
            "description",
            "icon",
            "author",
            "state",
            "reason",
            "listed",
            "updated_on",
        )

    @extend_schema_field(serializers.ChoiceField(choices=UserTemplateState.choices))
    def get_state(self, instance):
        state, _ = UserTemplateHandler().get_template_state(instance)
        return state

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_reason(self, instance):
        _, reason = UserTemplateHandler().get_template_state(instance)
        return reason

    @extend_schema_field(serializers.BooleanField())
    def get_listed(self, instance):
        return UserTemplateHandler().is_listed(instance)


class AdminApproveUserTemplateSerializer(serializers.Serializer):
    revision_id = serializers.IntegerField(
        help_text="The id of the revision the admin reviewed, which must still be "
        "the latest revision of the template."
    )
    state = serializers.ChoiceField(
        choices=UserTemplateState.choices,
        help_text="The state of the template the admin reviewed, which must still "
        "be its state.",
    )
    listed = serializers.BooleanField(
        help_text="Whether the template the admin reviewed was listed, which must "
        "still be so."
    )


class AdminRejectUserTemplateSerializer(AdminApproveUserTemplateSerializer):
    reason = serializers.CharField(
        max_length=1000, help_text="Why the template is rejected, shown to its author."
    )


class AdminUserTemplatesQueryParamsSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=USER_TEMPLATE_ADMIN_STATES, required=False)


class AdminUserTemplateCountsSerializer(serializers.Serializer):
    in_review = serializers.IntegerField(help_text="The templates in review.")
    public = serializers.IntegerField(help_text="The public templates.")
    rejected = serializers.IntegerField(help_text="The rejected templates.")
