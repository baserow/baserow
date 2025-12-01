import abc
from typing import Any, Dict, Generator, List

from django.db.models import QuerySet

from rest_framework.fields import Field

from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.rows.types import ActionData
from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry
from baserow.core.types import AnyUser


class RowMetadataRegistry(Registry):
    """
    Contains all the types of metadata that can be attached to individual rows in
    Baserow.
    """

    name = "row_metadata"

    def generate_and_merge_metadata_for_row(
        self, user, table, row_id: int
    ) -> Dict[str, Any]:
        """
        Alternative for generate_and_merge_metadata_for_rows which takes a single row
        id.
        """

        return self.generate_and_merge_metadata_for_rows(
            user, table, (i for i in [row_id])
        ).get(row_id, {})

    def generate_and_merge_metadata_for_rows(
        self, user, table, row_ids: Generator[int, None, None]
    ) -> Dict[int, Dict[str, Any]]:
        """
        For every type of row metadata will generate that type of metadata for each
        provided row in the row_ids generator. Then returns a dictionary keyed by the
        row id with the value being a dictionary of metadata. The dictionary of metadata
        is keyed by the particular instance's RowMetadataType.type with the value being
        whatever was returned by that instances generate_metadata_for_rows for that
        row id.

        For example if two different RowMetadata types 'A' and 'B" were registered,
        and they returned {'1': 10, '2': 2} and {'1': False, '2': True} from their
        respective generate_metadata_for_rows methods. This function would then return
        a dict which looked like: {'1': {'A':10, 'B':False}, '2': {'A':2, 'B':True}}.

        :param user: The user who the metadata is being generated for.
        :param table: The table containing the row_ids.
        :param row_ids: A generator which should return the row ids generate metadata
            for. If no RowMetadataTypes are registered then this generator will not be
            invoked.
        :return: A dictionary of Row Id -> RowMetadataType -> Metadata Value if
            metadata types are registered, otherwise an empty dict.
        """

        metadata_types = self.get_all()
        if len(metadata_types) > 0:
            row_ids = list(row_ids)
            row_metadata = {}
            for metadata_type in metadata_types:
                per_row_metadata = metadata_type.generate_metadata_for_rows(
                    user, table, row_ids
                )
                for row_id, metadata in per_row_metadata.items():
                    single_row_metadata = row_metadata.setdefault(row_id, {})
                    single_row_metadata[metadata_type.type] = metadata
            return row_metadata
        else:
            return {}


class RowMetadataType(Instance, abc.ABC):
    """
    Registering a RowMetadataType allows you to attach extra data on a per row basis
    to rows returned by the Baserow API. This metadata can then be accessed via views
    in the frontend code. This metadata is not explicitly stored on its own but instead
    should be retrievable in a single quick query run by generate_metadata_for_rows
    given a list of rows to get metadata for.

    Metadata on each row will be found under the key of this Types 'type' attribute.
    See RowMetadataRegistry.generate_and_merge_metadata_for_rows for more details.
    """

    @abc.abstractmethod
    def generate_metadata_for_rows(
        self, user, table, row_ids: List[int]
    ) -> Dict[int, Any]:
        """
        Given a table and a list of row ids to generate metadata for this function
        should be overridden and implemented to return a dictionary of row id to the
        metadata you wish to attach to that row.

        :param user: The user who the metadata is being generated for.
        :param table: The table containing the row_ids.
        :param row_ids: A list of the row ids to generate metadata for.
        :return: A dictionary of Row Id -> Metadata Value.
        """

        pass

    @abc.abstractmethod
    def get_example_serializer_field(self) -> Field:
        """
        Used to construct the rest api documentation. Should be a serializer field which
        represents the values in the dict returned by generate_metadata_for_rows.

        :return: A drf field with help_text and other example data set for use by the
            api documentation.
        """

        pass


class ChangeRowHistoryRegistry(Registry):
    """
    Contains instances providing additional filtering and operations
    on row history entries.
    """

    name = "change_row_history"


class ChangeRowHistoryType(Instance, abc.ABC):
    @abc.abstractmethod
    def apply_to_list_queryset(
        self,
        queryset: QuerySet[RowHistory],
        workspace: Workspace,
        table_id: int,
        row_id: int,
    ) -> QuerySet[RowHistory]:
        """
        By implementing this method you can further filter the
        returned queryset of row history entries.
        """

        return queryset


class RowHistoryProviderType(Instance, abc.ABC):
    """
    Generic row history provider ABC. This class acts as an interface
    definition for any history provider class hierarchy that should act on
    `action_done` signal and provide row changes entries.
    """

    @abc.abstractmethod
    def get_row_history(self, user: AnyUser, params: ActionData) -> list[RowHistory]:
        """
        Returns a list of RowHistory instances related to the action.
        """


class RowHistoryProviderRegistry(Registry[RowHistoryProviderType]):
    name = "row_history_provider"


row_metadata_registry = RowMetadataRegistry()
change_row_history_registry = ChangeRowHistoryRegistry()
row_history_provider_registry = RowHistoryProviderRegistry()
