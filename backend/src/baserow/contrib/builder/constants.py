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
