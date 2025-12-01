from typing import Annotated, Literal

from pydantic import Field

from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.models import Application as BaserowApplication
from baserow.core.registries import application_type_registry
from baserow_enterprise.assistant.types import BaseModel


class BuilderItemCreate(BaseModel):
    """Base model for creating a new module (no ID)."""

    name: str = Field(...)
    type: Literal["database", "application", "automation", "dashboard"] = Field(...)

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

        return cls(
            id=orm_app.id,
            name=orm_app.name,
            type=application_type_registry.get_by_model(orm_app.specific_class).type,
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
