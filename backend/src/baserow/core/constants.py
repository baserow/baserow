"""Miscellaneous constant values used across the codebase."""
from django.db import models

# Date formats supported in Baserow
DATE_FORMAT = {
    "EU": {"name": "European (D/M/Y)", "format": "%d/%m/%Y", "sql": "DD/MM/YYYY"},
    "US": {"name": "US (M/D/Y)", "format": "%m/%d/%Y", "sql": "MM/DD/YYYY"},
    "ISO": {"name": "ISO (Y-M-D)", "format": "%Y-%m-%d", "sql": "YYYY-MM-DD"},
}

# Django's choices to use with models.TextField
DATE_FORMAT_CHOICES = [(k, v["name"]) for k, v in DATE_FORMAT.items()]

# Date and time formats supported in Baserow
DATE_TIME_FORMAT = {
    "24": {"name": "24 hour", "format": "%H:%M", "sql": "HH24:MI"},
    "12": {"name": "12 hour", "format": "%I:%M %p", "sql": "HH12:MI AM"},
}

# Django's choices to use with models.TextField
DATE_TIME_FORMAT_CHOICES = [(k, v["name"]) for k, v in DATE_TIME_FORMAT.items()]

# Should stay in sync with `light-`, (non-prefixed), and 'dark-' in
# `modules/core/assets/scss/colors.scss::$colors`.
BASEROW_COLORS = [
    "light-blue",
    "light-cyan",
    "light-orange",
    "light-yellow",
    "light-red",
    "light-brown",
    "light-purple",
    "light-pink",
    "light-gray",
    "blue",
    "cyan",
    "orange",
    "yellow",
    "red",
    "brown",
    "purple",
    "pink",
    "gray",
    "dark-blue",
    "dark-cyan",
    "dark-orange",
    "dark-yellow",
    "dark-red",
    "dark-brown",
    "dark-purple",
    "dark-pink",
    "dark-gray",
]


class RatingStyleChoices(models.TextChoices):
    STAR = "star"
    HEART = "heart"
    THUMBS_UP = "thumbs-up"
    FLAG = "flag"
    SMILE = "smile"
