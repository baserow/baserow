from django.db import models

from baserow.contrib.database.fields.models import Field
from baserow.core.formula.field import FormulaField as ModelFormulaField


class AIField(Field):
    ai_generative_ai_type = models.CharField(max_length=32, null=True)
    ai_generative_ai_model = models.CharField(max_length=32, null=True)
    ai_temperature = models.FloatField(null=True)
    ai_prompt = ModelFormulaField(default="")
    ai_file_field = models.ForeignKey(
        Field, null=True, on_delete=models.SET_NULL, related_name="ai_field"
    )
