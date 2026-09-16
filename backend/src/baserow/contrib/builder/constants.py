from django.db import models

from baserow.core.formula.types import (
    BASEROW_FORMULA_FORMAT_MARKDOWN,
    BASEROW_FORMULA_FORMAT_PLAIN,
)

IMPORT_SERIALIZED_IMPORTING = "importing"

# A color field can store a hex color value, e.g. "#abc123ff". It can also
# store an arbitrary string, like "transparent" or "my customer color".
COLOR_FIELD_MAX_LENGTH = 255


class HorizontalAlignments(models.TextChoices):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class VerticalAlignments(models.TextChoices):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


class WIDTHS(models.TextChoices):
    AUTO = "auto"
    FULL = "full"


class BACKGROUND_IMAGE_MODES(models.TextChoices):
    TILE = "tile"
    FILL = "fill"
    FIT = "fit"


class TextFormats(models.TextChoices):
    """
    How a user-provided text is rendered by the frontend. The formula surfaces
    that can be Markdown are declared as `FormattedFormulaField`s and carry the
    format on their value; this enum backs the surfaces that have a column for
    it instead: the plain-string ones and the Text element.
    """

    PLAIN = BASEROW_FORMULA_FORMAT_PLAIN
    MARKDOWN = BASEROW_FORMULA_FORMAT_MARKDOWN


class FontWeights(models.TextChoices):
    THIN = "thin"
    EXTRA_LIGHT = "extra-light"
    LIGHT = "light"
    REGULAR = "regular"
    MEDIUM = "medium"
    SEMI_BOLD = "semi-bold"
    BOLD = "bold"
    EXTRA_BOLD = "extra-bold"
    HEAVY = "heavy"
    BLACK = "black"
    EXTRA_BLACK = "extra-black"
