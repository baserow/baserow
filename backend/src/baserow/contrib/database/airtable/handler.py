import json
import re
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from io import BytesIO, IOBase
from typing import Dict, List, Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import Storage

import requests
from requests import Response

from baserow.contrib.database.airtable.constants import (
    AIRTABLE_API_BASE_URL,
    AIRTABLE_BASE_URL,
    AIRTABLE_DOWNLOAD_FILE_TYPE_ATTACHMENT_ENDPOINT,
    AIRTABLE_DOWNLOAD_FILE_TYPE_FETCH,
    AIRTABLE_EXPORT_JOB_CONVERTING,
    AIRTABLE_EXPORT_JOB_DOWNLOADING_BASE,
    AIRTABLE_EXPORT_JOB_DOWNLOADING_FILES,
)
from baserow.contrib.database.airtable.registry import (
    AirtableColumnType,
    airtable_column_type_registry,
    airtable_view_type_registry,
)
from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.export_serialized import DatabaseExportSerializedStructure
from baserow.contrib.database.fields.field_types import FieldType, field_type_registry
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.models import Database
from baserow.core.export_serialized import CoreExportSerializedStructure
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.registries import ImportExportConfig
from baserow.core.utils import (
    ChildProgressBuilder,
    Progress,
    remove_invalid_surrogate_characters,
)

from .config import AirtableImportConfig
from .exceptions import (
    AirtableBaseNotPublic,
    AirtableBaseRequiresAuthentication,
    AirtableImportNotRespectingConfig,
    AirtableShareIsNotABase,
    AirtableSkipCellValue,
    FileDownloadFailed,
)
from .import_report import (
    ERROR_TYPE_OTHER,
    ERROR_TYPE_UNSUPPORTED_FEATURE,
    SCOPE_AUTOMATIONS,
    SCOPE_CELL,
    SCOPE_FIELD,
    SCOPE_INTERFACES,
    SCOPE_VIEW,
    AirtableImportReport,
)
from .models import DownloadFile
from .utils import parse_json_and_remove_invalid_surrogate_characters

User = get_user_model()


BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:95.0) Gecko/20100101 Firefox/95.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}


def download_airtable_file(
    name: str,
    download_file: DownloadFile,
    init_data: dict,
    request_id: str,
    cookies: dict,
    headers: dict = None,
) -> Response:
    """
    Downloads a file from Airtable using either direct URL fetch or
    attachment endpoint.

    :param name: The name of the file to download.
    :param download_file: The DownloadFile object containing download
        information
    :param init_data: The init_data returned by the initially
        requested shared base
    :param request_id: The request_id returned by the initially
        requested shared base
    :param cookies: The cookies dict returned by the initially
        requested shared base
    :param headers: Optional headers to use for the request
    :return: The response object from the download request
    :raises FileDownloadFailed: When the file could not be downloaded.
    """

    if download_file.type == AIRTABLE_DOWNLOAD_FILE_TYPE_FETCH:
        response = requests.get(download_file.url, headers=headers)  # nosec B113
    elif download_file.type == AIRTABLE_DOWNLOAD_FILE_TYPE_ATTACHMENT_ENDPOINT:
        response = AirtableHandler.fetch_attachment(
            row_id=download_file.row_id,
            column_id=download_file.column_id,
            attachment_id=download_file.attachment_id,
            init_data=init_data,
            request_id=request_id,
            cookies=cookies,
            headers=headers,
        )
    else:
        raise FileDownloadFailed(
            f"Unknown download file type: {download_file.type}",
        )
    if response.status_code not in [HTTPStatus.OK, HTTPStatus.PARTIAL_CONTENT]:
        raise FileDownloadFailed(
            f"File {name} could not be downloaded (HTTP {response.status_code}).",
        )

    return response


class AirtableFileImport:
    """
    A file-like object (we only need open and close methods) that facilitates on-demand
    file downloads from Airtable for re-uploading to Baserow. This avoids downloading
    all files at once, enabling efficient, one-by-one downloads as needed during the
    import process.
    """

    def __init__(self, init_data, request_id, cookies, headers=BASE_HEADERS):
        self.files_to_download = {}
        self.init_data = init_data
        self.request_id = request_id
        self.cookies = cookies
        self.headers = headers

    def add_files(self, files_to_download):
        self.files_to_download.update(files_to_download)

    @contextmanager
    def open(self, name):
        if name is None:
            raise ValueError(f"No file with name {name} found.")

        # Files for which check failed are excluded from the
        # files_to_download dict
        # Those missing files are already included in the import report
        if name not in self.files_to_download:
            raise KeyError(f"File '{name}' not found in files_to_download")

        response = download_airtable_file(
            name=name,
            download_file=self.files_to_download[name],
            init_data=self.init_data,
            request_id=self.request_id,
            cookies=self.cookies,
            headers=BASE_HEADERS,
        )

        stream = BytesIO(response.content)
        try:
            yield stream
        finally:
            stream.close()

    def close(self):
        pass


class AirtableHandler:
    @staticmethod
    def fetch_publicly_shared_base(
        share_id: str, config: AirtableImportConfig
    ) -> Tuple[str, dict, dict]:
        """
        Fetches the initial page of the publicly shared page. It will parse the content
        and extract and return the initial data needed for future requests.

        :param share_id: The Airtable share id of the page that must be fetched. Note
            that the base must be shared publicly. The id stars with `shr`.
        :param config: Additional configuration related to the import.
        :raises AirtableShareIsNotABase: When the URL doesn't point to a shared base.
        :return: The request ID, initial data and the cookies of the response.
        """

        url = f"{AIRTABLE_BASE_URL}/{share_id}"
        response = requests.get(
            url,
            headers=BASE_HEADERS,
            cookies=config.get_session_cookies(),
            allow_redirects=False,
        )  # nosec B113

        if response.status_code == 302 and response.headers.get(
            "Location", ""
        ).startswith("/login"):
            raise AirtableBaseRequiresAuthentication(
                f"The base with share id {share_id} requires authentication."
            )
        elif not response.ok:
            raise AirtableBaseNotPublic(
                f"The base with share id {share_id} is not public."
            )

        decoded_content = remove_invalid_surrogate_characters(response.content)

        request_id_re = re.search('requestId: "(.*)",', decoded_content)
        if request_id_re is None:
            raise AirtableShareIsNotABase("The `shared_id` is not a valid base link.")
        request_id = request_id_re.group(1)
        raw_init_data = re.search("window.initData = (.*);\n", decoded_content).group(1)
        init_data = json.loads(raw_init_data)
        cookies = response.cookies.get_dict()
        cookies.update(**config.get_session_cookies())

        if "sharedApplicationId" not in raw_init_data:
            raise AirtableShareIsNotABase("The `shared_id` is not a base.")

        return request_id, init_data, cookies

    @staticmethod
    def make_airtable_request(
        init_data: dict, request_id: str, headers=None, **kwargs
    ) -> Response:
        """
        Helper method to make a valid request to to Airtable with the correct headers
        and params.

        :param init_data: The init_data returned by the initially requested shared base.
        :param request_id: The request_id returned by the initially requested shared
            base.
        :param headers: The headers to be passed into the `requests` request.
        :param kwargs: THe kwargs that must be passed into the `requests.get` method.
        :return: The requests Response object related to the request.
        """

        if headers is None:
            headers = BASE_HEADERS

        application_id = list(init_data["rawApplications"].keys())[0]
        client_code_version = init_data["codeVersion"]
        page_load_id = init_data["pageLoadId"]
        access_policy = json.loads(init_data["accessPolicy"])

        params = kwargs.get("params", {})
        params["accessPolicy"] = json.dumps(access_policy)
        params["request_id"] = request_id

        return requests.get(
            headers={
                "x-airtable-application-id": application_id,
                "x-airtable-client-queue-time": "45",
                "x-airtable-inter-service-client": "webClient",
                "x-airtable-inter-service-client-code-version": client_code_version,
                "x-airtable-page-load-id": page_load_id,
                "X-Requested-With": "XMLHttpRequest",
                "x-time-zone": "Europe/Amsterdam",
                "x-user-locale": "en",
                **headers,
            },
            timeout=3 * 60,  # it can take quite a while for Airtable to respond.
            **kwargs,
        )  # nosec

    @staticmethod
    def fetch_table_data(
        table_id: str,
        init_data: dict,
        request_id: str,
        cookies: dict,
        fetch_application_structure: bool,
        stream=True,
    ) -> Response:
        """
        Fetches the data or application structure of a publicly shared Airtable table.

        :param table_id: The Airtable table id that must be fetched. The id starts with
            `tbl`.
        :param init_data: The init_data returned by the initially requested shared base.
        :param request_id: The request_id returned by the initially requested shared
            base.
        :param cookies: The cookies dict returned by the initially requested shared
            base.
        :param fetch_application_structure: Indicates whether the application structure
            must also be fetched. If True, the schema of all the tables and views will
            be included in the response. Note that the structure of the response is
            different because it will wrap application/table schema around the table
            data. The table data will be available at the path `data.tableDatas.0.rows`.
            If False, the only the table data will be included in the response JSON,
            which will be available at the path `data.rows`.
        :param stream: Indicates whether the request should be streamed. This could be
            useful if we want to show a progress bar. It will directly be passed into
            the `requests` request.
        :return: The `requests` response containing the result.
        """

        application_id = list(init_data["rawApplications"].keys())[0]
        stringified_object_params = {
            "includeDataForViewIds": None,
            "shouldIncludeSchemaChecksum": True,
            "mayOnlyIncludeRowAndCellDataForIncludedViews": False,
        }

        if fetch_application_structure:
            stringified_object_params["includeDataForTableIds"] = [table_id]
            url = f"{AIRTABLE_API_BASE_URL}/application/{application_id}/read"
        else:
            url = f"{AIRTABLE_API_BASE_URL}/table/{table_id}/readData"

        response = AirtableHandler.make_airtable_request(
            init_data,
            request_id,
            url=url,
            stream=stream,
            params={
                "stringifiedObjectParams": json.dumps(stringified_object_params),
            },
            cookies=cookies,
        )
        return response

    @staticmethod
    def fetch_view_data(
        view_id: str,
        init_data: dict,
        request_id: str,
        cookies: dict,
        stream=True,
    ) -> Response:
        """
        :param view_id: The Airtable view id that must be fetched. The id starts with
            `viw`.
        :param init_data: The init_data returned by the initially requested shared base.
        :param request_id: The request_id returned by the initially requested shared
            base.
        :param cookies: The cookies dict returned by the initially requested shared
            base.
        :param stream: Indicates whether the request should be streamed. This could be
            useful if we want to show a progress bar. It will directly be passed into
            the `requests` request.
        :return: The `requests` response containing the result.
        """

        stringified_object_params = {}
        url = f"{AIRTABLE_API_BASE_URL}/view/{view_id}/readData"

        response = AirtableHandler.make_airtable_request(
            init_data,
            request_id,
            url=url,
            stream=stream,
            params={"stringifiedObjectParams": json.dumps(stringified_object_params)},
            cookies=cookies,
        )
        return response

    @staticmethod
    def fetch_attachment(
        row_id: str,
        column_id: str,
        attachment_id: str,
        init_data: dict,
        request_id: str,
        cookies: dict,
        stream=True,
        headers=None,
    ) -> Response:
        """
        :param row_id: The Airtable row id of the attachment that must be fetched.
            The id starts with `rec`.
        :param column_id: The Airtable column id of the attachment that must be
            fetched. The id starts with `rec`.
        :param attachment_id: The Airtable attachment id that must be fetched. The id
            starts with `rec`.
        :param init_data: The init_data returned by the initially requested shared base.
        :param request_id: The request_id returned by the initially requested shared
            base.
        :param cookies: The cookies dict returned by the initially requested shared
            base.
        :param stream: Indicates whether the request should be streamed. This could be
            useful if we want to show a progress bar. It will directly be passed into
            the `requests` request.
        :param headers: The headers to be passed into the `requests` request.
        :return: The `requests` response containing the result.
        """

        stringified_object_params = {
            "columnId": column_id,
            "attachmentId": attachment_id,
        }
        url = f"{AIRTABLE_API_BASE_URL}/row/{row_id}/downloadAttachment"

        response = AirtableHandler.make_airtable_request(
            init_data,
            request_id,
            url=url,
            stream=stream,
            params={"stringifiedObjectParams": json.dumps(stringified_object_params)},
            cookies=cookies,
            allow_redirects=True,
            headers=headers,
        )
        return response

    @staticmethod
    def extract_schema(exports: List[dict]) -> Tuple[dict, dict]:
        """
        Loops over the provided exports and finds the export containing the application
        schema. That will be extracted and the rest of the table data will be moved
        into a dict where the key is the table id.

        :param exports: A list containing all the exports as dicts.
        :return: The database schema and a dict containing the table data.
        """

        schema = None
        tables = {}

        for export in exports:
            if "appBlanket" in export["data"]:
                table_data = export["data"].pop("tableDatas")[0]
                schema = export["data"]
            else:
                table_data = export["data"]

            tables[table_data["id"]] = table_data

        if schema is None:
            raise ValueError("None of the provided exports contains the schema.")

        return schema, tables

    @staticmethod
    def to_baserow_field(
        table: dict,
        column: dict,
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ) -> Union[Tuple[None, None, None], Tuple[Field, FieldType, AirtableColumnType]]:
        """
        Converts the provided Airtable column dict to the right Baserow field object.

        :param table: The Airtable table dict. This is needed to figure out whether the
            field is the primary field.
        :param column: The Airtable column dict. These values will be converted to
            Baserow format.
        :param config: Additional configuration related to the import.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :return: The converted Baserow field, field type and the Airtable column type.
        """

        (
            baserow_field,
            airtable_column_type,
        ) = airtable_column_type_registry.from_airtable_column_to_serialized(
            table, column, config, import_report
        )

        if baserow_field is None:
            return None, None, None

        baserow_field_type = field_type_registry.get_by_model(baserow_field)

        try:
            order = next(
                index
                for index, value in enumerate(table["meaningfulColumnOrder"])
                if value["columnId"] == column["id"]
            )
        except StopIteration:
            order = 32767

        baserow_field.id = column["id"]
        baserow_field.pk = 0
        baserow_field.name = column["name"]
        baserow_field.order = order
        baserow_field.description = column.get("description", None) or None
        baserow_field.primary = (
            baserow_field_type.can_be_primary_field(baserow_field)
            and table["primaryColumnId"] == column["id"]
        )

        return baserow_field, baserow_field_type, airtable_column_type

    @staticmethod
    def to_baserow_row_export(
        table: dict,
        row_id_mapping: Dict[str, Dict[str, int]],
        column_mapping: Dict[str, dict],
        row: dict,
        index: int,
        files_to_download: Dict[str, DownloadFile],
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ) -> dict:
        """
        Converts the provided Airtable record to a Baserow row by looping over the field
        types and executing the `from_airtable_column_value_to_serialized` method.

        :param table: The Airtable table dict.
        :param row_id_mapping: A mapping containing the table as key as the value is
            another mapping where the Airtable row id maps the Baserow row id.
        :param column_mapping: A mapping where the Airtable column id is the value and
            the value containing another mapping with the Airtable column dict and
            Baserow field dict.
        :param row: The Airtable row that must be converted a Baserow row.
        :param index: The index the row has in the table.
        :param files_to_download: A dict that contains all the user file URLs that must
            be downloaded. The key is the file name and the value the URL. Additional
            files can be added to this dict.
        :param config: Additional configuration related to the import.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :return: The converted row in Baserow export format.
        """

        created_on = row.get("createdTime")

        if created_on:
            created_on = (
                datetime.strptime(created_on, "%Y-%m-%dT%H:%M:%S.%fZ")
                .replace(tzinfo=timezone.utc)
                .isoformat()
            )

        exported_row = DatabaseExportSerializedStructure.row(
            id=row["id"],
            order=f"{index + 1}.00000000000000000000",
            created_on=created_on,
            updated_on=None,
        )

        # Some empty rows don't have the `cellValuesByColumnId` property because it
        # doesn't contain values, hence the fallback to prevent failing hard.
        cell_values = row.get("cellValuesByColumnId", {})

        for column_id, mapping_values in column_mapping.items():
            airtable_column_type = mapping_values["airtable_column_type"]
            args = [
                row_id_mapping,
                table,
                row,
                mapping_values["raw_airtable_column"],
                mapping_values["baserow_field"],
                cell_values.get(column_id, None),
                files_to_download,
                config,
                import_report,
            ]

            try:
                # The column_id typically doesn't exist in the `cell_values` if the
                # value is empty in Airtable.
                if column_id in cell_values:
                    baserow_serialized_value = (
                        airtable_column_type.to_baserow_export_serialized_value(*args)
                    )
                else:
                    # remove the cell_value because that one is not accepted in the args
                    # of this method.
                    args.pop(5)
                    baserow_serialized_value = (
                        airtable_column_type.to_baserow_export_empty_value(*args)
                    )
                exported_row[f"field_{column_id}"] = baserow_serialized_value
            except AirtableSkipCellValue:
                # If the `AirtableSkipCellValue` is raised, then the cell value must
                # not be included in the export. This is the default behavior for
                # `to_baserow_export_empty_value`, but in some cases, a specific empty
                # value must be returned.
                pass

        return exported_row

    @staticmethod
    def prepare_downloadable_files(
        files_to_download: Dict[str, DownloadFile],
        init_data: dict,
        request_id: str,
        cookies: dict,
        config: AirtableImportConfig,
        progress_builder: Optional[ChildProgressBuilder] = None,
        files_buffer: Union[None, IOBase] = None,
        import_report: AirtableImportReport = None,
        field_mapping_per_table: dict = None,
        exported_tables: list = None,
        row_id_mapping: Dict[str, Dict[str, int]] = None,
    ) -> BytesIO:
        """
        This method was used to download the files, but now it only collects
        them to be downloaded later so we can upload files to our storage one by one
        so that the memory needed is less.
        #TODO: Clean this up, rename the method properly and remove the old code.

        :param files_to_download: A dict that contains all the user file URLs that must
            be downloaded. The key is the file name and the value the URL. Additional
            files can be added to this dict.
        :param init_data: The init_data returned by the initially requested shared base.
        :param request_id: The request_id returned by the initially requested shared
            base.
        :param cookies: The cookies dict returned by the initially requested shared
            base.
        :param config: Additional configuration related to the import.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :param files_buffer: Optionally a file buffer can be provided to store the
            downloaded files in. They will be stored in memory if not provided.
        :return: An in memory buffer as zip file containing all the user files.
        """

        progress = ChildProgressBuilder.build(progress_builder, child_total=1)

        # Prevent downloading any file if desired. This can cause the import to fail,
        # but that's intentional because that way it can easily be discovered that the
        # `config.skip_files` is respected.
        if config.skip_files:
            if len(files_to_download.keys()) > 0:
                raise AirtableImportNotRespectingConfig(
                    "Files have been added to the `files_to_download`, but "
                    "`config.skip_files` is True. This is probably a mistake in the "
                    "code, accidentally adding files to the `files_to_download`."
                )

        file_archive = AirtableFileImport(
            init_data=init_data,
            request_id=request_id,
            cookies=cookies,
            headers=BASE_HEADERS,
        )

        failed_files = []
        for file_name, download_file in files_to_download.items():
            headers = BASE_HEADERS.copy()
            headers["Range"] = "bytes=0-5"

            try:
                download_airtable_file(
                    file_name, download_file, init_data, request_id, cookies, headers
                )
            except FileDownloadFailed:
                field_name = ""
                table_name = ""
                baserow_row_id = download_file.row_id

                for table_id, field_mapping in field_mapping_per_table.items():
                    if download_file.column_id in field_mapping:
                        field_info = field_mapping[download_file.column_id]
                        field_name = field_info["baserow_field"].name

                        for exported_table in exported_tables:
                            if exported_table["id"] == table_id:
                                table_name = exported_table["name"]
                                break

                        if row_id_mapping and table_id in row_id_mapping:
                            baserow_row_id = row_id_mapping[table_id].get(
                                download_file.row_id, download_file.row_id
                            )
                        break

                import_report.add_failed(
                    "File",
                    SCOPE_CELL,
                    table_name,
                    ERROR_TYPE_OTHER,
                    f"Field: {field_name}, Row: {baserow_row_id}, File: {file_name}",
                )
                failed_files.append(file_name)

        for file_name in failed_files:
            files_to_download.pop(file_name, None)

        file_archive.add_files(files_to_download)
        progress.increment(state=AIRTABLE_EXPORT_JOB_DOWNLOADING_FILES)

        return file_archive

    @classmethod
    def _parse_table_fields(
        cls,
        schema: dict,
        converting_progress: Progress,
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ):
        field_mapping_per_table = {}
        for table_index, table in enumerate(schema["tableSchemas"]):
            field_mapping = {}

            # Loop over all the columns in the table and try to convert them to Baserow
            # format.
            primary = None
            for column in table["columns"]:
                (
                    baserow_field,
                    baserow_field_type,
                    airtable_column_type,
                ) = cls.to_baserow_field(table, column, config, import_report)
                converting_progress.increment(state=AIRTABLE_EXPORT_JOB_CONVERTING)

                # None means that none of the field types know how to parse this field,
                # so we must ignore it.
                if baserow_field is None:
                    import_report.add_failed(
                        column["name"],
                        SCOPE_FIELD,
                        table["name"],
                        ERROR_TYPE_UNSUPPORTED_FEATURE,
                        f"""Field "{column['name']}" with field type {column["type"]} was not imported because it is not supported.""",
                    )
                    continue

                # The `baserow_field` is returning it it's specific form, but it doesn't
                # have the `content_type` property yet. This breaks all the `.specific`
                # behavior because an `id` is also not set.
                baserow_field.content_type = ContentType.objects.get_for_model(
                    baserow_field
                )

                # Construct a mapping where the Airtable column id is the key and the
                # value contains the raw Airtable column values, Baserow field and
                # the Baserow field type object for later use.
                field_mapping[column["id"]] = {
                    "baserow_field": baserow_field,
                    "baserow_field_type": baserow_field_type,
                    "raw_airtable_column": column,
                    "airtable_column_type": airtable_column_type,
                }
                if baserow_field.primary:
                    primary = baserow_field

            # There is always a primary field, but it could be that it's not compatible
            # with Baserow. In that case, we need to find an alternative field, or
            # create a new one.
            if primary is None:
                # First check if another field can act as the primary field type.
                found_existing_field = False
                for value in field_mapping.values():
                    if field_type_registry.get_by_model(
                        value["baserow_field"]
                    ).can_be_primary_field(value["baserow_field"]):
                        value["baserow_field"].primary = True
                        found_existing_field = True
                        import_report.add_failed(
                            value["baserow_field"].name,
                            SCOPE_FIELD,
                            table["name"],
                            ERROR_TYPE_UNSUPPORTED_FEATURE,
                            f"""Changed primary field to "{value["baserow_field"].name}" because the original primary field is incompatible.""",
                        )
                        break

                # If none of the existing fields can be primary, we will add a new
                # text field.
                if not found_existing_field:
                    airtable_column = {
                        "id": "primary_field",
                        "name": "Primary field (auto created)",
                        "type": "text",
                    }
                    (
                        baserow_field,
                        baserow_field_type,
                        airtable_column_type,
                    ) = cls.to_baserow_field(
                        table, airtable_column, config, import_report
                    )
                    baserow_field.primary = True
                    baserow_field.content_type = ContentType.objects.get_for_model(
                        baserow_field
                    )
                    field_mapping["primary_id"] = {
                        "baserow_field": baserow_field,
                        "baserow_field_type": baserow_field_type,
                        "raw_airtable_column": airtable_column,
                        "airtable_column_type": airtable_column_type,
                    }
                    import_report.add_failed(
                        baserow_field.name,
                        SCOPE_FIELD,
                        table["name"],
                        ERROR_TYPE_UNSUPPORTED_FEATURE,
                        f"""Created new primary field "{baserow_field.name}" because none of the provided fields are compatible.""",
                    )

            field_mapping_per_table[table["id"]] = field_mapping

        # Loop over all created fields, and post process them if needed. This is for
        # example needed for the link row field where the object must be enhanced with
        # the primary field of the related tables.
        for table_index, table in enumerate(schema["tableSchemas"]):
            field_mapping = field_mapping_per_table[table["id"]]

            for field_object in field_mapping.values():
                field_object["airtable_column_type"].after_field_objects_prepared(
                    field_mapping_per_table,
                    field_object["baserow_field"],
                    field_object["raw_airtable_column"],
                )

        return field_mapping_per_table

    @classmethod
    def _parse_rows_and_views(
        cls,
        schema: dict,
        tables: list,
        converting_progress: Progress,
        row_id_mapping: Dict[str, int],
        field_mapping_per_table: dict,
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ):
        # A list containing all the exported table in Baserow format.
        exported_tables = []

        # A dict containing all the user files that must be downloaded and added to a
        # zip file.
        files_to_download = {}

        # Loop over the table one more time to export the fields, rows, and views to
        # the serialized format. This must be done last after all the data is prepared
        # correctly.
        for table_index, table in enumerate(schema["tableSchemas"]):
            field_mapping = field_mapping_per_table[table["id"]]
            files_to_download_for_table = {}

            # Loop over all the fields and convert them to Baserow serialized format.
            exported_fields = [
                value["baserow_field_type"].export_serialized(value["baserow_field"])
                for value in field_mapping.values()
            ]

            # Loop over all the rows in the table and convert them to Baserow format. We
            # need to provide the `row_id_mapping` and `field_mapping` because there
            # could be references to other rows and fields. the
            # `files_to_download_for_table` is needed because every value could be
            # depending on additional files that must later be downloaded.
            exported_rows = []
            for row_index, row in enumerate(tables[table["id"]]["rows"]):
                exported_rows.append(
                    cls.to_baserow_row_export(
                        table,
                        row_id_mapping,
                        field_mapping,
                        row,
                        row_index,
                        files_to_download_for_table,
                        config,
                        import_report,
                    )
                )
                converting_progress.increment(state=AIRTABLE_EXPORT_JOB_CONVERTING)

            # Loop over all views to add them to them as failed to the import report
            # because the views are not yet supported.
            exported_views = []
            for view in table["views"]:
                table_data = tables[table["id"]]
                view_data = next(
                    (
                        view_data
                        for view_data in table_data["viewDatas"]
                        if view_data["id"] == view["id"]
                    )
                )
                serialized_view = (
                    airtable_view_type_registry.from_airtable_view_to_serialized(
                        field_mapping,
                        row_id_mapping,
                        table,
                        view,
                        view_data,
                        config,
                        import_report,
                    )
                )

                if serialized_view is None:
                    import_report.add_failed(
                        view["name"],
                        SCOPE_VIEW,
                        table["name"],
                        ERROR_TYPE_UNSUPPORTED_FEATURE,
                        f"View \"{view['name']}\" was not imported because "
                        f"{view['type']} is not supported.",
                    )
                    continue

                exported_views.append(serialized_view)

            exported_table = DatabaseExportSerializedStructure.table(
                id=table["id"],
                name=table["name"],
                order=table_index,
                fields=exported_fields,
                views=exported_views,
                rows=exported_rows,
                data_sync=None,
                field_rules=[],
            )
            exported_tables.append(exported_table)
            converting_progress.increment(state=AIRTABLE_EXPORT_JOB_CONVERTING)

            # Airtable can have a mapping of signed URLs for the uploaded files. The
            # mapping is provided in the table payload, and if it exists, we need
            # that URL for download instead of the one originally provided. If it
            # doesn't exist, we must use the fetch attachment endpoint.
            signed_user_content_urls = tables[table["id"]].get(
                "signedUserContentUrls", None
            )
            for file_name, download_file in files_to_download_for_table.items():
                url = download_file.url
                if (
                    signed_user_content_urls is not None
                    and url in signed_user_content_urls
                ):
                    download_file.url = signed_user_content_urls[url]
                elif signed_user_content_urls is None:
                    download_file.type = AIRTABLE_DOWNLOAD_FILE_TYPE_ATTACHMENT_ENDPOINT

                files_to_download[file_name] = download_file

        return exported_tables, files_to_download

    @classmethod
    def to_baserow_database_export(
        cls,
        init_data: dict,
        request_id: str,
        cookies: dict,
        schema: dict,
        tables: list,
        config: AirtableImportConfig,
        progress_builder: Optional[ChildProgressBuilder] = None,
        download_files_buffer: Union[None, IOBase] = None,
    ) -> Tuple[dict, IOBase]:
        """
        Converts the provided raw Airtable database dict to a Baserow export format and
        an in memory zip file containing all the downloaded user files.

        :param init_data: The init_data, extracted from the initial page related to the
            shared base.
        :param request_id: The request_id returned by the initially requested shared
            base.
        :param cookies: The cookies dict returned by the initially requested shared
            base.
        :param schema: An object containing the schema of the Airtable base.
        :param tables: a list containing the table data.
        :param config: Additional configuration related to the import.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :param download_files_buffer: Optionally a file buffer can be provided to store
            the downloaded files in. They will be stored in memory if not provided.
        :return: The converted Airtable base in Baserow export format and a zip file
            containing the user files.
        """

        # This instance allows collecting what we weren't able to import, like
        # incompatible fields, filters, etc. This will later be used to create a table
        # with an overview of what wasn't imported.
        import_report = AirtableImportReport()

        progress = ChildProgressBuilder.build(progress_builder, child_total=1000)
        converting_progress = progress.create_child(
            represents_progress=500,
            total=sum(
                [
                    # Mapping progress
                    len(tables[table["id"]]["rows"])
                    # Table column progress
                    + len(table["columns"])
                    # Table rows progress
                    + len(tables[table["id"]]["rows"])
                    # The table itself.
                    + 1
                    for table in schema["tableSchemas"]
                ]
            ),
        )

        # A mapping containing the Airtable table id as key and as value another mapping
        # containing with the key as Airtable row id and the value as new Baserow row
        # id. This mapping is created because Airtable has string row id that look like
        # "recAjnk3nkj5", but Baserow doesn't support string row id, so we need to
        # replace them with a unique int. We need a mapping because there could be
        # references to the row.
        row_id_mapping = defaultdict(dict)
        for index, table in enumerate(schema["tableSchemas"]):
            for row_index, row in enumerate(tables[table["id"]]["rows"]):
                new_id = row_index + 1
                row_id_mapping[table["id"]][row["id"]] = new_id
                row["airtable_record_id"] = row["id"]
                row["id"] = new_id
                converting_progress.increment(state=AIRTABLE_EXPORT_JOB_CONVERTING)

        field_mapping_per_table = AirtableHandler._parse_table_fields(
            schema, converting_progress, config, import_report
        )
        exported_tables, files_to_download = AirtableHandler._parse_rows_and_views(
            schema,
            tables,
            converting_progress,
            row_id_mapping,
            field_mapping_per_table,
            config,
            import_report,
        )

        # Just to be really clear that the automations and interfaces are not included.
        import_report.add_failed(
            "All automations",
            SCOPE_AUTOMATIONS,
            "",
            ERROR_TYPE_UNSUPPORTED_FEATURE,
            "Baserow doesn't support automations.",
        )
        import_report.add_failed(
            "All interfaces",
            SCOPE_INTERFACES,
            "",
            ERROR_TYPE_UNSUPPORTED_FEATURE,
            "Baserow doesn't support interfaces.",
        )

        # Convert the import report to the serialized export format of a Baserow table,
        # so that a new table is created with the import report result for the user to
        # see.
        exported_tables.append(
            import_report.get_baserow_export_table(len(schema["tableSchemas"]) + 1)
        )

        exported_database = CoreExportSerializedStructure.application(
            id=1,
            name=init_data["rawApplications"][init_data["sharedApplicationId"]]["name"],
            order=1,
            type=DatabaseApplicationType.type,
        )
        exported_database.update(
            **DatabaseExportSerializedStructure.database(tables=exported_tables)
        )

        report_items_count = len(import_report.items)

        # After all the tables have been converted to Baserow format, we must
        # download all the user files. Because we first want to the whole conversion to
        # be completed and because we want this to be added to the progress bar, this is
        # done last.
        user_files_zip = cls.prepare_downloadable_files(
            files_to_download,
            init_data,
            request_id,
            cookies,
            config,
            progress.create_child_builder(represents_progress=500),
            download_files_buffer,
            import_report,
            field_mapping_per_table,
            exported_tables,
            row_id_mapping,
        )

        import_report.append_items_to_exported_table(
            exported_database, import_report.items[report_items_count:]
        )

        return exported_database, user_files_zip

    @classmethod
    def fetch_and_combine_airtable_data(
        cls,
        share_id: str,
        config: AirtableImportConfig,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Union[dict, dict, list]:
        """
        :param share_id: The shared Airtable ID of which the data must be fetched.
        :param config: Additional configuration related to the import.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :return: The fetched init_data, schema, and list of tables enrichted with all
            the row and view data.
        """

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)

        # Execute the initial request to obtain the initial data that's needed to
        # make the request.
        request_id, init_data, cookies = cls.fetch_publicly_shared_base(
            share_id, config
        )
        progress.increment(state=AIRTABLE_EXPORT_JOB_DOWNLOADING_BASE)

        # Loop over all the tables and make a request for each table to obtain the raw
        # Airtable table data.
        tables = []
        raw_tables = list(
            init_data["singleApplicationScaffoldingData"]["tableById"].keys()
        )
        for index, table_id in enumerate(
            progress.track(
                represents_progress=49,
                state=AIRTABLE_EXPORT_JOB_DOWNLOADING_BASE,
                iterable=raw_tables,
            )
        ):
            response = cls.fetch_table_data(
                table_id=table_id,
                init_data=init_data,
                request_id=request_id,
                cookies=cookies,
                # At least one request must also fetch the application structure that
                # contains the schema of all the tables, so we do this for the first
                # table.
                fetch_application_structure=index == 0,
                stream=False,
            )
            json_decoded_content = parse_json_and_remove_invalid_surrogate_characters(
                response
            )

            tables.append(json_decoded_content)

        # Split database schema from the tables because we need this to be separated
        # later on.
        schema, tables = cls.extract_schema(tables)

        # Collect which for which view the data is missing, so that they can be
        # fetched while respecting the progress afterward.
        view_data_to_fetch = []
        for table in schema["tableSchemas"]:
            existing_view_data = [
                view_data["id"] for view_data in tables[table["id"]]["viewDatas"]
            ]
            for view in table["views"]:
                # Skip the view data that has already been loaded.
                if view["id"] in existing_view_data:
                    continue

                view_data_to_fetch.append((table["id"], view["id"]))

        # Fetch the missing view data, and add them to the table object so that we have
        # a complete object.
        for table_id, view_id in progress.track(
            represents_progress=50,
            state=AIRTABLE_EXPORT_JOB_DOWNLOADING_BASE,
            iterable=view_data_to_fetch,
        ):
            response = cls.fetch_view_data(
                view_id=view_id,
                init_data=init_data,
                request_id=request_id,
                cookies=cookies,
                stream=False,
            )
            json_decoded_content = parse_json_and_remove_invalid_surrogate_characters(
                response
            )
            tables[table_id]["viewDatas"].append(json_decoded_content["data"])

        return init_data, request_id, cookies, schema, tables

    @classmethod
    def import_from_airtable_to_workspace(
        cls,
        workspace: Workspace,
        share_id: str,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
        download_files_buffer: Optional[IOBase] = None,
        config: Optional[AirtableImportConfig] = None,
    ) -> Database:
        """
        Downloads all the data of the provided publicly shared Airtable base, converts
        it into Baserow export format, downloads the related files and imports that
        converted base into the provided workspace.

        :param workspace: The workspace where the copy of the Airtable must be added to.
        :param share_id: The shared Airtable ID that must be imported.
        :param storage: The storage where the user files must be saved to.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :param download_files_buffer: Optionally a file buffer can be provided to store
            the downloaded files in. They will be stored in memory if not provided.
        :param config: Additional configuration related to the import.
        :return: The imported database application representing the Airtable base.
        """

        if config is None:
            config = AirtableImportConfig()

        progress = ChildProgressBuilder.build(progress_builder, child_total=1000)

        (
            init_data,
            request_id,
            cookies,
            schema,
            tables,
        ) = AirtableHandler.fetch_and_combine_airtable_data(
            share_id,
            config,
            progress.create_child_builder(represents_progress=100),
        )

        # Convert the raw Airtable data to Baserow export format so we can import that
        # later.
        baserow_database_export, files_buffer = cls.to_baserow_database_export(
            init_data,
            request_id,
            cookies,
            schema,
            tables,
            config,
            progress.create_child_builder(represents_progress=300),
            download_files_buffer,
        )

        import_export_config = ImportExportConfig(
            # We are not yet downloading any role/permission data from airtable so
            # nothing to import
            include_permission_data=False,
            reduce_disk_space_usage=False,
        )
        # Import the converted data using the existing method to avoid duplicate code.
        databases, _ = CoreHandler().import_applications_to_workspace(
            workspace,
            [baserow_database_export],
            files_buffer,
            import_export_config,
            storage=storage,
            progress_builder=progress.create_child_builder(represents_progress=600),
        )

        return databases[0].specific
