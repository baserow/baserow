from typing import Dict


class BaserowModule:
    type = None
    heading = None

    @property
    def message_prefix(self) -> str:
        return f"[{self.heading}] "


class DatabaseBuilderModule(BaserowModule):
    type = "database"
    heading = "Database"

    @property
    def message_prefix(self) -> str:
        # For compatibility reasons, at the moment the database module does
        # not have a prefix. Remove this implementation if we change ours minds.
        return ""


class ApplicationBuilderModule(BaserowModule):
    type = "builder"
    heading = "Builder"


class AutomationBuilderModule(BaserowModule):
    type = "automation"
    heading = "Automation"


module_types: Dict[str, type[BaserowModule]] = {
    DatabaseBuilderModule.type: DatabaseBuilderModule,
    ApplicationBuilderModule.type: ApplicationBuilderModule,
    AutomationBuilderModule.type: AutomationBuilderModule,
}
