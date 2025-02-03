from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import fields, serializers

from baserow.api.serializers import FileURLSerializerMixin
from baserow.contrib.database.api.constants import get_filters_object_description
from baserow.contrib.database.api.views.serializers import PublicViewFiltersSerializer
from baserow.contrib.database.export.handler import ExportHandler
from baserow.contrib.database.export.models import ExportJob
from baserow.contrib.database.export.registries import table_exporter_registry

# This is a map from the front end supported charsets to the internal python supported
# charset value as they do not always match up.
# Please keep in sync with
# web-frontend/modules/core/components/helpers/CharsetDropdown.vue:
SUPPORTED_EXPORT_CHARSETS = [
    ("utf-8", "utf-8"),
    ("iso-8859-6", "iso-8859-6"),
    ("windows-1256", "windows-1256"),
    ("iso-8859-4", "iso-8859-4"),
    ("windows-1257", "windows-1257"),
    ("iso-8859-14", "iso-8859-14"),
    ("iso-8859-2", "iso-8859-2"),
    ("windows-1250", "windows-1250"),
    ("gbk", "gbk"),
    ("gb18030", "gb18030"),
    ("big5", "big5"),
    ("koi8-r", "koi8-r"),
    ("koi8-u", "koi8-u"),
    ("iso-8859-5", "iso-8859-5"),
    ("windows-1251", "windows-1251"),
    ("x-mac-cyrillic", "mac-cyrillic"),
    ("iso-8859-7", "iso-8859-7"),
    ("windows-1253", "windows-1253"),
    ("iso-8859-8", "iso-8859-8"),
    ("windows-1255", "windows-1255"),
    ("euc-jp", "euc-jp"),
    ("iso-2022-jp", "iso-2022-jp"),
    ("shift-jis", "shift-jis"),
    ("euc-kr", "euc-kr"),
    ("macintosh", "macintosh"),
    ("iso-8859-10", "iso-8859-10"),
    ("iso-8859-16", "iso-8859-16"),
    ("windows-874", "cp874"),
    ("windows-1254", "windows-1254"),
    ("windows-1258", "windows-1258"),
    ("iso-8859-1", "iso-8859-1"),
    ("windows-1252", "windows-1252"),
    ("iso-8859-3", "iso-8859-3"),
]
# Please keep in sync with modules/database/components/export/TableCSVExporter.vue
SUPPORTED_CSV_COLUMN_SEPARATORS = [
    (",", ","),
    (";", ";"),
    ("|", "|"),
    ("tab", "\t"),
    ("record_separator", "\x1e"),
    ("unit_separator", "\x1f"),
]


class ExportedFileURLSerializerMixin(FileURLSerializerMixin):
    """
    When mixed in to a model serializer for an ExportJob this will add an url field
    with the actual usable url of the export job's file (if it has one).
    """

    def get_handler(self):
        return ExportHandler()


class ExportJobSerializer(ExportedFileURLSerializerMixin, serializers.ModelSerializer):
    status = serializers.SerializerMethodField(
        help_text="DEPRECATED: Use state instead"
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_status(self, instance):
        return instance.state

    class Meta:
        model = ExportJob
        fields = [
            "id",
            "table",
            "view",
            "exporter_type",
            "state",
            "status",
            "exported_file_name",
            "created_at",
            "progress_percentage",
            "url",
        ]


class DisplayChoiceField(serializers.ChoiceField):
    """
    Just like a choice field but returns the second value of each choice tuple when
    serialized.
    """

    def to_representation(self, obj):
        return self._choices[obj]


class BaseExporterOptionsSerializer(serializers.Serializer):
    view_id = fields.IntegerField(
        min_value=0,
        required=False,
        allow_null=True,
        help_text="Optional: The view for this table to export using its filters, "
        "sorts and other view specific settings.",
    )
    exporter_type = fields.ChoiceField(
        choices=lazy(table_exporter_registry.get_types, list)(),
        help_text="The file type to export to.",
    )
    # Map to the python encoding aliases at the same time by using a DisplayChoiceField
    export_charset = DisplayChoiceField(
        choices=SUPPORTED_EXPORT_CHARSETS,
        default="utf-8",
        help_text="The character set to use when creating the export file.",
    )
    filters = PublicViewFiltersSerializer(
        required=False,
        allow_null=True,
        help_text=lazy(
            lambda: get_filters_object_description(True, False),
            str,
        )(),
    )
    order_by = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optionally the rows can be ordered by provided field ids separated "
        "by comma. By default a field is ordered in ascending (A-Z) order, but by "
        "prepending the field with a '-' it can be ordered descending (Z-A).",
    )
    fields = serializers.ListField(
        required=False,
        allow_null=True,
        child=serializers.IntegerField(),
        help_text="List of field IDs that must be included in the export, in the desired order.",
    )


class CsvExporterOptionsSerializer(BaseExporterOptionsSerializer):
    # For ease of use we expect the JSON to contain human typeable forms of each
    # different separator instead of the unicode character itself. By using the
    # DisplayChoiceField we can then map this to the actual separator character by
    # having those be the second value of each choice tuple.
    csv_column_separator = DisplayChoiceField(
        choices=SUPPORTED_CSV_COLUMN_SEPARATORS,
        default=",",
        help_text="The value used to separate columns in the resulting csv file.",
    )
    csv_include_header = fields.BooleanField(
        default=True,
        help_text="Whether or not to generate a header row at the top of the csv file.",
    )
