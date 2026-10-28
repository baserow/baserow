from baserow.api.settings.registries import SettingsDataType
from baserow.core.embeddings import vector_search_available


class SemanticSearchSettingsDataType(SettingsDataType):
    type = "semantic_search"

    def get_settings_data(self, request) -> dict:
        return {"available": vector_search_available()}
