import pytest

from baserow.contrib.builder.api.theme.serializers import (
    DynamicConfigBlockSerializer,
    serialize_builder_theme,
)
from baserow.contrib.builder.theme.theme_config_block_types import (
    ButtonThemeConfigBlockType,
    LinkThemeConfigBlockType,
    TypographyThemeConfigBlockType,
)


def test_dynamic_config_block_serializer_supports_type_names_per_property():
    serializer = DynamicConfigBlockSerializer(
        property_names=["menu", "burger"],
        theme_config_block_type_names=[
            [
                ButtonThemeConfigBlockType.type,
                LinkThemeConfigBlockType.type,
            ],
            [TypographyThemeConfigBlockType.type],
        ],
    )

    menu_fields = serializer.fields["menu"].fields
    burger_fields = serializer.fields["burger"].fields

    assert "button_background_color" in menu_fields
    assert "link_text_color" in menu_fields
    assert "body_font_size" not in menu_fields

    assert "body_font_size" in burger_fields
    assert "button_background_color" not in burger_fields
    assert "link_text_color" not in burger_fields


@pytest.mark.django_db
def test_serialize_builder_theme_serializes_user_file_fields(data_fixture):
    """
    The reused theme config block serializers must keep serializing user file fields,
    like the page background image, which only serialize their value when the parent
    serializer has an instance.
    """

    builder = data_fixture.create_builder_application()
    user_file = data_fixture.create_user_file(original_extension="png")
    builder.pagethemeconfigblock.page_background_file = user_file
    builder.pagethemeconfigblock.save()

    theme = serialize_builder_theme(builder)

    assert theme["page_background_file"]["name"] == user_file.name
