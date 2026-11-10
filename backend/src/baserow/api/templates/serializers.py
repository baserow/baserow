from typing import Optional, Tuple

from django.conf import settings

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.handler import CoreHandler
from baserow.core.models import Template, TemplateCategory, UserTemplateState
from baserow.core.user_templates.handler import UserTemplateHandler


class ListTemplatesQueryParamSerializer(serializers.Serializer):
    view = serializers.ChoiceField(choices=["flat"], required=False)
    type = serializers.ChoiceField(choices=Template.Type.choices, required=False)
    owned = serializers.BooleanField(required=False, default=False)
    search = serializers.CharField(required=False, allow_blank=True)
    listed = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Only the templates everybody can open: the official ones and "
        "the public revision of the public user templates.",
    )
    category = serializers.IntegerField(required=False)


class UpdateTemplateSerializer(serializers.Serializer):
    visibility = serializers.ChoiceField(
        choices=["public", "private"],
        required=False,
        help_text="`public` lists the template, with the name of its author, for "
        "everybody on this instance. `private` takes it out of that listing, so "
        "that only its owner and anyone with its private link can open it.",
    )
    public_listing_consent = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Must be true with `public`: the author agrees that the template "
        "and their name are listed for everybody on this instance. It's recorded "
        "in the audit log.",
    )
    private_link = serializers.BooleanField(
        required=False,
        help_text="`true` creates the private link of the template. Anyone with "
        "the link can preview the template, also signed out, and install or "
        "download it once signed in. `false` turns the link off, so that it stops "
        "working. A public template stays public.",
    )

    def validate(self, data):
        if ("visibility" in data) == ("private_link" in data):
            raise serializers.ValidationError(
                "Exactly one of `visibility` and `private_link` must be given."
            )
        return data


class InstallTemplateQueryParamSerializer(serializers.Serializer):
    latest = serializers.BooleanField(required=False, default=False)
    revision_id = serializers.IntegerField(required=False)


class DownloadTemplateSerializer(serializers.Serializer):
    revision_id = serializers.IntegerField(
        help_text="The id of the revision of the user template that the user was "
        "shown. Its owner and the instance admins may download any revision. "
        "Anyone else downloads the public revision, or the latest one of a "
        "template that isn't public with the token of its private link."
    )


class TemplateArchiveSerializer(serializers.Serializer):
    url = serializers.URLField(
        help_text="The URL of the archive, which imports like a workspace export."
    )
    file_name = serializers.CharField(help_text="The name to save the archive as.")


class TemplateSerializer(serializers.ModelSerializer):
    """
    Serializes a template revision. The id, slug and keywords are the template's,
    so they are read from its root.
    """

    id = serializers.IntegerField(source="family_id", read_only=True)
    revision_id = serializers.IntegerField(
        source="id",
        read_only=True,
        help_text="The id of the serialized revision. Sent with an install, so that "
        "the template isn't installed if it was updated since.",
    )
    type = serializers.SerializerMethodField(
        help_text="Whether it's an official or a user template."
    )
    slug = serializers.SlugField(source="get_root.slug", read_only=True)
    keywords = serializers.CharField(source="get_root.keywords", read_only=True)
    author_name = serializers.SerializerMethodField(
        help_text="The first name of the author of a user template. Null for an "
        "official template or a deleted author."
    )
    is_default = serializers.SerializerMethodField(
        help_text="Indicates if the template must be selected by default. The "
        "web-frontend automatically selects the first `is_default` template "
        "that it can find."
    )

    class Meta:
        model = Template
        fields = (
            "id",
            "revision_id",
            "type",
            "name",
            "slug",
            "description",
            "icon",
            "keywords",
            "workspace_id",
            "is_default",
            "open_application",
            "author_name",
        )

    @extend_schema_field(serializers.ChoiceField(choices=Template.Type.choices))
    def get_type(self, instance):
        # A null `type` means official.
        return instance.type or Template.Type.OFFICIAL

    @extend_schema_field(OpenApiTypes.STR)
    def get_is_default(self, instance):
        return instance.get_root().slug == settings.DEFAULT_APPLICATION_TEMPLATES[0]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_author_name(self, instance: Template) -> Optional[str]:
        author = instance.get_root().author
        return None if author is None else author.first_name


class TemplateCategoriesSerializer(serializers.ModelSerializer):
    templates = TemplateSerializer(read_only=True, many=True)

    class Meta:
        model = TemplateCategory
        fields = ("id", "name", "templates")


class TemplateCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateCategory
        fields = ("id", "name")


class TemplateDetailSerializer(TemplateSerializer):
    """
    A template revision as the template page and the flat list show it, with
    whether the user who asks owns it. Needs the request in the context.
    """

    is_own = serializers.SerializerMethodField(
        help_text="Whether the authenticated user owns this user template."
    )
    updated_on = serializers.SerializerMethodField(
        help_text="When the content shown was last changed: the creation of the "
        "revision of a user template, the last update of an official one."
    )

    class Meta(TemplateSerializer.Meta):
        fields = TemplateSerializer.Meta.fields + ("is_own", "updated_on")

    def _is_owner(self, instance: Template) -> bool:
        request = self.context.get("request")
        # An anonymous user has no id, and only a user template has an owner.
        return (
            instance.type == Template.Type.USER
            and request is not None
            and request.user.is_authenticated
            and instance.get_root().owner_id == request.user.id
        )

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_own(self, instance: Template) -> bool:
        return self._is_owner(instance)

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_updated_on(self, instance: Template) -> str:
        # A revision isn't changed after it's created, an official template is.
        updated_on = (
            instance.created_on
            if instance.type == Template.Type.USER
            else instance.updated_on
        )
        return serializers.DateTimeField().to_representation(updated_on)


class TemplateListItemSerializer(TemplateDetailSerializer):
    """
    A revision of a template in the flat list, or opened by its slug. The fields
    marked as only shown to the owner of a user template are null for anyone else.
    """

    created_on = serializers.DateTimeField(source="get_root.created_on", read_only=True)
    categories = TemplateCategorySerializer(read_only=True, many=True)
    state = serializers.SerializerMethodField(
        help_text="The state of the template as shown to its owner, and to "
        "instance admins on the template page. Null for anyone else."
    )
    reason = serializers.SerializerMethodField(
        help_text="Why the template was rejected or blocked, if given. Only shown "
        "to its owner, and to instance admins on the template page."
    )
    can_make_public = serializers.SerializerMethodField(
        help_text="Whether making the template public lists it or sends it to "
        "review: it's not blocked, in review, or listed as it is. Only shown to its "
        "owner, null on listed rows."
    )
    make_public_needs_review = serializers.SerializerMethodField(
        help_text="Whether making the template public sends it to the review of "
        "an instance admin, because approval is required or an admin rejected it "
        "since it was last approved. Only shown to its owner, null on listed rows."
    )
    update_needs_review = serializers.SerializerMethodField(
        help_text="Whether an update of the template sends it to the review of an "
        "instance admin: when it's listed and approval is required or an admin "
        "rejected it since it was last approved, or when it's in review already. "
        "Only shown to its owner."
    )
    listed = serializers.SerializerMethodField(
        help_text="Whether a revision of the template is listed for everybody, also "
        "while a later one is in review or rejected. Only shown to its owner."
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
    private_link_token = serializers.SerializerMethodField(
        help_text="The token of the private link, null without one. Only shown to "
        "its owner."
    )

    class Meta(TemplateDetailSerializer.Meta):
        fields = TemplateDetailSerializer.Meta.fields + (
            "categories",
            "state",
            "reason",
            "can_make_public",
            "make_public_needs_review",
            "update_needs_review",
            "listed",
            "source_workspace_id",
            "source_application_ids",
            "install_count",
            "private_link_token",
            "created_on",
        )

    def _get_state(
        self, instance: Template
    ) -> Tuple[Optional[UserTemplateState], Optional[str]]:
        """
        The state of the template and the admin's reason, shown to its owner, and
        to instance admins when the context has `shows_state_to_staff`.

        :param instance: The template revision.
        :return: The state and the reason, None for anyone else.
        """

        request = self.context.get("request")
        shown_to_staff = (
            self.context.get("shows_state_to_staff", False)
            and instance.type == Template.Type.USER
            and request.user.is_staff
        )
        if not (shown_to_staff or self._is_owner(instance)):
            return None, None
        return UserTemplateHandler().get_template_state(instance)

    def _get_owner_metadata(self, instance):
        if not self._is_owner(instance):
            return None
        return UserTemplateHandler().get_template_metadata(instance)

    def _describes_latest_revision_to_owner(self, instance: Template) -> bool:
        """
        Whether the row is shown to its owner and isn't a listed row, which is the
        listed revision rather than the latest one that making public submits.

        :param instance: The template revision.
        :return: True if the fields about making it public apply to the row.
        """

        return self._is_owner(instance) and not self.context.get("listed")

    def _require_approval(self) -> bool:
        """
        Whether user templates need approval, read once per response.

        :return: The value of `Settings.user_templates_require_approval`.
        """

        if "require_approval" not in self.context:
            self.context["require_approval"] = (
                CoreHandler().get_settings().user_templates_require_approval
            )
        return self.context["require_approval"]

    @extend_schema_field(
        serializers.ChoiceField(choices=UserTemplateState.choices, allow_null=True)
    )
    def get_state(self, instance: Template) -> Optional[UserTemplateState]:
        state, _ = self._get_state(instance)
        return state

    @extend_schema_field(OpenApiTypes.STR)
    def get_reason(self, instance: Template) -> Optional[str]:
        _, reason = self._get_state(instance)
        return reason

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_can_make_public(self, instance: Template) -> Optional[bool]:
        if not self._describes_latest_revision_to_owner(instance):
            return None
        return UserTemplateHandler().make_public_submits(instance)

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_make_public_needs_review(self, instance: Template) -> Optional[bool]:
        if not self._describes_latest_revision_to_owner(instance):
            return None
        return UserTemplateHandler().make_public_needs_review(
            instance, self._require_approval()
        )

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_update_needs_review(self, instance: Template) -> Optional[bool]:
        if not self._is_owner(instance):
            return None
        return UserTemplateHandler().update_needs_review(
            instance, self._require_approval()
        )

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_listed(self, instance: Template) -> Optional[bool]:
        if not self._is_owner(instance):
            return None
        return UserTemplateHandler().is_listed(instance)

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

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_private_link_token(self, instance):
        if not self._is_owner(instance):
            return None
        return instance.get_root().private_link_token
