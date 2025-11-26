from enum import StrEnum

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models

from baserow.contrib.database.fields.models import Field
from baserow.core.formula.field import FormulaField as ModelFormulaField
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job

from .ai_field_output_types import TextAIFieldOutputType
from .registries import ai_field_output_registry

User = get_user_model()


class AIField(Field):
    ai_generative_ai_type = models.CharField(max_length=32, null=True)
    ai_generative_ai_model = models.CharField(max_length=128, null=True)
    ai_output_type = models.CharField(
        max_length=32,
        db_default=TextAIFieldOutputType.type,
        default=TextAIFieldOutputType.type,
    )
    ai_temperature = models.FloatField(null=True)
    ai_prompt = ModelFormulaField(default="")
    ai_file_field = models.ForeignKey(
        Field, null=True, on_delete=models.SET_NULL, related_name="ai_field"
    )
    ai_auto_update = models.BooleanField(
        default=False,
        db_default=False,
        help_text="If set, and the prompt refers other fields, a change on those fields will trigger a recalculation of this field.",
    )
    ai_auto_update_user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        help_text="The user on whose behalf the field is auto-updated.",
    )

    def __getattr__(self, name):
        """
        When a property is called on the field object, it tries to return the default
        value of the field object related to the `ai_output_type` `model_class`. This
        will make it more compatible with the check functions like `check_can_group_by`.
        """

        try:
            ai_output_type = ai_field_output_registry.get(self.ai_output_type)
            output_field = ai_output_type.baserow_field_type.model_class
            return output_field._meta.get_field(name).default
        except Exception:
            super().__getattr__(name)

    @property
    def ai_max_concurrent_generations(self) -> int:
        """
        Returns a number of max concurrent workers to be used with the model.
        """

        return settings.BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS


class GenerateAIValuesJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    class MODES(StrEnum):
        ROWS = "rows"
        VIEW = "view"
        TABLE = "table"

    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="The AI field to generate values for.",
    )
    row_ids = ArrayField(
        models.IntegerField(),
        null=True,
        help_text="If provided, the row IDs to generate AI values for.",
    )
    view_id = models.IntegerField(
        null=True, help_text="If provided, the view ID to generate AI values for."
    )
    only_empty = models.BooleanField(
        default=False, help_text="Whether to only generate values for empty cells."
    )

    @property
    def mode(self):
        if self.row_ids is not None:
            return self.MODES.ROWS
        elif self.view_id is not None:
            return self.MODES.VIEW
        else:  # Without filters, generate the values for the whole table
            return self.MODES.TABLE
