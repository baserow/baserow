from typing import Literal, Optional

from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel

# =============================================================================
# Common Types
# =============================================================================

# Available font families in Baserow builder
FontFamily = Literal[
    "inter",
    "arial",
    "verdana",
    "tahoma",
    "trebuchet_ms",
    "times_new_roman",
    "georgia",
    "garamond",
    "courier_new",
    "brush_script_mt",
]

FontWeight = Literal["regular", "medium", "semi_bold", "bold"]
HorizontalAlignment = Literal["left", "center", "right"]


# =============================================================================
# Color Theme
# =============================================================================


class ColorThemeUpdate(BaseModel):
    """Color theme settings for the application."""

    primary_color: Optional[str] = Field(
        default=None,
        description="Primary brand color (hex with alpha, e.g., '#5190efff')",
    )
    secondary_color: Optional[str] = Field(
        default=None,
        description="Secondary brand color (hex with alpha)",
    )
    border_color: Optional[str] = Field(
        default=None,
        description="Default border color (hex with alpha)",
    )
    main_success_color: Optional[str] = Field(
        default=None,
        description="Success state color (hex with alpha)",
    )
    main_warning_color: Optional[str] = Field(
        default=None,
        description="Warning state color (hex with alpha)",
    )
    main_error_color: Optional[str] = Field(
        default=None,
        description="Error state color (hex with alpha)",
    )


# =============================================================================
# Typography Theme
# =============================================================================


class TextDecorationUpdate(BaseModel):
    """Text decoration flags."""

    underline: Optional[bool] = None
    strike: Optional[bool] = None
    uppercase: Optional[bool] = None
    italic: Optional[bool] = None


class HeadingStyleUpdate(BaseModel):
    """Style settings for a heading level (1-6)."""

    font_family: Optional[FontFamily] = None
    font_size: Optional[int] = Field(default=None, ge=8, le=72)
    font_weight: Optional[FontWeight] = None
    text_color: Optional[str] = Field(
        default=None,
        description="Text color (hex with alpha or 'primary'/'secondary')",
    )
    text_alignment: Optional[HorizontalAlignment] = None
    text_decoration: Optional[TextDecorationUpdate] = None


class TypographyThemeUpdate(BaseModel):
    """Typography theme settings for body text and headings."""

    # Body text
    body_font_family: Optional[FontFamily] = None
    body_font_size: Optional[int] = Field(default=None, ge=8, le=72)
    body_font_weight: Optional[FontWeight] = None
    body_text_color: Optional[str] = None
    body_text_alignment: Optional[HorizontalAlignment] = None

    # Headings 1-6
    heading_1: Optional[HeadingStyleUpdate] = None
    heading_2: Optional[HeadingStyleUpdate] = None
    heading_3: Optional[HeadingStyleUpdate] = None
    heading_4: Optional[HeadingStyleUpdate] = None
    heading_5: Optional[HeadingStyleUpdate] = None
    heading_6: Optional[HeadingStyleUpdate] = None


# =============================================================================
# Button Theme
# =============================================================================


class ButtonThemeUpdate(BaseModel):
    """Button theme settings."""

    font_family: Optional[FontFamily] = None
    font_size: Optional[int] = Field(default=None, ge=8, le=72)
    font_weight: Optional[FontWeight] = None
    alignment: Optional[HorizontalAlignment] = Field(
        default=None,
        description="Button alignment within its container",
    )
    text_alignment: Optional[HorizontalAlignment] = Field(
        default=None,
        description="Text alignment within the button",
    )
    width: Optional[Literal["auto", "full", "full-width"]] = None
    background_color: Optional[str] = Field(
        default=None,
        description="Background color (use 'primary' for theme color or hex)",
    )
    text_color: Optional[str] = None
    border_color: Optional[str] = Field(
        default=None,
        description="Border color (use 'border' for theme color or hex)",
    )
    border_size: Optional[int] = Field(default=None, ge=0)
    border_radius: Optional[int] = Field(default=None, ge=0)
    vertical_padding: Optional[int] = Field(default=None, ge=0)
    horizontal_padding: Optional[int] = Field(default=None, ge=0)
    hover_background_color: Optional[str] = None
    hover_text_color: Optional[str] = None
    hover_border_color: Optional[str] = None
    active_background_color: Optional[str] = None
    active_text_color: Optional[str] = None
    active_border_color: Optional[str] = None


# =============================================================================
# Link Theme
# =============================================================================


class LinkThemeUpdate(BaseModel):
    """Link theme settings."""

    font_family: Optional[FontFamily] = None
    font_size: Optional[int] = Field(default=None, ge=8, le=72)
    font_weight: Optional[FontWeight] = None
    text_alignment: Optional[HorizontalAlignment] = None
    text_color: Optional[str] = Field(
        default=None,
        description="Link text color (use 'primary' for theme color or hex)",
    )
    hover_text_color: Optional[str] = None
    active_text_color: Optional[str] = None
    default_text_decoration: Optional[TextDecorationUpdate] = None
    hover_text_decoration: Optional[TextDecorationUpdate] = None
    active_text_decoration: Optional[TextDecorationUpdate] = None


# =============================================================================
# Image Theme
# =============================================================================


class ImageThemeUpdate(BaseModel):
    """Image theme settings."""

    alignment: Optional[HorizontalAlignment] = None
    max_width: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Max width as percentage (0-100)",
    )
    max_height: Optional[int] = Field(
        default=None,
        ge=5,
        le=3000,
        description="Max height in pixels (5-3000)",
    )
    border_radius: Optional[int] = Field(default=None, ge=0, le=100)
    constraint: Optional[Literal["cover", "contain", "full-width"]] = None


# =============================================================================
# Page Theme
# =============================================================================


class PageThemeUpdate(BaseModel):
    """Page background theme settings."""

    background_color: Optional[str] = None
    background_mode: Optional[Literal["tile", "fill", "fit"]] = None


# =============================================================================
# Input Theme
# =============================================================================


class InputThemeUpdate(BaseModel):
    """Form input theme settings."""

    # Label styling
    label_font_family: Optional[FontFamily] = None
    label_text_color: Optional[str] = None
    label_font_size: Optional[int] = Field(default=None, ge=8, le=72)
    label_font_weight: Optional[FontWeight] = None

    # Input field styling
    input_font_family: Optional[FontFamily] = None
    input_font_size: Optional[int] = Field(default=None, ge=8, le=72)
    input_font_weight: Optional[FontWeight] = None
    input_text_color: Optional[str] = None
    input_background_color: Optional[str] = None
    input_border_color: Optional[str] = None
    input_border_size: Optional[int] = Field(default=None, ge=0)
    input_border_radius: Optional[int] = Field(default=None, ge=0)
    input_vertical_padding: Optional[int] = Field(default=None, ge=0)
    input_horizontal_padding: Optional[int] = Field(default=None, ge=0)


# =============================================================================
# Table Theme
# =============================================================================


class TableThemeUpdate(BaseModel):
    """Table theme settings."""

    # Table border
    border_color: Optional[str] = None
    border_size: Optional[int] = Field(default=None, ge=0)
    border_radius: Optional[int] = Field(default=None, ge=0)

    # Header styling
    header_background_color: Optional[str] = None
    header_text_color: Optional[str] = None
    header_font_size: Optional[int] = Field(default=None, ge=8, le=72)
    header_font_weight: Optional[FontWeight] = None
    header_font_family: Optional[FontFamily] = None
    header_text_alignment: Optional[HorizontalAlignment] = None

    # Cell styling
    cell_background_color: Optional[str] = None
    cell_alternate_background_color: Optional[str] = None
    cell_alignment: Optional[HorizontalAlignment] = None
    cell_vertical_padding: Optional[int] = Field(default=None, ge=0)
    cell_horizontal_padding: Optional[int] = Field(default=None, ge=0)

    # Separator styling
    vertical_separator_color: Optional[str] = None
    vertical_separator_size: Optional[int] = Field(default=None, ge=0)
    horizontal_separator_color: Optional[str] = None
    horizontal_separator_size: Optional[int] = Field(default=None, ge=0)
