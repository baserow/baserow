from django.conf import settings

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.models import Template, TemplateCategory
from baserow.core.user_templates.constants import UserTemplateState
from baserow.core.user_templates.handler import UserTemplateHandler


class ListTemplatesQueryParamSerializer(serializers.Serializer):
    view = serializers.ChoiceField(choices=["flat"], required=False)
    type = serializers.ChoiceField(choices=Template.Type.choices, required=False)
    owned = serializers.BooleanField(required=False, default=False)
    search = serializers.CharField(required=False, allow_blank=True)


class InstallTemplateQueryParamSerializer(serializers.Serializer):
    latest = serializers.BooleanField(required=False, default=False)


class TemplateSerializer(serializers.ModelSerializer):
    """
    Serializes a template revision. The id, slug and keywords are the template's,
    so they are read from its root.
    """

    id = serializers.IntegerField(source="family_id", read_only=True)
    type = serializers.SerializerMethodField(
        help_text="Whether it's an official or a user template."
    )
    slug = serializers.SlugField(source="get_root.slug", read_only=True)
    keywords = serializers.CharField(source="get_root.keywords", read_only=True)
    is_default = serializers.SerializerMethodField(
        help_text="Indicates if the template must be selected by default. The "
        "web-frontend automatically selects the first `is_default` template "
        "that it can find."
    )

    class Meta:
        model = Template
        fields = (
            "id",
            "type",
            "name",
            "slug",
            "description",
            "icon",
            "keywords",
            "workspace_id",
            "is_default",
            "open_application",
        )

    @extend_schema_field(serializers.ChoiceField(choices=Template.Type.choices))
    def get_type(self, instance):
        # A null `type` means official.
        return instance.type or Template.Type.OFFICIAL

    @extend_schema_field(OpenApiTypes.STR)
    def get_is_default(self, instance):
        return instance.get_root().slug == settings.DEFAULT_APPLICATION_TEMPLATES[0]


class TemplateCategoriesSerializer(serializers.ModelSerializer):
    templates = TemplateSerializer(read_only=True, many=True)

    class Meta:
        model = TemplateCategory
        fields = ("id", "name", "templates")


class TemplateCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateCategory
        fields = ("id", "name")


class TemplateListItemSerializer(TemplateSerializer):
    """
    The latest revision of a template in the flat list. The dates are the
    template's, so they are read from its root. `state`, `reason`, the source and
    `install_count` are only shown to the owner of a user template, and are null
    otherwise.
    """

    created_on = serializers.DateTimeField(source="get_root.created_on", read_only=True)
    updated_on = serializers.DateTimeField(source="get_root.updated_on", read_only=True)
    categories = TemplateCategorySerializer(read_only=True, many=True)
    state = serializers.SerializerMethodField(
        help_text="The state of the template as shown to its owner. Null for "
        "anyone else."
    )
    reason = serializers.SerializerMethodField(
        help_text="Why the template was rejected or blocked, if given. Only shown "
        "to its owner."
    )
    source_workspace_id = serializers.SerializerMethodField(
        help_text="The workspace the applications of the latest revision were "
        "copied from, if known. Only shown to its owner."
    )
    source_application_ids = serializers.SerializerMethodField(
        help_text="The applications the latest revision was copied from. Only shown "
        "to its owner."
    )
    install_count = serializers.SerializerMethodField(
        help_text="How many times the template was installed. Only shown to its owner."
    )

    class Meta(TemplateSerializer.Meta):
        fields = TemplateSerializer.Meta.fields + (
            "categories",
            "state",
            "reason",
            "source_workspace_id",
            "source_application_ids",
            "install_count",
            "created_on",
            "updated_on",
        )

    def _is_owner(self, instance) -> bool:
        request = self.context.get("request")
        return (
            instance.type == Template.Type.USER
            and request is not None
            and instance.get_root().owner_id == request.user.id
        )

    def _get_owner_state(self, instance):
        if not self._is_owner(instance):
            return None, None
        return UserTemplateHandler().get_template_state(instance)

    def _get_owner_metadata(self, instance):
        if not self._is_owner(instance):
            return None
        return UserTemplateHandler().get_template_metadata(instance)

    @extend_schema_field(
        serializers.ChoiceField(choices=UserTemplateState.choices, allow_null=True)
    )
    def get_state(self, instance):
        state, _ = self._get_owner_state(instance)
        return state

    @extend_schema_field(OpenApiTypes.STR)
    def get_reason(self, instance):
        _, reason = self._get_owner_state(instance)
        return reason

    @extend_schema_field(OpenApiTypes.INT)
    def get_source_workspace_id(self, instance):
        metadata = self._get_owner_metadata(instance)
        return None if metadata is None else metadata.get("source_workspace_id")

    @extend_schema_field(
        serializers.ListField(child=serializers.IntegerField(), allow_null=True)
    )
    def get_source_application_ids(self, instance):
        metadata = self._get_owner_metadata(instance)
        return None if metadata is None else metadata.get("source_application_ids", [])

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_install_count(self, instance):
        if not self._is_owner(instance):
            return None
        # Counted on the root, which the list selects with every revision.
        return instance.get_root().install_count
