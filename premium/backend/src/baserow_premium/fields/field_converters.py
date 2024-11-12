from baserow.contrib.database.fields.field_converters import RecreateFieldConverter

from .models import AIField


class AIFieldConverter(RecreateFieldConverter):
    type = "ai"

    def is_applicable(self, from_model, from_field, to_field):
        from_ai = isinstance(from_field, AIField)
        to_ai = isinstance(to_field, AIField)
        # If any field converts to the AI field, then we want to recreate the field
        return not from_ai and to_ai
