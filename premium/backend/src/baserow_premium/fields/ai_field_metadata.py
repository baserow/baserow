from enum import Enum
from typing import TYPE_CHECKING, Optional, Union

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils import timezone

from baserow.contrib.database.fields.metadata_handler import (
    FieldMetadataHandler,
    MetadataUpdate,
)

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel
    from baserow_premium.fields.models import AIField


class AIGenerationStatus(Enum):
    """
    Status values for AI field generation.

    Status is derived from metadata presence/values, not stored directly.
    """

    GENERATING = "generating"
    SUCCESS = "success"
    ERROR = "error"

    @classmethod
    def from_metadata(cls, metadata: Optional[dict]) -> Optional["AIGenerationStatus"]:
        """
        Derive status from metadata.

        Returns None if no metadata (row was never processed - this is normal state).

        If a row has been generating for longer than BASEROW_JOB_SOFT_TIME_LIMIT,
        it is considered timed out and returns None (to clear stuck UI states).

        :param metadata: The metadata dictionary for a field
        :return: AIGenerationStatus or None if no metadata
        """

        if not metadata:
            return None

        # Has start but no end = currently generating (unless timed out)
        if AIMetadataKeys.START in metadata and AIMetadataKeys.END not in metadata:
            start_time = metadata.get(AIMetadataKeys.START)
            if start_time:
                timeout = settings.BASEROW_JOB_SOFT_TIME_LIMIT
                elapsed = timezone.now().timestamp() - start_time
                if elapsed > timeout:
                    # Generation has exceeded job time limit - treat as timed out
                    return None
            return cls.GENERATING

        # Has end with ok=True = success
        if metadata.get(AIMetadataKeys.OK) is True:
            return cls.SUCCESS

        # Has end with ok=False = error
        if metadata.get(AIMetadataKeys.OK) is False:
            return cls.ERROR

        return None


class AIMetadataKeys:
    """
    Defines metadata keys for AI field generation tracking.

    Storage format by state:
        GENERATING: {"start": 1702656000}
        SUCCESS:    {"end": 1702656060, "ok": True}
        ERROR:      {"end": 1702656060, "ok": False, "error": "Error message"}
    """

    START = "start"
    END = "end"
    OK = "ok"
    ERROR = "error"


class AIFieldMetadataHandler:
    """
    Metadata handler for AI fields.

    Tracks AI generation lifecycle using the following metadata format:
    - start: When generation started (Unix timestamp)
    - end: When generation completed (Unix timestamp)
    - ok: True if successful, False if error
    - error: Error message (only present if ok=False)

    Status is derived from metadata:
    - No metadata: Row was never processed (normal state)
    - Has start, no end: GENERATING
    - Has end, ok=True: SUCCESS
    - Has end, ok=False: ERROR
    """

    MAX_ERROR_MESSAGE_LENGTH = 500

    @classmethod
    def set_generating(
        cls,
        ai_field: "AIField",
        row_ids: Union[int, list[int]],
    ):
        """
        Set generating status for one or more rows.

        :param ai_field: The AI field
        :param row_ids: Single row ID or list of row IDs
        """

        if isinstance(row_ids, int):
            row_ids = [row_ids]

        model = ai_field.table.get_model()

        if not FieldMetadataHandler.is_metadata_available(model):
            return

        timestamp = timezone.now().timestamp()
        updates = [
            MetadataUpdate(
                row_id=row_id,
                field_id=ai_field.id,
                metadata={AIMetadataKeys.START: timestamp},
            )
            for row_id in row_ids
        ]
        FieldMetadataHandler.set_metadata(model, updates, merge=False)

    @classmethod
    def set_generating_and_broadcast(
        cls,
        ai_field: "AIField",
        row_ids: Union[int, list[int]],
        user: AbstractUser,
    ):
        """
        Set generating status for rows and broadcast to connected clients.

        This combined method ensures the generating status is set in the database
        and all connected clients are notified.

        :param ai_field: The AI field
        :param row_ids: Single row ID or list of row IDs
        :param user: The user who triggered the generation
        """

        if isinstance(row_ids, int):
            row_ids = [row_ids]

        cls.set_generating(ai_field, row_ids)
        cls.broadcast_generation_started(ai_field, row_ids, user)

    @classmethod
    def set_success(
        cls,
        model: type["GeneratedTableModel"],
        row_id: int,
        field_id: int,
    ):
        """
        Mark an AI field as successfully generated.

        :param model: The generated table model
        :param row_id: The row ID
        :param field_id: The AI field ID
        """

        metadata = {
            AIMetadataKeys.END: timezone.now().timestamp(),
            AIMetadataKeys.OK: True,
        }
        FieldMetadataHandler.set_metadata(
            model,
            [MetadataUpdate(row_id=row_id, field_id=field_id, metadata=metadata)],
            merge=True,
        )

    @classmethod
    def set_error(
        cls,
        model: type["GeneratedTableModel"],
        row_id: int,
        field_id: int,
        error_message: str,
    ):
        """
        Mark an AI field as failed with an error.

        :param model: The generated table model
        :param row_id: The row ID
        :param field_id: The AI field ID
        :param error_message: Error message from the exception
        """

        truncated_error = error_message
        if len(error_message) > cls.MAX_ERROR_MESSAGE_LENGTH:
            truncated_error = error_message[: cls.MAX_ERROR_MESSAGE_LENGTH - 3] + "..."

        metadata = {
            AIMetadataKeys.END: timezone.now().timestamp(),
            AIMetadataKeys.OK: False,
            AIMetadataKeys.ERROR: truncated_error,
        }
        FieldMetadataHandler.set_metadata(
            model,
            [MetadataUpdate(row_id=row_id, field_id=field_id, metadata=metadata)],
            merge=True,
        )

    @classmethod
    def clear_metadata(
        cls,
        ai_field: "AIField",
        row_ids: list[int],
    ) -> bool:
        """
        Clear AI field metadata for specific rows.

        This is used to remove "generating" status from rows that were not
        processed due to an error in an earlier row within the same batch.

        :param ai_field: The AI field
        :param row_ids: List of row IDs to clear metadata for
        :return: True if metadata was cleared, False if metadata is not available
        """

        model = ai_field.table.get_model()

        if not FieldMetadataHandler.is_metadata_available(model):
            return False

        if not row_ids:
            return True

        FieldMetadataHandler.delete_metadata(model, ai_field.id, row_ids=row_ids)

        return True

    @classmethod
    def broadcast_generation_started(
        cls,
        ai_field: "AIField",
        row_ids: list[int],
        user: AbstractUser,
    ):
        """
        Broadcast metadata update to all connected clients when generation starts.

        This should be called AFTER setting metadata in the database and BEFORE
        dispatching the generation task. This ensures other users/windows see
        the generating status.

        :param ai_field: The AI field
        :param row_ids: List of row IDs being generated
        :param user: The user who triggered the generation
        """

        from baserow.contrib.database.rows.registries import row_metadata_registry
        from baserow.ws.registries import page_registry

        table = ai_field.table
        table_page_type = page_registry.get("table")

        metadata = row_metadata_registry.generate_and_merge_metadata_for_rows(
            user, table, row_ids
        )

        payload = {
            "type": "rows_metadata_updated",
            "table_id": table.id,
            "row_ids": row_ids,
            "metadata": metadata,
        }

        # Use on_commit to ensure the broadcast only fires after the DB
        # transaction commits. When called inside @transaction.atomic (e.g.,
        # from the API view), this prevents sending WS messages for changes
        # that might be rolled back. When called outside a transaction (e.g.,
        # during job execution with _empty_transaction_context), on_commit
        # fires immediately.
        transaction.on_commit(
            lambda: table_page_type.broadcast(
                payload,
                None,
                table_id=table.id,
            )
        )
