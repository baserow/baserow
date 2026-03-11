import json
from functools import lru_cache
from typing import Annotated, Literal

from loguru import logger
from pydantic import Field

from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.models import Application as BaserowApplication
from baserow.core.registries import application_type_registry
from baserow_enterprise.assistant.types import BaseModel

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


def apply_theme(builder, theme_name: str, user=None) -> None:
    """Apply a predefined theme to a builder application."""

    theme_data = _load_theme_data(theme_name)
    if not theme_data:
        return

    if user is not None:
        from baserow.contrib.builder.theme.service import ThemeService

        ThemeService().update_theme(user, builder, **theme_data)
    else:
        from baserow.contrib.builder.theme.handler import ThemeHandler

        ThemeHandler().update_theme(builder, **theme_data)


class BuilderItemCreate(BaseModel):
    """Base model for creating a new module (no ID)."""

    name: str = Field(...)
    type: Literal["database", "application", "automation", "dashboard"] = Field(...)
    theme: ThemeName | None = Field(
        default=None,
        description="Theme to apply (applications only). See THEME_CATALOG for options.",
    )

    def get_orm_type(self) -> str:
        """Returns the corresponding ORM type for the builder."""

        type_mapping = {
            "database": "database",
            "application": "builder",
            "automation": "automation",
            "dashboard": "dashboard",
        }
        return type_mapping[self.type]

    @classmethod
    def from_django_orm(cls, orm_app: BaserowApplication) -> "BuilderItem":
        """Creates a BuilderItem instance from a Django ORM Application instance."""

        orm_type = application_type_registry.get_by_model(orm_app.specific_class).type
        # The application_type_registry uses "builder" internally, but our
        # Literal type expects "application".
        type_mapping = {"builder": "application"}
        return cls(
            id=orm_app.id,
            name=orm_app.name,
            type=type_mapping.get(orm_type, orm_type),
        )

    def _post_creation_hook(self, user, builder_orm_instance):
        """Internal hook that can be overridden to perform actions after creation."""

    def post_creation_hook(self, user, builder_orm_instance):
        """Hook that can be overridden to perform actions after creation."""

        specific_item_create = builder_type_registry.get_by_type_create(self.type)

        return specific_item_create(**self.model_dump())._post_creation_hook(
            user, builder_orm_instance
        )


class BuilderItem(BuilderItemCreate):
    """Model for an existing module (with ID)."""

    id: int = Field(...)


class DatabaseItemCreate(BuilderItemCreate):
    """Base model for creating a new database (no ID)."""

    type: Literal["database"] = Field(...)


class DatabaseItem(DatabaseItemCreate):
    """Model for an existing database (with ID)."""

    id: int = Field(...)


class ApplicationItemCreate(BuilderItemCreate):
    """Base model for creating a new application (no ID)."""

    type: Literal["application"] = Field(...)

    def _post_creation_hook(self, user, builder_orm_instance):
        IntegrationService().create_integration(
            user,
            integration_type_registry.get("local_baserow"),
            builder_orm_instance,
            name="Local Baserow",
        )
        apply_theme(builder_orm_instance, self.theme or "baserow", user=user)


class ApplicationItem(ApplicationItemCreate):
    """Model for an existing application (with ID)."""

    id: int = Field(...)


class AutomationItemCreate(BuilderItemCreate):
    """Base model for creating a new automation (no ID)."""

    type: Literal["automation"] = Field(...)

    def _post_creation_hook(self, user, builder_orm_instance):
        IntegrationService().create_integration(
            user,
            integration_type_registry.get("local_baserow"),
            builder_orm_instance,
            name="Local Baserow",
        )


class AutomationItem(AutomationItemCreate):
    """Model for an existing automation (with ID)."""

    id: int = Field(...)


class DashboardItemCreate(BuilderItemCreate):
    """Base model for creating a new dashboard (no ID)."""

    type: Literal["dashboard"] = Field(...)

    def _post_creation_hook(self, user, builder_orm_instance):
        IntegrationService().create_integration(
            user,
            integration_type_registry.get("local_baserow"),
            builder_orm_instance,
            name="Local Baserow",
        )


class DashboardItem(DashboardItemCreate):
    """Model for an existing dashboard (with ID)."""

    id: int = Field(...)


AnyBuilderItem = Annotated[
    DatabaseItem | ApplicationItem | AutomationItem | DashboardItem,
    Field(discriminator="type"),
]

AnyBuilderItemCreate = Annotated[
    DatabaseItemCreate
    | ApplicationItemCreate
    | AutomationItemCreate
    | DashboardItemCreate,
    Field(discriminator="type"),
]


class BuilderItemRegistry:
    _registry = {
        "database": DatabaseItem,
        "application": ApplicationItem,
        "builder": ApplicationItem,  # alias for application
        "automation": AutomationItem,
        "dashboard": DashboardItem,
    }
    _registry_create = {
        "database": DatabaseItemCreate,
        "application": ApplicationItemCreate,
        "builder": ApplicationItemCreate,  # alias for application
        "automation": AutomationItemCreate,
        "dashboard": DashboardItemCreate,
    }

    def get_by_type(self, builder_type: str) -> AnyBuilderItem:
        return self._registry[builder_type]

    def get_by_type_create(self, builder_type: str) -> AnyBuilderItemCreate:
        return self._registry_create[builder_type]

    def from_django_orm(self, orm_app: BaserowApplication) -> BuilderItem:
        app_type = application_type_registry.get_by_model(orm_app.specific_class).type
        field_class: AnyBuilderItem = self._registry[app_type]
        return field_class.from_django_orm(orm_app)


builder_type_registry = BuilderItemRegistry()
