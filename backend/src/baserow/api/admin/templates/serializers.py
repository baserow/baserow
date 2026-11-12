from typing import Optional

from django.contrib.auth import get_user_model

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.templates.serializers import (
    TemplateCategorySerializer,
    TemplateSerializer,
)
from baserow.core.models import Template, UserTemplateState
from baserow.core.user_templates.constants import USER_TEMPLATE_ADMIN_STATES
from baserow.core.user_templates.handler import UserTemplateHandler

User = get_user_model()


class AdminUserTemplateAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "email")


class AdminUserTemplateSerializer(TemplateSerializer):
    """
    A row of the admin page.
    """

    categories = TemplateCategorySerializer(read_only=True, many=True)

    author = AdminUserTemplateAuthorSerializer(
        source="get_root.author",
        read_only=True,
        allow_null=True,
        help_text="The author of the template. Null if they were deleted.",
    )
    state = serializers.ChoiceField(
        source="admin_state",
        choices=UserTemplateState.choices,
        read_only=True,
        help_text="The tab of the admin page the template is on, or private once "
        "an admin unblocked it.",
    )
    reason = serializers.SerializerMethodField(
        help_text="Why an admin rejected or blocked the template, for a rejected "
        "or blocked one."
    )
    listed = serializers.SerializerMethodField(
        help_text="Whether a revision of the template is listed for everybody, "
        "also while a later one is in review or rejected."
    )
    can_approve = serializers.BooleanField(
        read_only=True,
        help_text="Whether an admin can approve the revision: in review or "
        "rejected, with content, and not edited since it was submitted.",
    )
    edited_since_submitted = serializers.BooleanField(
        read_only=True,
        help_text="Whether the template was edited since the revision was "
        "submitted, which is why an admin can't approve it.",
    )
    can_reject = serializers.SerializerMethodField(
        help_text="Whether an admin can reject the template: in review, or listed."
    )
    reject_unlists = serializers.SerializerMethodField(
        help_text="Whether rejecting the template takes it out of the listing: "
        "when it's listed, unless only its edit is in review."
    )
    updated_on = serializers.DateTimeField(
        source="template_updated_on",
        read_only=True,
        help_text="When the revision was made.",
    )
    reviewed_on = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
        help_text="When an admin, or a submit without review, last reviewed the "
        "revision. Null if never.",
    )
    install_count = serializers.IntegerField(
        source="template_install_count",
        read_only=True,
        help_text="How many times the template was installed.",
    )
    submitted_on = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
        help_text="When the revision was submitted for review, if it was.",
    )

    class Meta(TemplateSerializer.Meta):
        fields = (
            "id",
            "revision_id",
            "slug",
            "type",
            "name",
            "description",
            "icon",
            "workspace_id",
            "open_application",
            "categories",
            "author",
            "state",
            "reason",
            "listed",
            "can_approve",
            "edited_since_submitted",
            "can_reject",
            "reject_unlists",
            "updated_on",
            "reviewed_on",
            "install_count",
            "submitted_on",
        )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_reason(self, instance: Template) -> Optional[str]:
        if instance.admin_state == UserTemplateState.REJECTED:
            return instance.reject_reason or None
        if instance.admin_state == UserTemplateState.BLOCKED:
            return instance.get_root().blocked_reason or None
        return None

    @extend_schema_field(serializers.BooleanField())
    def get_listed(self, instance: Template) -> bool:
        return UserTemplateHandler().is_listed(instance)

    @extend_schema_field(serializers.BooleanField())
    def get_can_reject(self, instance: Template) -> bool:
        return UserTemplateHandler().reject_applies(
            instance.admin_state, self.get_listed(instance)
        )

    @extend_schema_field(serializers.BooleanField())
    def get_reject_unlists(self, instance: Template) -> bool:
        return UserTemplateHandler().reject_unlists(
            instance.admin_state, self.get_listed(instance)
        )


class AdminApproveUserTemplateSerializer(serializers.Serializer):
    revision_id = serializers.IntegerField(
        help_text="The id of the revision the admin reviewed, which must still be "
        "the row of the template."
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
    reviewed_on = serializers.DateTimeField(
        allow_null=True,
        help_text="The `reviewed_on` of the revision the admin reviewed, which must "
        "still be its value.",
    )


class AdminRejectUserTemplateSerializer(AdminApproveUserTemplateSerializer):
    reason = serializers.CharField(
        max_length=1000, help_text="Why the template is rejected, shown to its author."
    )


class AdminBlockUserTemplateSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=1000, help_text="Why the template is blocked, shown to its author."
    )


class AdminUserTemplatesQueryParamsSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=USER_TEMPLATE_ADMIN_STATES)


class AdminUserTemplateCountsSerializer(serializers.Serializer):
    in_review = serializers.IntegerField(help_text="The templates in review.")
    public = serializers.IntegerField(
        help_text="The listed templates without an edit in review or rejected."
    )
    rejected = serializers.IntegerField(help_text="The rejected templates.")
    blocked = serializers.IntegerField(help_text="The blocked templates.")
