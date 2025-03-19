from rest_framework import fields

from baserow.contrib.database.api.export.serializers import (
    BaseExporterOptionsSerializer,
)


class ExcelExporterOptionsSerializer(BaseExporterOptionsSerializer):
    excel_include_header = fields.BooleanField(
        default=True,
        help_text="Whether or not to generate the field names as header row at the top "
        "of the Excel file.",
    )


class FileExporterOptionsSerializer(BaseExporterOptionsSerializer):
    organize_files = fields.BooleanField(
        default=True,
        help_text="Whether or not to group files by row id in the export.",
    )
