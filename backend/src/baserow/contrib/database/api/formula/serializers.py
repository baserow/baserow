from rest_framework import serializers

from baserow.contrib.database.fields.dependencies.circular_reference_checker import (
    get_all_field_dependencies,
)
from baserow.contrib.database.fields.field_types import FormulaFieldType
from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.formula.types.formula_types import (
    BaserowFormulaSingleSelectType,
)


class TypeFormulaRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormulaField
        fields = ("formula", "name")


class TypeFormulaResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormulaField
        fields = FormulaFieldType.serializer_field_names


class BaserowFormulaSelectOptionsSerializer(serializers.ListField):
    def to_representation(self, data):
        from baserow.contrib.database.fields.models import SelectOption

        field = data.instance
        if field.formula_type != BaserowFormulaSingleSelectType.type:
            return []

        select_options = SelectOption.objects.filter(
            field_id__in=get_all_field_dependencies(field)
        )
        return [self.child.to_representation(item) for item in select_options]
