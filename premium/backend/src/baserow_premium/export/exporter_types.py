import json
from collections import OrderedDict
from typing import List, Optional, Type

import zipstream
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler

from baserow.config.settings.base import BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL
from baserow.contrib.database.api.export.serializers import (
    BaseExporterOptionsSerializer,
)
from baserow.contrib.database.export.file_writer import FileWriter, QuerysetSerializer
from baserow.contrib.database.export.registries import TableExporter
from baserow.contrib.database.export.utils import view_is_publicly_exportable
from baserow.contrib.database.fields.field_helpers import prepare_files_for_export
from baserow.contrib.database.fields.field_types import FileFieldType
from baserow.contrib.database.views.view_types import GridViewType
from baserow.core.storage import ExportZipFile, get_default_storage

from .serializers import ExcelExporterOptionsSerializer, FileExporterOptionsSerializer
from .utils import get_unique_name, safe_xml_tag_name, to_xml


class PremiumTableExporter(TableExporter):
    def before_job_create(self, user, table, view, export_options):
        """
        Checks if the related user access to a valid license before the job is created.
        """

        if view_is_publicly_exportable(user, view):
            # No need to check if the workspace has the license if the view is
            # publicly exportable because then we should always allow it, regardless
            # of the license.
            pass
        else:
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

        from openpyxl import Workbook

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


class FileQuerysetSerializer(QuerysetSerializer):
    can_handle_rich_value = True

    def write_to_file(
        self,
        file_writer: FileWriter,
        export_charset: str = "utf-8",
        organize_files: bool = True,
    ):
        """
        Writes files from the queryset to a zip archive. Will create a directory
        structure based on field names and include all files found in the rows.

        :param file_writer: The FileWriter instance to write to.
        :param export_charset: The charset to use for writing metadata.
        :param organize_files: Whether or not to group files by row id in the export
        """

        file_writer.update_check()

        storage = get_default_storage()
        field_serializers = []

        zip_file = ExportZipFile(
            compress_level=BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
            compress_type=zipstream.ZIP_DEFLATED,
        )

        file_fields = []
        # Get list of file-type fields
        for field_object in self.ordered_field_objects:
            if isinstance(field_object["type"], FileFieldType):
                file_fields.append(field_object)
                field_serializers.append(self._get_field_serializer(field_object))

        progress = 0

        def write_row(row, is_last):
            file_data = {}
            row_folder = f"row_{row.id}/" if organize_files else ""

            for file_field_data in file_fields:
                file_field = file_field_data["type"]

                records = file_field.get_internal_value_from_db(
                    row, file_field_data["name"]
                )
                file_serialized_data = prepare_files_for_export(
                    records,
                    {},
                    zip_file,
                    storage,
                    row_folder,
                )
                for file in file_serialized_data:
                    file_data[file["name"]] = file["size"]
            return file_data

        # processing rows is 15% of total progress
        processed_files = file_writer.write_rows(
            self.queryset, write_row, progress_weight=15
        )
        unique_files = {key: value for d in processed_files for key, value in d.items()}
        total_size = sum(unique_files.values()) or 1

        # 85% for writing chunks
        for chunk in zip_file:
            size = len(chunk)
            progress += size / total_size * 85
            file_writer._file.write(chunk)
            file_writer._check_and_update_job(15 + progress, 100)


class FileTableExporter(PremiumTableExporter):
    type = "file"

    @property
    def option_serializer_class(self) -> Type[BaseExporterOptionsSerializer]:
        return FileExporterOptionsSerializer

    @property
    def can_export_table(self) -> bool:
        return True

    @property
    def supported_views(self) -> List[str]:
        return [GridViewType.type]

    @property
    def file_extension(self) -> str:
        return ".zip"

    @property
    def queryset_serializer_class(self):
        return FileQuerysetSerializer
