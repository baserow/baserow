import re


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
    primary_column_id = table.get("primaryColumnId", "")
    primary_value = row.get("cellValuesByColumnId", {}).get(primary_column_id, None)

    if not primary_value or not isinstance(primary_value, str):
        primary_value = row["id"]

    return primary_value
