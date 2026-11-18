from baserow.contrib.agent.registries import agent_data_provider_type_registry
from baserow.core.formula.registries import DataProviderTypeRegistry
from baserow.core.services.formula_importer import BaserowFormulaImporter


class AgentFormulaImporter(BaserowFormulaImporter):
    """Updates the paths of an agent formula's `get()` calls to imported ids."""

    def get_data_provider_type_registry(self) -> DataProviderTypeRegistry:
        """
        :return: The registry the agent's formulas name their providers in.
        """

        return agent_data_provider_type_registry
