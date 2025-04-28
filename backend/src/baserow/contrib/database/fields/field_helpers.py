from typing import Any, Dict, List, Optional

from baserow.contrib.database.export_serialized import DatabaseExportSerializedStructure
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils.duration import D_H_M
from baserow.core.import_export.utils import file_chunk_generator
from baserow.core.storage import ExportZipFile, Storage
from baserow.core.user_files.handler import UserFileHandler


def construct_all_possible_field_kwargs(
    table,
    link_table,
    decimal_link_table,
    file_link_table,
    multiple_collaborator_link_table,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Some baserow field types have multiple different 'modes' which result in
    different database columns and modes of operation being
    created. This function creates a dictionary of field type to a list of
    kwarg dicts, one for each interesting possible 'subtype' of the field.
    """

    all_interesting_field_kwargs = {
        "text": [{"name": "text", "primary": True}],
        "long_text": [{"name": "long_text"}],
        "url": [{"name": "url"}],
        "email": [{"name": "email"}],
        "number": [
            {
                "name": "negative_int",
                "number_negative": True,
                "number_decimal_places": 0,
            },
            {
                "name": "positive_int",
                "number_negative": False,
                "number_decimal_places": 0,
            },
            {
                "name": "negative_decimal",
                "number_negative": "True",
                "number_decimal_places": 1,
            },
            {
                "name": "positive_decimal",
                "number_negative": False,
                "number_decimal_places": 1,
            },
            {
                "name": "decimal_with_default",
                "number_negative": False,
                "number_decimal_places": 1,
                "number_default": 1.8,
            },
        ],
        "rating": [
            {"name": "rating", "max_value": 5, "color": "blue", "style": "star"}
        ],
        "boolean": [
            {"name": "boolean"},
            {
                "name": "boolean_with_default",
                "boolean_default": True,
            },
        ],
        "date": [
            {"name": "datetime_us", "date_include_time": True, "date_format": "US"},
            {"name": "date_us", "date_include_time": False, "date_format": "US"},
            {
                "name": "datetime_eu",
                "date_include_time": True,
                "date_format": "EU",
            },
            {"name": "date_eu", "date_include_time": False, "date_format": "EU"},
            {
                "name": "datetime_eu_tzone_visible",
                "date_include_time": True,
                "date_format": "EU",
                "date_force_timezone": "Europe/Amsterdam",
                "date_show_tzinfo": True,
            },
            {
                "name": "datetime_eu_tzone_hidden",
                "date_include_time": True,
                "date_format": "EU",
                "date_force_timezone": "Europe/Amsterdam",
                "date_show_tzinfo": False,
            },
        ],
        "last_modified": [
            {
                "name": "last_modified_datetime_us",
                "date_include_time": True,
                "date_format": "US",
            },
            {
                "name": "last_modified_date_us",
                "date_include_time": False,
                "date_format": "US",
            },
            {
                "name": "last_modified_datetime_eu",
                "date_include_time": True,
                "date_format": "EU",
            },
            {
                "name": "last_modified_date_eu",
                "date_include_time": False,
                "date_format": "EU",
            },
            {
                "name": "last_modified_datetime_eu_tzone",
                "date_include_time": True,
                "date_format": "EU",
                "date_force_timezone": "Europe/Amsterdam",
                "date_show_tzinfo": True,
            },
        ],
        "created_on": [
            {
                "name": "created_on_datetime_us",
                "date_include_time": True,
                "date_format": "US",
            },
            {
                "name": "created_on_date_us",
                "date_include_time": False,
                "date_format": "US",
            },
            {
                "name": "created_on_datetime_eu",
                "date_include_time": True,
                "date_format": "EU",
            },
            {
                "name": "created_on_date_eu",
                "date_include_time": False,
                "date_format": "EU",
            },
            {
                "name": "created_on_datetime_eu_tzone",
                "date_include_time": True,
                "date_format": "EU",
                "date_force_timezone": "Europe/Amsterdam",
                "date_show_tzinfo": True,
            },
        ],
        "last_modified_by": [
            {
                "name": "last_modified_by",
            }
        ],
        "created_by": [
            {
                "name": "created_by",
            }
        ],
        "duration": [
            {"name": "duration_hm", "duration_format": "h:mm"},
            {"name": "duration_hms", "duration_format": "h:mm:ss"},
            {"name": "duration_hms_s", "duration_format": "h:mm:ss.s"},
            {"name": "duration_hms_ss", "duration_format": "h:mm:ss.ss"},
            {"name": "duration_hms_sss", "duration_format": "h:mm:ss.sss"},
            {"name": "duration_dh", "duration_format": "d h"},
            {"name": "duration_dhm", "duration_format": "d h:mm"},
            {"name": "duration_dhms", "duration_format": "d h:mm:ss"},
        ],
        "link_row": [
            {"name": "link_row", "link_row_table": link_table},
            {
                "name": "self_link_row",
                "link_row_table": table,
                "has_related_field": False,
            },
            {
                "name": "link_row_without_related",
                "link_row_table": link_table,
                "has_related_field": False,
            },
            {"name": "decimal_link_row", "link_row_table": decimal_link_table},
            {"name": "file_link_row", "link_row_table": file_link_table},
            {
                "name": "multiple_collaborators_link_row",
                "link_row_table": multiple_collaborator_link_table,
            },
        ],
        "file": [{"name": "file"}],
        "single_select": [
            {
                "name": "single_select",
                "select_options": [
                    {"id": 0, "value": "A", "color": "red"},
                    {"id": 1, "value": "B", "color": "blue"},
                ],
            },
            {
                "name": "single_select_with_default",
                "select_options": [
                    {"id": 10, "value": "AA", "color": "red"},
                    {"id": 11, "value": "BB", "color": "blue"},
                ],
                "single_select_default": 11,
            },
        ],
        "multiple_select": [
            {
                "name": "multiple_select",
                "select_options": [
                    {"id": 2, "value": "C", "color": "orange"},
                    {"id": 3, "value": "D", "color": "yellow"},
                    {"id": 4, "value": "E", "color": "green"},
                ],
            },
            {
                "name": "multiple_select_with_default",
                "select_options": [
                    {"id": 21, "value": "M-1", "color": "pink"},
                    {"id": 22, "value": "M-2", "color": "purple"},
                    {"id": 23, "value": "M-3", "color": "blue"},
                ],
                "multiple_select_default": [21, 22],
            },
        ],
        "multiple_collaborators": [
            {
                "name": "multiple_collaborators",
                "notify_user_when_added": False,
            }
        ],
        "phone_number": [{"name": "phone_number"}],
        "formula": [
            # Make one for each Baserow formula type!
            {"name": "formula_text", "formula": "CONCAT('test ', UPPER('formula'))"},
            {"name": "formula_int", "formula": "1"},
            {"name": "formula_bool", "formula": "true"},
            {"name": "formula_decimal", "formula": "100/3"},
            {
                "name": "formula_dateinterval",
                "formula": "date_interval('1 day')",
                "duration_format": D_H_M,
            },
            {"name": "formula_date", "formula": "todate('20200101', 'YYYYMMDD')"},
            {"name": "formula_singleselect", "formula": "field('single_select')"},
            {"name": "formula_email", "formula": "field('email')"},
            {
                "name": "formula_link_with_label",
                "formula": "button('https://google.com', 'label')",
            },
            {"name": "formula_link_url_only", "formula": "link('https://google.com')"},
            {"name": "formula_multipleselect", "formula": "field('multiple_select')"},
            {
                "name": "formula_multiple_collaborators",
                "formula": "field('multiple_collaborators')",
            },
        ],
        "count": [
            {
                "name": "count",
                "through_field_name": "link_row",
            }
        ],
        "rollup": [
            {
                "name": "rollup",
                "through_field_name": "decimal_link_row",
                "target_field_name": "decimal_field",
                "rollup_function": "sum",
                "number_decimal_places": 3,
            },
            {
                "name": "duration_rollup_sum",
                "through_field_name": "link_row",
                "target_field_name": "duration_field",
                "rollup_function": "sum",
                "duration_format": "h:mm",
            },
            {
                "name": "duration_rollup_avg",
                "through_field_name": "link_row",
                "target_field_name": "duration_field",
                "rollup_function": "avg",
                "duration_format": "h:mm",
            },
        ],
        "lookup": [
            {
                "name": "lookup",
                "through_field_name": "link_row",
                "target_field_name": "text_field",
            },
            {
                "name": "multiple_collaborators_lookup",
                "through_field_name": "multiple_collaborators_link_row",
                "target_field_name": "multiple_collaborators",
            },
        ],
        "uuid": [{"name": "uuid"}],
        "autonumber": [{"name": "autonumber"}],
        "password": [{"name": "password"}],
        "ai": [
            {
                "name": "ai",
                "ai_generative_ai_type": "test_generative_ai",
                "ai_generative_ai_model": "test_1",
                "ai_output_type": "text",
                "ai_prompt": "'Who are you?'",
            },
            {
                "name": "ai_choice",
                "ai_generative_ai_type": "test_generative_ai",
                "ai_generative_ai_model": "test_1",
                "ai_prompt": "'What are you?'",
                "ai_output_type": "choice",
                "select_options": [
                    {"id": 5, "value": "Object", "color": "orange"},
                    {"id": 6, "value": "Else", "color": "yellow"},
                ],
            },
        ],
    }
    # If you have added a new field please add an entry into the dict above with any
    # test worthy combinations of kwargs
    # nosec ignore as this code is test/dev cli tool only, no matter if this assert
    # does not get run in the cli tools.
    assert set(field_type_registry.get_types()) == set(  # nosec
        all_interesting_field_kwargs.keys()
    ), "Please add the new field type to the testing dictionary of interesting kwargs"
    return all_interesting_field_kwargs


def prepare_files_for_export(
    records: List[Dict[str, Any]],
    cache: Dict[str, Any],
    files_zip: Optional[ExportZipFile] = None,
    storage: Optional[Storage] = None,
    name_prefix: str = "",
) -> List[Dict[str, Any]]:
    """
    Prepares file field values for export by either adding them to a zip file or
    returning the serialized file data

    :param records: List of file records containing file metadata.
    :param cache: A dictionary used to track which files have already been processed
        to avoid duplicates.
    :param files_zip: Optional ExportZipFile to add the actual file contents to.
    :param storage: Optional storage backend to read the file contents from when adding
        to zip.
    :param name_prefix: Optional prefix to prepend to file names in the export.
    :return: List of serialized file metadata
    """

    file_names = []
    user_file_handler = UserFileHandler()

    for record in records:
        # Check if the user file object is already in the cache and if not,
        # it must be fetched and added to it.
        file_name = f"{name_prefix}{record['name']}"
        cache_entry = f"user_file_{file_name}"
        if cache_entry not in cache:
            if files_zip is not None and file_name not in [
                item["name"] for item in files_zip.info_list()
            ]:
                file_path = user_file_handler.user_file_path(record["name"])
                # Create chunk generator for the file content and add it to the zip
                # stream. That file will be read when zip stream is being
                # written to final zip file
                chunk_generator = file_chunk_generator(storage, file_path)
                files_zip.add(chunk_generator, file_name)

            # This is just used to avoid writing the same file twice.
            cache[cache_entry] = True

        if files_zip is None:
            # If the zip file is `None`, it means we're duplicating this row. To
            # avoid unnecessary queries, we jump add the complete file, and will
            # use that during import instead of fetching the user file object.
            file_names.append(record)
        else:
            file_names.append(
                DatabaseExportSerializedStructure.file_field_value(
                    name=file_name,
                    visible_name=record["visible_name"],
                    original_name=record["name"],
                    size=record["size"],
                )
            )

    return file_names
