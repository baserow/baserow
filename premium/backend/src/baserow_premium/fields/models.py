from django.db import models

from baserow.contrib.database.fields.models import Field
from baserow.core.formula.field import FormulaField as ModelFormulaField

from .ai_field_output_types import TextAIFieldOutputType
from .registries import ai_field_output_registry


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
