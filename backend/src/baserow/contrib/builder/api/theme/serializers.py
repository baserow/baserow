from functools import cache

from loguru import logger
from rest_framework import serializers

from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.theme.registries import theme_config_block_registry


class DynamicConfigBlockSerializer(serializers.Serializer):
    """
    Style overrides for this element.
    """

    def __init__(
        self,
        *args,
        property_name=None,
        theme_config_block_type_name=None,
        serializer_kwargs=None,
        request_serializer=False,
        **kwargs,
    ):
        if property_name is None:
            raise ValueError("Missing property_name parameter")
        if theme_config_block_type_name is None:
            raise ValueError("Missing theme_block_type parameter")

        super().__init__(*args, **kwargs)

        if serializer_kwargs is None:
            serializer_kwargs = {}

        if not isinstance(property_name, list):
            property_name = [property_name]

        if not isinstance(theme_config_block_type_name, list):
            theme_config_block_type_name = [theme_config_block_type_name]

        for prop, type_names in zip(property_name, theme_config_block_type_name):
            if not isinstance(type_names, list):
                type_names = [type_names]

            config_blocks = (
                theme_config_block_registry.get(type_name) for type_name in type_names
            )
            serializer_class = combine_theme_config_blocks_serializer_class(
                config_blocks,
                request_serializer=request_serializer,
                name="SubConfigBlockSerializer",
            )

            self.fields[prop] = serializer_class(**serializer_kwargs)

        all_type_names = "".join(
            [
                "And".join(sub.capitalize() for sub in p)
                if isinstance(p, list)
                else p.capitalize()
                for p in theme_config_block_type_name
            ]
        )

        # Dynamically create the Meta class with ref name to prevent collision
        class DynamicMeta:
            type_names = all_type_names
            ref_name = f"{all_type_names}ConfigBlockSerializer"
            meta_ref_name = f"{all_type_names}ConfigBlockSerializer"

        self.Meta = DynamicMeta


def serialize_builder_theme(builder: Builder) -> dict:
    """
    A helper function that serializes all theme properties of the provided builder.

    :param builder: The builder that must be serialized.
    :return: The serialized theme properties.
    """

    theme = {}

    for theme_config_block in theme_config_block_registry.get_all():
        serializer_class = theme_config_block.get_serializer_class()
        serializer = serializer_class(
            getattr(builder, theme_config_block.related_name_in_builder_model),
            source=theme_config_block.related_name_in_builder_model,
        )
        theme.update(**serializer.data)

    return theme


def combine_theme_config_blocks_serializer_class(
    theme_config_blocks,
    request_serializer=False,
    name="CombinedThemeConfigBlocksSerializer",
) -> serializers.Serializer:
    """
    This helper function generates one single serializer that contains all the fields
    of all the theme config blocks. The API always communicates all theme properties
    flat in one single object.

    :return: The generated serializer.
    """

    attrs = {}

    for theme_config_block in theme_config_blocks:
        serializer = theme_config_block.get_serializer_class(
            request_serializer=request_serializer
        )
        serializer_fields = serializer().get_fields()

        for name, field in serializer_fields.items():
            attrs[name] = field

    class Meta:
        ref_name = "".join(t.type.capitalize() for t in theme_config_blocks) + name
        meta_ref_name = "".join(t.type.capitalize() for t in theme_config_blocks) + name

    attrs["Meta"] = Meta

    class_object = type(name, (serializers.Serializer,), attrs)

    return class_object


@cache
def get_combined_theme_config_blocks_serializer_class(
    request_serializer=False,
) -> serializers.Serializer:
    """
    This helper function generates one single serializer that contains all the fields
    of all the theme config blocks. The API always communicates all theme properties
    flat in one single object.

    :return: The generated serializer.
    """

    if len(theme_config_block_registry.registry.values()) == 0:
        logger.warning(
            "The theme config block types appear to be empty. This module is probably "
            "imported before the theme config blocks have been registered."
        )

    return combine_theme_config_blocks_serializer_class(
        theme_config_block_registry.get_all(), request_serializer=request_serializer
    )


CombinedThemeConfigBlocksSerializer = (
    get_combined_theme_config_blocks_serializer_class()
)

CombinedThemeConfigBlocksRequestSerializer = (
    get_combined_theme_config_blocks_serializer_class(request_serializer=True)
)
