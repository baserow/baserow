import json
from collections import OrderedDict
from typing import List, Optional, Type

from baserow_premium.license.handler import LicenseHandler
from openpyxl import Workbook

from baserow.contrib.database.api.export.serializers import (
    BaseExporterOptionsSerializer,
)
from baserow.contrib.database.export.file_writer import FileWriter, QuerysetSerializer
from baserow.contrib.database.export.registries import TableExporter
from baserow.contrib.database.views.view_types import GridViewType

from ..license.features import PREMIUM
from .serializers import ExcelExporterOptionsSerializer
from .utils import get_unique_name, safe_xml_tag_name, to_xml


class PremiumTableExporter(TableExporter):
    def before_job_create(self, user, table, view, export_options):
        """
        Checks if the related user access to a valid license before the job is created.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, user, table.database.workspace
        )
        super().before_job_create(user, table, view, export_options)


class JSONQuerysetSerializer(QuerysetSerializer):
    can_handle_rich_value = True

    def write_to_file(self, file_writer: FileWriter, export_charset="utf-8"):
        """
        Writes the queryset to the provided file in json format. Will generate
        semi-structured json based on the fields in the queryset.
        The root element is a json list and will look like:
        [
            {...},
            {...}
        ]
        Where each row in the queryset is a dict of key-values in the returned json
        array.

        :param file_writer: The file writer to use to do the writing.
        :param export_charset: The charset to write to the file using.
        """

        file_writer.write("[\n", encoding=export_charset)

        def write_row(row, last_row):
            data = {}
            for field_serializer in self.field_serializers:
                _, field_name, field_csv_value = field_serializer(row)
                field_name = get_unique_name(data, field_name, separator=" ")
                data[field_name] = field_csv_value

            file_writer.write(json.dumps(data, indent=4), encoding=export_charset)
            if not last_row:
                file_writer.write(",\n", encoding=export_charset)

        file_writer.write_rows(self.queryset, write_row)
        file_writer.write("\n]\n", encoding=export_charset)


class JSONTableExporter(PremiumTableExporter):
    type = "json"

    @property
    def queryset_serializer_class(self):
        return JSONQuerysetSerializer

    @property
    def option_serializer_class(self) -> Type[BaseExporterOptionsSerializer]:
        return BaseExporterOptionsSerializer

    @property
    def can_export_table(self) -> bool:
        return True

    @property
    def supported_views(self) -> List[str]:
        return [GridViewType.type]

    @property
    def file_extension(self) -> str:
        return ".json"


class XMLQuerysetSerializer(QuerysetSerializer):
    can_handle_rich_value = True

    def write_to_file(self, file_writer: FileWriter, export_charset="utf-8"):
        """
        Writes the queryset to the provided file in xml format. Will generate
        semi-structured xml based on the fields in the queryset. Each separate row in
        the queryset will have an xml element like so:
        <rows>
            <row>...</row>
            <row>...</row>
        </rows>

        :param file_writer: The file writer to use to do the writing.
        :param export_charset: The charset to write to the file using.
        """

        file_writer.write(
            f'<?xml version="1.0" encoding="{export_charset}" ?>\n<rows>\n',
            encoding=export_charset,
        )

        def write_row(row, _):
            data = OrderedDict()
            for field_serializer in self.field_serializers:
                _, field_name, field_xml_value = field_serializer(row)
                field_name = safe_xml_tag_name(
                    field_name, "field-", _.replace("_", "-")
                )
                field_name = get_unique_name(data, field_name, separator="-")
                data[field_name] = field_xml_value

            row_xml = to_xml(
                {"row": data},
            )
            file_writer.write(row_xml + "\n", encoding=export_charset)

        file_writer.write_rows(self.queryset, write_row)
        file_writer.write("</rows>\n", encoding=export_charset)


class XMLTableExporter(PremiumTableExporter):
    type = "xml"

    @property
    def queryset_serializer_class(self):
        return XMLQuerysetSerializer

    @property
    def option_serializer_class(self) -> Type[BaseExporterOptionsSerializer]:
        return BaseExporterOptionsSerializer

    @property
    def can_export_table(self) -> bool:
        return True

    @property
    def supported_views(self) -> List[str]:
        return [GridViewType.type]

    @property
    def file_extension(self) -> str:
        return ".xml"


class ExcelQuerysetSerializer(QuerysetSerializer):
    def __init__(self, queryset, ordered_field_objects):
        super().__init__(queryset, ordered_field_objects)

        self.headers = OrderedDict({"id": "id"})

        for field_object in ordered_field_objects:
            field_database_name = field_object["name"]
            field_display_name = field_object["field"].name
            self.headers[field_database_name] = field_display_name

    def write_to_file(
        self,
        file_writer: FileWriter,
        export_charset: Optional[str] = None,
        excel_include_header: bool = False,
    ):
        """
        :param file_writer: The FileWriter instance to write to.
        :param export_charset:
        :param excel_include_header: Whether or not to include a header in the resulting
        Excel file.
        """

        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet()

        if excel_include_header:
            worksheet.append(list(self.headers.values()))

        def write_row(row, _):
            data = []
            for field_serializer in self.field_serializers:
                _, _, field_human_value = field_serializer(row)
                data.append(str(field_human_value))
            worksheet.append(data)

        file_writer.write_rows(self.queryset, write_row)

        workbook.save(file_writer._file)


class ExcelTableExporter(PremiumTableExporter):
    type = "excel"

    @property
    def option_serializer_class(self) -> Type[BaseExporterOptionsSerializer]:
        return ExcelExporterOptionsSerializer

    @property
    def can_export_table(self) -> bool:
        return True

    @property
    def supported_views(self) -> List[str]:
        return [GridViewType.type]

    @property
    def file_extension(self) -> str:
        return ".xlsx"

    @property
    def queryset_serializer_class(self):
        return ExcelQuerysetSerializer
