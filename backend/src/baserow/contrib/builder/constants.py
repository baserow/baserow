from django.db import models

IMPORT_SERIALIZED_IMPORTING = "importing"


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


class FontWeights(models.TextChoices):
    THIN = "Thin"
    ULTRA_LIGHT = "Extra-light"
    LIGHT = "Light"
    REGULAR = "Regular"
    MEDIUM = "Medium"
    SEMI_BOLD = "Semi-bold"
    BOLD = "Bold"
    EXTRA_BOLD = "Extra-bold"
    HEAVY = "Heavy"
