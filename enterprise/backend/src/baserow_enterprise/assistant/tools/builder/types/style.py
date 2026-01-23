from typing import Literal, Optional

from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel

from .theme import FontFamily, FontWeight, HorizontalAlignment

# =============================================================================
# Element Style Configuration
# =============================================================================


class ElementStyleConfig(BaseModel):
    """
    Common styling options for all elements.

    All properties are optional - only set properties will be applied.
    """

    # Border settings (per side)
    border_top_color: Optional[str] = Field(
        default=None,
        description="Top border color (hex or 'border' for theme color)",
    )
    border_top_size: Optional[int] = Field(default=None, ge=0)
    border_bottom_color: Optional[str] = None
    border_bottom_size: Optional[int] = Field(default=None, ge=0)
    border_left_color: Optional[str] = None
    border_left_size: Optional[int] = Field(default=None, ge=0)
    border_right_color: Optional[str] = None
    border_right_size: Optional[int] = Field(default=None, ge=0)

    # Padding (per side, in pixels)
    padding_top: Optional[int] = Field(default=None, ge=0)
    padding_bottom: Optional[int] = Field(default=None, ge=0)
    padding_left: Optional[int] = Field(default=None, ge=0)
    padding_right: Optional[int] = Field(default=None, ge=0)

    # Margin (per side, in pixels)
    margin_top: Optional[int] = Field(default=None, ge=0)
    margin_bottom: Optional[int] = Field(default=None, ge=0)
    margin_left: Optional[int] = Field(default=None, ge=0)
    margin_right: Optional[int] = Field(default=None, ge=0)

    # Border and background radius
    border_radius: Optional[int] = Field(default=None, ge=0)
    background_radius: Optional[int] = Field(default=None, ge=0)

    # Background
    background: Optional[Literal["none", "color", "image"]] = None
    background_color: Optional[str] = Field(
        default=None,
        description="Background color (hex with alpha)",
    )
    background_mode: Optional[Literal["tile", "fill", "fit"]] = None

    # Width
    width: Optional[Literal["full", "full-width", "normal", "medium", "small"]] = None

    def to_orm_kwargs(self) -> dict:
        """Convert style config to ORM kwargs with style_ prefix."""
        kwargs = {}
        for key, value in self.model_dump(exclude_none=True).items():
            kwargs[f"style_{key}"] = value
        return kwargs


# =============================================================================
# Element Theme Overrides
# =============================================================================


class ElementThemeOverrides(BaseModel):
    """
    Theme property overrides for a specific element.

    These allow overriding theme settings at the element level.
    The available properties depend on the element type.
    """

    # Typography overrides (for heading, text elements)
    heading_1_text_color: Optional[str] = None
    heading_1_font_size: Optional[int] = None
    heading_1_font_family: Optional[FontFamily] = None
    heading_1_font_weight: Optional[FontWeight] = None
    heading_1_text_alignment: Optional[HorizontalAlignment] = None

    heading_2_text_color: Optional[str] = None
    heading_2_font_size: Optional[int] = None
    heading_2_font_family: Optional[FontFamily] = None
    heading_2_font_weight: Optional[FontWeight] = None
    heading_2_text_alignment: Optional[HorizontalAlignment] = None

    heading_3_text_color: Optional[str] = None
    heading_3_font_size: Optional[int] = None
    heading_3_font_family: Optional[FontFamily] = None
    heading_3_font_weight: Optional[FontWeight] = None
    heading_3_text_alignment: Optional[HorizontalAlignment] = None

    # Button overrides (for button, form_container elements)
    button_background_color: Optional[str] = None
    button_text_color: Optional[str] = None
    button_border_color: Optional[str] = None
    button_border_size: Optional[int] = None
    button_border_radius: Optional[int] = None
    button_alignment: Optional[HorizontalAlignment] = None
    button_text_alignment: Optional[HorizontalAlignment] = None
    button_vertical_padding: Optional[int] = None
    button_horizontal_padding: Optional[int] = None

    # Link overrides (for link elements)
    link_text_color: Optional[str] = None
    link_hover_text_color: Optional[str] = None
    link_text_alignment: Optional[HorizontalAlignment] = None

    # Input overrides (for form input elements)
    input_background_color: Optional[str] = None
    input_text_color: Optional[str] = None
    input_border_color: Optional[str] = None
    input_border_size: Optional[int] = None
    input_border_radius: Optional[int] = None

    # Image overrides (for image elements)
    image_alignment: Optional[HorizontalAlignment] = None
    image_max_width: Optional[int] = None
    image_max_height: Optional[int] = None

    # Table overrides (for table elements)
    table_border_color: Optional[str] = None
    table_border_size: Optional[int] = None
    table_header_background_color: Optional[str] = None
    table_header_text_color: Optional[str] = None
    table_cell_background_color: Optional[str] = None


# =============================================================================
# Element Update
# =============================================================================


class ElementUpdate(BaseModel):
    """
    Update specification for an existing element.

    Only provided fields will be updated.
    """

    element_id: int = Field(..., description="ID of the element to update")

    # Style updates
    style: Optional[ElementStyleConfig] = Field(
        default=None,
        description="Style properties to update (border, padding, margin, background)",
    )
    styles: Optional[ElementThemeOverrides] = Field(
        default=None,
        description="Theme overrides to update",
    )
    css_classes: Optional[str] = Field(
        default=None,
        description="Space-separated CSS class names",
    )

    # Visibility
    visibility: Optional[Literal["all", "logged-in", "not-logged"]] = Field(
        default=None,
        description="Element visibility setting",
    )
