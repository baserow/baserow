from baserow.contrib.builder.api.theme.serializers import DynamicConfigBlockSerializer
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
