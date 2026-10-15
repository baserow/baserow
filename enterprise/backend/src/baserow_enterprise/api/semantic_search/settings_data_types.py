from django.conf import settings

from baserow.api.settings.registries import SettingsDataType
from baserow.core.embeddings import vector_search_available


class SemanticSearchSettingsDataType(SettingsDataType):
    type = "semantic_search"

    def get_settings_data(self, request) -> dict:
        return {
            "available": vector_search_available(),
            # So that the editor can explain the limit before the server refuses it.
            "max_results": settings.BASEROW_SEMANTIC_SEARCH_MAX_RESULTS,
        }
