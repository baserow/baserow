from typing import Dict


class BaserowDomain:
    type = None
    heading = None

    @property
    def message_prefix(self) -> str:
        return f"[{self.heading}] "


class CoreDomain(BaserowDomain):
    type = "core"
    heading = "Core"


class DashboardDomain(BaserowDomain):
    type = "dashboard"
    heading = "Dashboard"


class DatabaseDomain(BaserowDomain):
    type = "database"
    heading = "Database"


class BuilderDomain(BaserowDomain):
    type = "builder"
    heading = "Builder"


class AutomationDomain(BaserowDomain):
    type = "automation"
    heading = "Automation"


class IntegrationDomain(BaserowDomain):
    type = "integration"
    heading = "Integration"


domain_types: Dict[str, type[BaserowDomain]] = {
    CoreDomain.type: CoreDomain,
    DashboardDomain.type: DashboardDomain,
    DatabaseDomain.type: DatabaseDomain,
    BuilderDomain.type: BuilderDomain,
    AutomationDomain.type: AutomationDomain,
    IntegrationDomain.type: IntegrationDomain,
}
