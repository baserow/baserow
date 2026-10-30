from .exceptions import InvalidDashboardFilterValues

MAX_SELECTION_VALUES = 1_000
MAX_SELECTION_BYTES = 64 * 1024


def validate_selection_budget(selections):
    """Bound stored selections and option lookups without changing their indexes."""

    count = 0
    size = 0
    for values in selections:
        if not isinstance(values, list):
            raise InvalidDashboardFilterValues("Selected values must be a list.")
        count += len(values)
        if count > MAX_SELECTION_VALUES:
            raise InvalidDashboardFilterValues(
                f"Select at most {MAX_SELECTION_VALUES} values in total.",
                code="max_selection_values",
            )
        for value in values:
            if not isinstance(value, str):
                raise InvalidDashboardFilterValues("Selected values must be text.")
            if "\x00" in value:
                raise InvalidDashboardFilterValues(
                    "Selected values cannot contain null characters.",
                    code="null_characters_not_allowed",
                )
            remaining = MAX_SELECTION_BYTES - size
            if len(value) > remaining:
                size = MAX_SELECTION_BYTES + 1
            else:
                try:
                    size += len(value.encode("utf-8"))
                except UnicodeEncodeError as exc:
                    raise InvalidDashboardFilterValues(
                        "Selected values must contain valid Unicode.",
                        code="surrogate_characters_not_allowed",
                    ) from exc
            if size > MAX_SELECTION_BYTES:
                raise InvalidDashboardFilterValues(
                    f"Selected values must use at most {MAX_SELECTION_BYTES} "
                    "UTF-8 bytes in total.",
                    code="max_selection_bytes",
                )


def selection_format(filter_type, mode, multiple, operator):
    """Identify edits that invalidate a control's currently selected values."""

    has_value = operator not in {"empty", "not_empty", "is_even_and_whole"}
    if filter_type == "date" and operator.startswith("date_is"):
        value_format = "date"
    elif operator == "date_equals_day_of_month":
        value_format = "day_of_month"
    else:
        value_format = "plain"
    return (
        filter_type,
        mode,
        multiple if mode == "dropdown" else False,
        has_value,
        value_format,
        operator == "date_is_within",
    )
