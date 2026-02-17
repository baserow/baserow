from typing import Any, Dict, List, Optional

from django.utils import timezone

from rest_framework import serializers
from rest_framework.fields import Field

from baserow.contrib.database.fields.metadata_handler import FieldMetadataHandler
from baserow.contrib.database.rows.registries import RowMetadataType

from .ai_field_metadata import AIGenerationStatus, AIMetadataKeys
from .models import AIField


class AIFieldMetadataType(RowMetadataType):
    """
    Row metadata type for AI fields.

    Returns metadata for all AI fields in a table, showing status for
    generating/error states. Metadata is stored in the field_metadata
    JSONB column and transformed to a simplified format for the API.

    Example response structure:
    {
        "row_metadata": {
            "ai_field": {
                "456": {"status": "generating"},
                "457": {"status": "error"}
            }
        }
    }

    Status values:
    - "generating": AI is currently generating a value
    - "error": generation failed (only shown for a limited time)

    Success and pending states are not included in the response.
    """

    type = "ai_field"
    # Time in seconds after which error status is no longer shown (1 hour)
    ERROR_EXPIRATION_SECONDS = 3600

    def generate_metadata_for_rows(
        self, user, table, row_ids: List[int]
    ) -> Dict[int, Any]:
        """
        Generate AI field metadata for the specified rows.

        :param user: The user requesting the metadata
        :param table: The table containing the rows
        :param row_ids: List of row IDs to generate metadata for
        :return: Dictionary mapping row_id -> {field_id -> metadata}
        """

        ai_fields = AIField.objects.filter(table=table)

        if not ai_fields.exists():
            return {}

        model = table.get_model()

        if not FieldMetadataHandler.is_metadata_available(model):
            return {}

        ai_field_ids = [f.id for f in ai_fields]
        metadata_result = FieldMetadataHandler.get_metadata(
            model, row_ids, ai_field_ids
        )

        result = {}
        for row_id, fields_metadata in metadata_result.items():
            row_metadata = {}

            for field_id, field_metadata in fields_metadata.items():
                if field_metadata:
                    api_metadata = self._transform_metadata_for_api(field_metadata)
                    # Only add to result if there's metadata to show
                    if api_metadata:
                        row_metadata[str(field_id)] = api_metadata

            if row_metadata:
                result[row_id] = row_metadata

        return result

    def _transform_metadata_for_api(
        self, metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Transform internal metadata to API format.

        Only returns metadata for generating or error states.
        Error state is only returned if it occurred within ERROR_EXPIRATION_SECONDS.

        Storage format: {"start": 1234.5, "end": 1234.5, "ok": True/False}
        API format: {"status": "generating"} or {"status": "error"}

        :param metadata: Internal metadata
        :return: Dictionary with status or None if no status to show
        """

        status_enum = AIGenerationStatus.from_metadata(metadata)

        if status_enum is None:
            return None

        # Only return status for generating or error states
        if status_enum == AIGenerationStatus.GENERATING:
            return {"status": "generating"}
        elif status_enum == AIGenerationStatus.ERROR:
            generation_finished_at = metadata.get(AIMetadataKeys.END)
            if generation_finished_at:
                current_time = timezone.now().timestamp()
                time_since_error = current_time - generation_finished_at

                if time_since_error <= self.ERROR_EXPIRATION_SECONDS:
                    return {"status": "error"}

            # Error has expired or no timestamp, don't show it
            return None

        # Success state is not shown
        return None

    def get_example_serializer_field(self) -> Field:
        """
        Return example serializer field for API documentation.

        The field represents a dictionary mapping field_id -> status object.
        """

        return serializers.DictField(
            child=serializers.DictField(child=serializers.CharField()),
            help_text=(
                "AI field status indicators keyed by field ID. "
                "Values are objects with 'status' key: 'generating' or 'error'. "
                "Only fields with generating or recent error status are included. "
                "Errors expire after 1 hour."
            ),
            required=False,
        )
