from typing import Any, Dict, Optional
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db.models import QuerySet

from rest_framework import serializers

from baserow.contrib.builder.models import Builder
from baserow.core.user_files.handler import UserFileHandler

from .models import (
    ButtonThemeConfigBlock,
    ColorThemeConfigBlock,
    ImageThemeConfigBlock,
    InputThemeConfigBlock,
    LinkThemeConfigBlock,
    PageThemeConfigBlock,
    TableThemeConfigBlock,
    ThemeConfigBlock,
    TypographyThemeConfigBlock,
)
from .registries import ThemeConfigBlockType


class ColorThemeConfigBlockType(ThemeConfigBlockType):
    type = "color"
    model_class = ColorThemeConfigBlock


class TypographyThemeConfigBlockType(ThemeConfigBlockType):
    type = "typography"
    model_class = TypographyThemeConfigBlock

    @property
    def serializer_field_overrides(self):
        return {
            "heading_1_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
            "heading_2_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
            "heading_3_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
            "heading_4_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
            "heading_5_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
            "heading_6_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
        }

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
        **kwargs,
    ):
        # Translate from old color property names to new names for compat with templates
        for level in range(3):
            if f"heading_{level+1}_color" in serialized_values:
                serialized_values[
                    f"heading_{level+1}_text_color"
                ] = serialized_values.pop(f"heading_{level+1}_color")

        return super().import_serialized(
            parent, serialized_values, id_mapping, files_zip, storage, cache
        )


class ButtonThemeConfigBlockType(ThemeConfigBlockType):
    type = "button"
    model_class = ButtonThemeConfigBlock


class LinkThemeConfigBlockType(ThemeConfigBlockType):
    type = "link"
    model_class = LinkThemeConfigBlock

    @property
    def serializer_field_overrides(self):
        return {
            "link_default_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Default text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
            "link_hover_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Hover text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
            "link_active_text_decoration": serializers.ListField(
                child=serializers.BooleanField(),
                help_text="Active text decoration: [underline, stroke, uppercase, italic]",
                required=False,
            ),
        }


class ImageThemeConfigBlockType(ThemeConfigBlockType):
    type = "image"
    model_class = ImageThemeConfigBlock

    @property
    def serializer_field_overrides(self):
        # For some reason if we don't allow_null=False here the null value is returned
        return {
            "image_max_height": serializers.IntegerField(
                allow_null=False,
                required=False,
                help_text="The image max height",
            ),
        }

    @property
    def request_serializer_field_overrides(self):
        return {
            "image_max_height": serializers.IntegerField(
                allow_null=True,
                required=False,
                default=None,
                help_text="The image max height",
            ),
        }


class PageThemeConfigBlockType(ThemeConfigBlockType):
    type = "page"
    model_class = PageThemeConfigBlock

    def get_property_names(self):
        """
        Let's replace the page_background_file property with page_background_file_id.
        """

        return [
            n if n != "page_background_file" else "page_background_file_id"
            for n in super().get_property_names()
        ]

    @property
    def serializer_field_overrides(self):
        from baserow.api.user_files.serializers import UserFileField
        from baserow.contrib.builder.api.validators import image_file_validation

        return {
            "page_background_file": UserFileField(
                allow_null=True,
                required=False,
                help_text="The image file",
                validators=[image_file_validation],
            ),
        }

    def serialize_property(
        self,
        theme_config_block: ThemeConfigBlock,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        You can customize the behavior of the serialization of a property with this
        hook.
        """

        if prop_name == "page_background_file_id":
            return UserFileHandler().export_user_file(
                theme_config_block.page_background_file,
                files_zip=files_zip,
                storage=storage,
                cache=cache,
            )

        return super().serialize_property(
            theme_config_block,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def deserialize_property(
        self,
        prop_name: str,
        value,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        if prop_name == "page_background_file_id":
            user_file = UserFileHandler().import_user_file(
                value, files_zip=files_zip, storage=storage
            )
            if user_file:
                return user_file.id
            return None

        return value

    def enhance_queryset(self, queryset: QuerySet[Builder]) -> QuerySet[Builder]:
        return queryset.select_related(
            f"{self.related_name_in_builder_model}__page_background_file"
        )


class InputThemeConfigBlockType(ThemeConfigBlockType):
    type = "input"
    model_class = InputThemeConfigBlock


class TableThemeConfigBlockType(ThemeConfigBlockType):
    type = "table"
    model_class = TableThemeConfigBlock
