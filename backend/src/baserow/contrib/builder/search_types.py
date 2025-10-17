from typing import Optional

from baserow.contrib.builder.models import Builder
from baserow.core.models import Workspace
from baserow.core.search.data_types import SearchResult
from baserow.core.search.search_types import ApplicationSearchType


class BuilderSearchType(ApplicationSearchType):
    """
    Searchable item type specifically for builders.
    """

    type = "builder"
    name = "Builder"
    model_class = Builder
    priority = 2

    def serialize_result(
        self, result, user=None, workspace: "Workspace" = None
    ) -> Optional[SearchResult]:
        """Convert builder to search result with builder_id in metadata."""

        return SearchResult(
            type=self.type,
            id=result.id,
            title=result.name,
            subtitle=self.type,
            created_on=result.created_on,
            updated_on=result.updated_on,
            metadata={
                "workspace_id": workspace.id,
                "workspace_name": workspace.name,
                "builder_id": result.id,
            },
        )
