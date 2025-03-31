from typing import TYPE_CHECKING, List

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.api.pages.serializers import PageSerializer
from baserow.contrib.builder.api.theme.serializers import (
    CombinedThemeConfigBlocksSerializer,
    serialize_builder_theme,
)
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.handler import PageHandler

if TYPE_CHECKING:
    from baserow.contrib.builder.application_types import BuilderApplicationType


class BuilderSerializer(serializers.ModelSerializer):
    """
    The builder serializer.

    👉 Mind to update the
    baserow.contrib.builder.api.domains.serializer.PublicBuilderSerializer
    when you update this one.
    """

    pages = serializers.SerializerMethodField(
        help_text="This field is specific to the `builder` application and contains "
        "an array of pages that are in the builder."
    )
    theme = serializers.SerializerMethodField(
        help_text="This field is specific to the `builder` application and contains "
        "the theme settings."
    )

    class Meta:
        model = Builder
        ref_name = "BuilderApplication"
        fields = ("id", "name", "pages", "theme", "integrations", "user_sources")

    @extend_schema_field(PageSerializer(many=True))
    def get_pages(self, instance: Builder) -> List:
        """
        Serializes the builder's pages. Uses pre-fetched pages attribute if available;
        otherwise, retrieves them from the database using the appropriate context and
        application type to avoid unnecessary queries when serializing nested fields.

        :param instance: The builder instance.
        :return: A list of serialized pages.
        """

        pages = getattr(instance, "pages", None)
        if pages is None:
            ctx = self.context
            user = ctx.get("user", None)
            request = ctx.get("request")
            if user is None and hasattr(request, "user"):
                user = request.user if request.user.is_authenticated else None

            builder_type: "BuilderApplicationType" = instance.get_type()
            pages = builder_type.fetch_pages_to_serialize(instance, user)

        return PageSerializer(pages, many=True).data

    @extend_schema_field(CombinedThemeConfigBlocksSerializer())
    def get_theme(self, instance):
        return serialize_builder_theme(instance)

    def validate_login_page_id(self, value: int) -> int:
        """Validate the Builder's login_page."""

        # Although only possible via the API, setting the login_page to the
        # shared page shouldn't be allowed because the shared page isn't
        # a real page.
        if value and PageHandler().get_page(value).shared:
            raise DRFValidationError(
                detail="The login page cannot be a shared page.",
                code="invalid_login_page_id",
            )

        return value
