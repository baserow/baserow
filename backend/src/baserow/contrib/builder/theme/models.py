from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from baserow.contrib.builder.constants import (
    BACKGROUND_IMAGE_MODES,
    COLOR_FIELD_MAX_LENGTH,
    WIDTHS,
    FontWeights,
    HorizontalAlignments,
)
from baserow.core.fields import AutoOneToOneField, MultipleFlagField
from baserow.core.user_files.models import UserFile


class ThemeConfigBlock(models.Model):
    builder = AutoOneToOneField(
        "builder.Builder",
        on_delete=models.CASCADE,
        related_name="%(class)s",
    )

    class Meta:
        abstract = True


class ColorThemeConfigBlock(ThemeConfigBlock):
    primary_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#5190efff"
    )
    secondary_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#0eaa42ff"
    )
    border_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#d7d8d9ff"
    )
    main_success_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#12D452"
    )
    main_warning_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#FCC74A"
    )
    main_error_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#FF5A4A"
    )
    custom_colors = models.JSONField(default=list, db_default=[])


class TypographyThemeConfigBlock(ThemeConfigBlock):
    body_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    body_font_size = models.SmallIntegerField(default=14)
    body_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.REGULAR,
        db_default=FontWeights.REGULAR,
    )
    body_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#070810ff"
    )
    body_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    heading_1_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    heading_1_font_size = models.SmallIntegerField(default=24)
    heading_1_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.BOLD,
        db_default=FontWeights.BOLD,
    )
    heading_1_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#070810ff"
    )
    heading_1_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    heading_1_text_decoration = MultipleFlagField(
        default=[False, False, False, False],
        num_flags=4,
        db_default="0000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )
    heading_2_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    heading_2_font_size = models.SmallIntegerField(default=20)
    heading_2_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.SEMI_BOLD,
        db_default=FontWeights.SEMI_BOLD,
    )
    heading_2_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#070810ff"
    )
    heading_2_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    heading_2_text_decoration = MultipleFlagField(
        default=[False, False, False, False],
        num_flags=4,
        db_default="0000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )
    heading_3_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    heading_3_font_size = models.SmallIntegerField(default=16)
    heading_3_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.MEDIUM,
        db_default=FontWeights.MEDIUM,
    )
    heading_3_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#070810ff"
    )
    heading_3_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    heading_3_text_decoration = MultipleFlagField(
        default=[False, False, False, False],
        num_flags=4,
        db_default="0000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )
    heading_4_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    heading_4_font_size = models.SmallIntegerField(default=16)
    heading_4_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.MEDIUM,
        db_default=FontWeights.MEDIUM,
    )
    heading_4_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#070810ff"
    )
    heading_4_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    heading_4_text_decoration = MultipleFlagField(
        default=[False, False, False, False],
        num_flags=4,
        db_default="0000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )
    heading_5_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    heading_5_font_size = models.SmallIntegerField(default=14)
    heading_5_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.REGULAR,
        db_default=FontWeights.REGULAR,
    )
    heading_5_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#070810ff"
    )
    heading_5_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    heading_5_text_decoration = MultipleFlagField(
        default=[False, False, False, False],
        num_flags=4,
        db_default="0000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )
    heading_6_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    heading_6_font_size = models.SmallIntegerField(default=14)
    heading_6_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.REGULAR,
        db_default=FontWeights.REGULAR,
    )
    heading_6_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH, default="#202128"
    )
    heading_6_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    heading_6_text_decoration = MultipleFlagField(
        default=[False, False, False, False],
        num_flags=4,
        db_default="0000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )


class ButtonThemeConfigBlockMixin(models.Model):
    button_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    button_font_size = models.SmallIntegerField(default=13)
    button_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.REGULAR,
        db_default=FontWeights.REGULAR,
    )
    button_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    button_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.CENTER,
    )
    button_width = models.CharField(
        choices=WIDTHS.choices,
        max_length=10,
        default=WIDTHS.AUTO,
    )
    button_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="primary",
        blank=True,
        help_text="The background color of buttons",
    )
    button_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#ffffffff",
        blank=True,
        help_text="The text color of buttons",
    )
    button_border_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="border",
        blank=True,
        help_text="The border color of buttons",
    )
    button_border_size = models.SmallIntegerField(
        default=0, help_text="Button border size"
    )
    button_border_radius = models.SmallIntegerField(
        default=4, help_text="Button border radius"
    )
    button_vertical_padding = models.SmallIntegerField(
        default=12, help_text="Button vertical padding"
    )
    button_horizontal_padding = models.SmallIntegerField(
        default=12, help_text="Button horizontal padding"
    )
    button_hover_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#96baf6ff",
        blank=True,
        help_text="The background color of buttons when hovered",
    )
    button_hover_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#ffffffff",
        blank=True,
        help_text="The text color of buttons when hovered",
    )
    button_hover_border_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="border",
        blank=True,
        help_text="The border color of buttons when hovered",
    )
    button_active_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#4783db",
        blank=True,
        help_text="The background color of buttons when active",
    )
    button_active_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#ffffffff",
        blank=True,
        help_text="The text color of buttons when active",
    )
    button_active_border_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#275d9f",
        blank=True,
        help_text="The border color of buttons when active",
    )

    class Meta:
        abstract = True


class ButtonThemeConfigBlock(ButtonThemeConfigBlockMixin, ThemeConfigBlock):
    pass


class LinkThemeConfigBlockMixin(models.Model):
    link_font_family = models.CharField(
        max_length=250,
        default="inter",
    )
    link_font_size = models.SmallIntegerField(default=13)
    link_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.REGULAR,
        db_default=FontWeights.REGULAR,
    )
    link_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    link_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="primary",
        blank=True,
        help_text="The text color of links",
    )
    link_hover_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#96baf6ff",
        blank=True,
        help_text="The hover color of links when hovered",
    )
    link_active_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#275d9f",
        blank=True,
        help_text="The hover color of links when active",
    )
    link_default_text_decoration = MultipleFlagField(
        default=[True, False, False, False],
        num_flags=4,
        db_default="1000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )
    link_hover_text_decoration = MultipleFlagField(
        default=[True, False, False, False],
        num_flags=4,
        db_default="1000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )
    link_active_text_decoration = MultipleFlagField(
        default=[True, False, False, False],
        num_flags=4,
        db_default="1000",
        help_text=("The text decoration flags [underline, strike, uppercase, italic]"),
    )

    class Meta:
        abstract = True


class LinkThemeConfigBlock(LinkThemeConfigBlockMixin, ThemeConfigBlock):
    pass


class ImageThemeConfigBlock(ThemeConfigBlock):
    class IMAGE_CONSTRAINT_TYPES(models.TextChoices):
        COVER = "cover"
        CONTAIN = "contain"
        FULL_WIDTH = "full-width"

    image_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )

    image_max_width = models.PositiveIntegerField(
        help_text="The max-width for this image element.",
        default=100,
        validators=[
            MinValueValidator(0, message="Value cannot be less than 0."),
            MaxValueValidator(100, message="Value cannot be greater than 100."),
        ],
    )

    image_max_height = models.PositiveIntegerField(
        null=True,
        help_text="The max-height for this image element.",
        validators=[
            MinValueValidator(5, message="Value cannot be less than 5."),
            MaxValueValidator(3000, message="Value cannot be greater than 3000."),
        ],
    )

    image_border_radius = models.SmallIntegerField(
        help_text="The border radius for this image element.",
        validators=[
            MinValueValidator(0, message="Value cannot be less than 0."),
            MaxValueValidator(100, message="Value cannot be greater than 100."),
        ],
        default=0,
        db_default=0,
    )

    image_constraint = models.CharField(
        help_text="The image constraint to apply to this image",
        choices=IMAGE_CONSTRAINT_TYPES.choices,
        max_length=32,
        default=IMAGE_CONSTRAINT_TYPES.CONTAIN,
    )


class PageThemeConfigBlock(ThemeConfigBlock):
    """
    Theme for pages.
    """

    page_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#ffffffff",
        blank=True,
        help_text="The background color of the page",
    )

    page_background_file = models.ForeignKey(
        UserFile,
        null=True,
        on_delete=models.SET_NULL,
        related_name="page_background_image_file",
        help_text="An image file uploaded by the user to be used as page background",
    )

    page_background_mode = models.CharField(
        help_text="The mode of the background image",
        choices=BACKGROUND_IMAGE_MODES.choices,
        max_length=32,
        default=BACKGROUND_IMAGE_MODES.TILE,
    )


class InputThemeConfigBlock(ThemeConfigBlock):
    """
    Theme for inputs.
    """

    label_font_family = models.CharField(
        max_length=250,
        default="inter",
        help_text="The font family of the label",
    )
    label_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#070810FF",
        blank=True,
        help_text="The text color of the label",
    )
    label_font_size = models.SmallIntegerField(
        default=13,
        help_text="The font size of the label",
    )
    label_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.MEDIUM,
        db_default=FontWeights.MEDIUM,
    )

    input_font_family = models.CharField(
        max_length=250,
        default="inter",
        help_text="The font family of the input",
    )
    input_font_size = models.SmallIntegerField(default=13)
    input_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.REGULAR,
        db_default=FontWeights.REGULAR,
    )
    input_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#070810FF",
        blank=True,
        help_text="The text color of the input",
    )
    input_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#FFFFFFFF",
        blank=True,
        help_text="The background color of the input",
    )
    input_border_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#000000FF",
        blank=True,
        help_text="The color of the input border",
    )
    input_border_size = models.SmallIntegerField(
        default=1, help_text="Input border size"
    )
    input_border_radius = models.SmallIntegerField(
        default=0, help_text="Input border radius"
    )
    input_vertical_padding = models.SmallIntegerField(
        default=8, help_text="Input vertical padding"
    )
    input_horizontal_padding = models.SmallIntegerField(
        default=12, help_text="Input horizontal padding"
    )


class TableThemeConfigBlock(ThemeConfigBlock):
    """
    Theme for tables.
    """

    # Table styles
    table_border_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#000000FF",
        blank=True,
        help_text="The color of the table border",
    )
    table_border_size = models.SmallIntegerField(
        default=1, help_text="Table border size"
    )
    table_border_radius = models.SmallIntegerField(
        default=0, help_text="Table border radius"
    )

    # Header styles
    table_header_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#edededff",
        blank=True,
        help_text="The background color of the table header cells",
    )
    table_header_text_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#000000ff",
        blank=True,
        help_text="The text color of the table header cells",
    )
    table_header_font_size = models.SmallIntegerField(
        default=13,
        help_text="The font size of the header cells",
    )
    table_header_font_weight = models.CharField(
        choices=FontWeights.choices,
        max_length=11,
        default=FontWeights.SEMI_BOLD,
        db_default=FontWeights.SEMI_BOLD,
    )
    table_header_font_family = models.CharField(
        max_length=250,
        default="inter",
        help_text="The font family of the table header cells",
    )
    table_header_text_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )

    # Cell styles
    table_cell_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="transparent",
        blank=True,
        help_text="The background color of the table cells",
    )

    table_cell_alternate_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="transparent",
        blank=True,
        help_text="The alternate background color of the table cells",
    )
    table_cell_alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )
    table_cell_vertical_padding = models.SmallIntegerField(
        default=10, help_text="Table cell vertical padding"
    )
    table_cell_horizontal_padding = models.SmallIntegerField(
        default=20, help_text="Table cell horizontal padding"
    )

    # Separator styles
    table_vertical_separator_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#000000FF",
        blank=True,
        help_text="The color of the table vertical separator",
    )
    table_vertical_separator_size = models.SmallIntegerField(
        default=0, help_text="Table vertical separator size"
    )

    table_horizontal_separator_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#000000FF",
        blank=True,
        help_text="The color of the table horizontal separator",
    )
    table_horizontal_separator_size = models.SmallIntegerField(
        default=1, help_text="Table horizontal separator size"
    )
