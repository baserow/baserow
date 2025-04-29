from rest_framework import serializers

from baserow.contrib.database.fields.dependencies.circular_reference_checker import (
    get_all_field_dependencies,
)
from baserow.contrib.database.fields.field_types import FormulaFieldType
from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.fields.registries import field_type_registry


class TypeFormulaRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormulaField
        fields = ("formula", "name")


class TypeFormulaResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormulaField
        fields = list(
            set(FormulaFieldType.serializer_field_names)
            - {"available_collaborators", "select_options"}
        )


class BaserowFormulaSelectOptionsSerializer(serializers.ListField):
    def to_representation(self, data):
        from baserow.contrib.database.fields.models import SelectOption

        field = data.instance
        field_type = field_type_registry.get_by_model(field)

        # Select options are needed for view filters in the frontend,
        # but let's avoid the potentially slow query if not required.
        if field_type.can_represent_select_options(field):
            select_options = SelectOption.objects.filter(
                field_id__in=get_all_field_dependencies(field),
                field__trashed=False,
            )
            return [self.child.to_representation(item) for item in select_options]
        else:
            return []
