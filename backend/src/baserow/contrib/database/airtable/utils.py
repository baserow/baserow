import json
import re
from typing import Any, Optional, Union

from requests import Response

from baserow.contrib.database.airtable.constants import (
    AIRTABLE_DATE_FILTER_VALUE_MAP,
    AIRTABLE_MAX_DURATION_VALUE,
)
from baserow.contrib.database.airtable.exceptions import AirtableSkipFilter
from baserow.core.utils import get_value_at_path, remove_invalid_surrogate_characters


def extract_share_id_from_url(public_base_url: str) -> str:
    """
    Extracts the Airtable share id from the provided URL.

    :param public_base_url: The URL where the share id must be extracted from.
    :raises ValueError: If the provided URL doesn't match the publicly shared
        Airtable URL.
    :return: The extracted share id.
    """

    result = re.search(r"https:\/\/airtable.com\/(shr|app)(.*)$", public_base_url)

    if not result:
        raise ValueError(
            f"Please provide a valid shared Airtable URL (e.g. "
            f"https://airtable.com/shrxxxxxxxxxxxxxx)"
        )

    return f"{result.group(1)}{result.group(2)}"


def get_airtable_row_primary_value(table, row):
    """
    Tries to extract the name of a row using the primary value. If empty or not
    available, then it falls back on the row ID>

    :param table: The table where to extract primary column ID from.
    :param row: The row to get the value name for.
    :return: The primary value or ID of the row.
    """

    primary_column_id = table.get("primaryColumnId", "")
    primary_value = row.get("cellValuesByColumnId", {}).get(primary_column_id, None)

    if not primary_value or not isinstance(primary_value, str):
        primary_value = row["id"]

    return primary_value


def get_airtable_column_name(raw_airtable_table, column_id) -> str:
    """
    Tries to extract the name of the column from the provided Airtable table.

    :param raw_airtable_table: The table where to get the column names from.
    :param column_id: The column ID to get the name for.
    :return: The found column name or column_id if not found.
    """

    for column in raw_airtable_table["columns"]:
        if column["id"] == column_id:
            return column["name"]

    return column_id


def unknown_value_to_human_readable(value: Any) -> str:
    """
    If a value can't be converted to human-readable value, then this function can be
    used to generate something user-friendly.

    :param value: The value that must be converted.
    :return: The human-readable string value.
    """

    if value is None:
        return ""
    if isinstance(value, list):
        value_len = len(value)
        return "1 item" if value_len == 1 else f"{value_len} items"
    if isinstance(value, str) and value.startswith("usr"):
        return "1 item"
    return str(value)


def parse_json_and_remove_invalid_surrogate_characters(response: Response) -> dict:
    """
    The response from Airtable can sometimes contain invalid surrogate characters. This
    helper method removed them, and parses it to JSON.

    :param response: The response from the request to Airtable.
    :return: Parsed JSON from the response.
    """

    try:
        decoded_content = remove_invalid_surrogate_characters(
            response.content, response.encoding
        )
        json_decoded_content = json.loads(decoded_content)
    except json.decoder.JSONDecodeError:
        # In some cases, the `remove_invalid_surrogate_characters` results in
        # invalid JSON. It's not completely clear why that is, but this
        # fallback can still produce valid JSON to import in most cases if
        # the original json didn't contain invalid surrogate characters.
        json_decoded_content = response.json()

    return json_decoded_content


def quill_parse_inline(insert, attributes):
    if "bold" in attributes:
        insert = f"**{insert}**"
    if "italic" in attributes:
        insert = f"_{insert}_"
    if "strike" in attributes:
        insert = f"~~{insert}~~"
    if "code" in attributes:
        insert = f"`{insert}`"
    if "link" in attributes:
        insert = f"[{insert}]({attributes['link']})"
    if isinstance(insert, dict) and "mention" in insert:
        insert = f"@{insert['mention'].get('userId', '')}"

    return insert


def quill_wrap_block(attributes):
    prepend = ""
    append = ""
    multi_line = False
    if "header" in attributes:
        prepend = "#" * attributes["header"] + " "
    if "list" in attributes:
        list_type = attributes["list"]
        prepend = " " * attributes.get("indent", 0) * 4
        if list_type == "ordered":
            prepend += f"1. "
        elif list_type == "bullet":
            prepend += "- "
        elif list_type == "unchecked":
            prepend += "- [ ] "
        elif list_type == "checked":
            prepend += "- [x] "
    if "blockquote" in attributes:
        prepend = "> "
    if "≈≈" in attributes:
        prepend = "> "
    if "code-block" in attributes:
        prepend = "```\n"
        append = "```\n"
        multi_line = True
    return prepend, append, multi_line


def quill_split_with_newlines(value):
    parts = re.split(r"(\n)", value)
    if parts and parts[0] == "":
        parts.pop(0)
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def quill_to_markdown(ops: list) -> str:
    """
    Airtable uses the QuillJS editor for their rich text field. There is no library
    to convert it in Baserow compatible markdown. This is a simple, custom written
    function to convert it to Baserow compatible markdown.

    The format is a bit odd because a newline entry can define how it should have been
    formatted as on block level, making it a bit tricky because it's not sequential.

    See the `test_quill_to_markdown_airtable_example` test for an example.

    :param ops: The QuillJS delta object that must be converted to markdown.
    :return: The converted markdown string.
    """

    md_output = []
    # Holds everything that must be written as a line. Each entry in the ops can add to
    # it until a "\n" character is detected.
    current_object = ""
    # Temporarily holds markdown code that has start and ending block, like with
    # code "```", for example. Need to temporarily store the prepend and append values,
    # so that we can add to it if it consists of multiple lines.
    current_multi_line = None

    def flush_line():
        nonlocal md_output
        nonlocal current_object
        if current_object != "":
            md_output.append(current_object)
            current_object = ""

    def flush_multi_line(current_prepend, current_append):
        nonlocal current_object
        nonlocal current_multi_line
        if current_multi_line is not None and current_multi_line != (
            current_prepend,
            current_append,
        ):
            current_object = (
                current_multi_line[0] + current_object + current_multi_line[1]
            )
            flush_line()
            current_multi_line = None

    for index, op in enumerate(ops):
        raw_insert = op.get("insert", "")
        attributes = op.get("attributes", {})

        if isinstance(raw_insert, str):
            insert_lines = quill_split_with_newlines(raw_insert)
        else:
            insert_lines = [raw_insert]

        # Break the insert by "\n" because the block formatting options should only
        # refer to the previous line.
        for insert_line in insert_lines:
            is_new_line = insert_line == "\n"

            if is_new_line:
                prepend, append, multi_line = quill_wrap_block(attributes)
                flush_multi_line(prepend, append)

                # Starting a new multi-line block. All the following lines will be
                # enclosed by the prepend and append.
                if multi_line and current_multi_line is None:
                    current_multi_line = (prepend, append)

            parsed_insert = quill_parse_inline(insert_line, attributes)
            current_object += parsed_insert

            if is_new_line and not multi_line:
                current_object = prepend + current_object + append
                flush_line()

    flush_multi_line(None, None)
    flush_line()

    return "".join(md_output).strip()


def airtable_date_filter_value_to_baserow(value: Optional[Union[dict, str]]) -> str:
    """
    Converts the provided Airtable filter date value to the Baserow compatible date
    value string.

    :param value: A dict containing the Airtable date value.
    :return: e.g. Europe/Amsterdam?2025-01-01?exact_date
    """

    if value is None:
        return ""

    # If the value is a string, then it contains an exact date. This is the old format
    # of Airtable. In that case, we can conert it to the correct format.
    if isinstance(value, str):
        value = {
            "mode": "exactDate",
            "exactDate": value,
            "timeZone": "",  # it's okay to leave the timezone empty in Baserow.
        }

    mode = value["mode"]
    if "exactDate" in value:
        # By default, Airtable adds the time, but that is not needed in Baserow.
        value["exactDate"] = value["exactDate"][:10]
    date_string = AIRTABLE_DATE_FILTER_VALUE_MAP[mode]
    return date_string.format(**value)


def skip_filter_if_type_duration_and_value_too_high(raw_airtable_column, value):
    """
    If the provided Airtable column is a number with duration formatting, and if the
    value exceeds the maximum we can process, then the `AirtableSkipFilter` is raised.

    :param raw_airtable_column: The related raw Airtable column.
    :param value: The value that must be checked.
    :raises: AirtableSkipFilter
    """

    is_duration = (
        get_value_at_path(raw_airtable_column, "typeOptions.format") == "duration"
    )

    if not is_duration:
        return

    try:
        value = int(value)
        if abs(value) > AIRTABLE_MAX_DURATION_VALUE:
            raise AirtableSkipFilter
    except ValueError:
        pass
