from django.contrib.postgres.fields import ArrayField
from django.db import models

from baserow.core.action.signals import ActionCommandType
from baserow.core.encoders import JSONEncoderSupportingDataClasses
from baserow.core.subjects import UserSubjectType


class RowHistory(models.Model):
    # Reuse the former user columns so existing entries become User actors without a
    # data migration. The actor type must always be used together with the actor ID
    # because User and Agent primary keys can overlap.
    actor_id = models.PositiveIntegerField(
        db_column="user_id",
        null=True,
        help_text="The ID of the actor that performed the action.",
    )
    actor_type = models.CharField(max_length=255, db_default=UserSubjectType.type)
    actor_name = models.CharField(
        db_column="user_name",
        max_length=160,
        blank=True,
        help_text="The name of the actor that performed the action.",
    )
    table = models.ForeignKey(
        "database.Table",
        on_delete=models.CASCADE,
        help_text="The table that the row belongs to.",
    )
    row_id = models.PositiveIntegerField(
        help_text="The id of the row that was changed.",
    )
    field_names = ArrayField(
        models.CharField(max_length=255),
        help_text="The names of the fields that were changed. All these names "
        "must be provided in fields_metadata, before_values and after_values.",
    )
    fields_metadata = models.JSONField(
        encoder=JSONEncoderSupportingDataClasses,
        help_text="The metadata of the fields that were changed.",
    )
    action_uuid = models.CharField(
        max_length=36,
        help_text="The UUID of the action that was performed resulting in this history entry. ",
    )
    action_command_type = models.CharField(
        choices=[(t.value, t.name) for t in ActionCommandType],
        default=ActionCommandType.DO.value,
        max_length=4,
        help_text="The type of command that was performed.",
    )
    action_type = models.TextField(
        help_text="The type of the action that was performed."
    )
    action_timestamp = models.DateTimeField(
        help_text="The timestamp of the action that was performed."
    )
    before_values = models.JSONField(
        encoder=JSONEncoderSupportingDataClasses,
        help_text="The values of the row before the action was performed.",
    )
    after_values = models.JSONField(
        encoder=JSONEncoderSupportingDataClasses,
        help_text="The values of the row after the action was performed.",
    )

    class Meta:
        ordering = ("-action_timestamp", "-id")
        indexes = [
            # For deleting history entries by action timestamp.
            models.Index(fields=["action_timestamp"]),
            # For listing the history of a row.
            models.Index(fields=["table", "row_id", "-action_timestamp", "-id"]),
        ]
