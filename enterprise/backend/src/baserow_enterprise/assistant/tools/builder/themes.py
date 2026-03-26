import json
from functools import lru_cache
from typing import Literal

from loguru import logger

# ---------------------------------------------------------------------------
# Theme catalog
# ---------------------------------------------------------------------------

THEME_CATALOG: dict[str, str] = {
    "baserow": "Clean, modern light theme with blue accents. Good default for most apps.",
    "eclipse": "Dark, high-contrast theme. Best for dashboards, analytics, or developer tools.",
    "ivory": "Warm, soft light theme with neutral tones. Suits blogs, portfolios, and creative apps.",
    "ocean": "Deep sea blues, clean and professional. Good for corporate portals, logistics dashboards.",
    "forest": "Deep greens and warm wood tones. Good for sustainability, outdoor brands, wellness.",
    "sunset": "Warm oranges and purples. Good for creative agencies, media, entertainment.",
    "slate": "Ultra-clean monochrome grayscale. Good for developer tools, documentation, admin panels.",
    "neon": "Dark background with vivid neon accents. Good for gaming, tech startups, dashboards.",
    "terracotta": "Mediterranean warmth. Good for architecture, real estate, interior design, restaurants.",
    "lavender": "Gentle, calming purple tones. Good for health/wellness, beauty, education, SaaS.",
    "coral": "Vibrant and energetic. Good for travel, hospitality, food & beverage, lifestyle brands.",
    "midnight": "Elegant dark mode with warm gold accents. Good for finance, luxury, executive dashboards.",
    "mint": "Light and airy with fresh mint green. Good for fintech, health apps, clean dashboards.",
    "corporate": "Navy and steel, sharp and professional. Good for enterprise portals, B2B platforms.",
    "finance": "Deep green and gold, trustworthy and conservative. Good for banking, investment, insurance.",
    "tech": "Modern indigo and cyan. Good for SaaS products, developer platforms, tech companies.",
    "luxury": "Dark with champagne gold accents and serif headings. Good for premium brands, high-end services.",
    "healthcare": "Calming cyan and teal. Good for medical portals, health apps, wellness platforms.",
    "education": "Warm blue with orange accents. Good for schools, e-learning, training platforms.",
    "legal": "Dark navy with serif headings. Good for law firms, consulting, professional services.",
    "startup": "Bold violet with pill-shaped buttons. Good for modern startups, product launches.",
    "agency": "Dark with sharp red accents and zero border radius. Good for creative studios, design agencies.",
    "realestate": "Warm brown with serif headings. Good for property listings, architecture, interior design.",
}

ThemeName = Literal[tuple(THEME_CATALOG.keys())]


@lru_cache(maxsize=len(THEME_CATALOG))
def _load_theme_data(theme_name: str) -> dict | None:
    """Load theme properties from a template JSON file. Cached per theme."""

    if theme_name not in THEME_CATALOG:
        return None

    import os

    from django.conf import settings

    filename = f"ab_{theme_name}_theme.json"
    path = os.path.join(settings.APPLICATION_TEMPLATES_DIR, filename)
    try:
        with open(path) as f:
            template = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(
            "[assistant] Theme template '{}' not found at {}", filename, path
        )
        return None

    for app in template.get("export", []):
        if app.get("type") == "builder" and "theme" in app:
            return app["theme"]

    return None


def apply_theme(builder, theme_name: str, user=None) -> bool:
    """
    Apply a predefined theme to a builder application.

    Returns ``True`` if the theme was applied, ``False`` if the theme
    template could not be loaded (missing/corrupt file).
    """

    theme_data = _load_theme_data(theme_name)
    if not theme_data:
        return False

    if user is not None:
        from baserow.contrib.builder.theme.service import ThemeService

        ThemeService().update_theme(user, builder, **theme_data)
    else:
        from baserow.contrib.builder.theme.handler import ThemeHandler

        ThemeHandler().update_theme(builder, **theme_data)

    return True
