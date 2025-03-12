from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.api.data_sync.serializers import DataSyncSerializer
from baserow.contrib.database.table.models import Table


class TableImportConfiguration(serializers.Serializer):
    """
    Additional table import configuration.
    """

    upsert_fields = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        allow_null=True,
        allow_empty=True,
        default=None,
        help_text=(
            (
                "A list of field ids in the table, that should be used to create "
                "a value identifying a row in the table. Each field id should point "
                "to an existing field in the table, that can be used to create upsert "
                "match value.\nField types that can be used in upsert fields: text, "
                "long_text, number, rating, boolean, date, duration, phone_number, "
                "email, url.\n"
                "If speficied, `upsert_values` should also be provided."
            )
        ),
    )
    upsert_values = serializers.ListField(
        allow_empty=True,
        allow_null=True,
        default=None,
        child=serializers.ListField(
            min_length=1,
        ),
        help_text=(
            "A list of list of values that are identifying a row in imported data. "
            "Each value in a list for a single row should correspond with field type "
            "in the table selected in `upsert_fields`. \n"
            "Each row in `upsert_values` should correspond to a row in imported "
            "dataset. Subsequent occurrence of the same upsert value will be compared "
            "to corresponding subsequent occurrence of the same value in the table. \n"
            "This also requires that import data should be in the same order as rows "
            "in the table."
        ),
    )

    def validate(self, attrs):
        if attrs.get("upsert_fields") and not len(attrs.get("upsert_values") or []):
            raise ValidationError(
                {
                    "upsert_value": (
                        "upsert_values must not be empty "
                        "when upsert_fields are provided."
                    )
                }
            )
        return attrs


class TableSerializer(serializers.ModelSerializer):
    data_sync = DataSyncSerializer()

    class Meta:
        model = Table
        fields = ("id", "name", "order", "database_id", "data_sync")
        extra_kwargs = {
            "id": {"read_only": True},
            "database_id": {"read_only": True},
            "order": {"help_text": "Lowest first."},
        }


class TableWithoutDataSyncSerializer(TableSerializer):
    data_sync = None

    class Meta(TableSerializer.Meta):
        fields = (
            "id",
            "name",
            "order",
            "database_id",
        )


class TableCreateSerializer(serializers.ModelSerializer):
    data = serializers.ListField(
        min_length=1,
        default=None,
        help_text=(
            "A list of rows that needs to be created as initial table data. "
            "Each row is a list of values that are going to be added in the new "
            "table in the same order as provided.\n\n"
            'Ex: \n```json\n[\n  ["row1_field1_value", "row1_field2_value"],\n'
            '  ["row2_field1_value", "row2_field2_value"],\n]\n```\n'
            "for creating a two rows table with two fields.\n\n"
            "If not provided, some example data is going to be created."
        ),
    )
    first_row_header = serializers.BooleanField(
        default=False,
        help_text="Indicates if the first provided row is the header. If true the "
        "field names are going to be the values of the first row. Otherwise "
        'they will be called "Field N"',
    )

    class Meta:
        model = Table
        fields = ("name", "data", "first_row_header")
        extra_kwargs = {
            "data": {"required": False},
            "first_row_header": {"required": False},
        }


class TableImportSerializer(serializers.Serializer):
    data = serializers.ListField(
        min_length=1,
        required=True,
        help_text=(
            "A list of rows you want to add to the specified table. "
            "Each row is a list of values, one for each **writable** field. "
            "The field values must be ordered according to the field order in the "
            "table. "
            "All values must be compatible with the corresponding field type.\n\n"
            'Ex: \n```json\n[\n  ["row1_field1_value", "row1_field2_value"],\n'
            '  ["row2_field1_value", "row2_field2_value"],\n]\n```\n'
            "for adding two rows to a table with two writable fields."
        ),
    )
    configuration = TableImportConfiguration(required=False, default=None)

    class Meta:
        fields = ("data",)


class TableUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ("name",)


class OrderTablesSerializer(serializers.Serializer):
    table_ids = serializers.ListField(
        child=serializers.IntegerField(), help_text="Table ids in the desired order."
    )
