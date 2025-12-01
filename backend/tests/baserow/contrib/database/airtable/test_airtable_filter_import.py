import json
from copy import deepcopy

import pytest

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.exceptions import AirtableSkipFilter
from baserow.contrib.database.airtable.import_report import AirtableImportReport
from baserow.contrib.database.airtable.registry import (
    airtable_column_type_registry,
    airtable_filter_operator_registry,
)

AIRTABLE_TABLE = {
    "id": "tbl7glLIGtH8C8zGCzb",
    "name": "Data",
    "primaryColumnId": "",
    "columns": [],
    "meaningfulColumnOrder": [],
    "views": [],
    "viewOrder": [],
    "viewsById": {},
    "viewSectionsById": {},
    "schemaChecksum": "46f523a43433afe37d63e00d1a0f36c64310f06e4e0af2c32b6e99f26ab0e51a",
}
AIRTABLE_COLUMN_PER_TYPE = {
    "text": {"id": "fld2K7nZbMvWBYE6g", "name": "Single line text", "type": "text"},
    "multilineText": {
        "id": "fld8arQx6h2H91ONW",
        "name": "Long text",
        "type": "multilineText",
    },
    "multipleAttachment": {
        "id": "fldRhiYOuJrWF5DUR",
        "name": "Attachment",
        "type": "multipleAttachment",
        "typeOptions": {"unreversed": True},
    },
    "checkbox": {
        "id": "fldrWHvavdw0eAV1h",
        "name": "Checkbox",
        "type": "checkbox",
        "typeOptions": {"color": "green", "icon": "check"},
    },
    "multiSelect": {
        "id": "fldE3rb2UYv3a605v",
        "name": "Multiple select",
        "type": "multiSelect",
        "typeOptions": {
            "choiceOrder": [
                "selNkxVarxxS8tRkS",
                "selFSuP84urXClrlS",
                "selvostaiXnRkaHXI",
            ],
            "choices": {
                "selNkxVarxxS8tRkS": {
                    "id": "selNkxVarxxS8tRkS",
                    "color": "blue",
                    "name": "Option 1",
                },
                "selFSuP84urXClrlS": {
                    "id": "selFSuP84urXClrlS",
                    "color": "cyan",
                    "name": "Option 2",
                },
                "selvostaiXnRkaHXI": {
                    "id": "selvostaiXnRkaHXI",
                    "color": "teal",
                    "name": "Option 3",
                },
            },
            "disableColors": False,
        },
    },
    "select": {
        "id": "fldWmh0gNFmvYHLwy",
        "name": "Single select",
        "type": "select",
        "typeOptions": {
            "choiceOrder": [
                "sela2TITKl8Ng946B",
                "selTvmx6xRumPDwa7",
                "selRvipUxtrC2Wc6g",
            ],
            "choices": {
                "sela2TITKl8Ng946B": {
                    "id": "sela2TITKl8Ng946B",
                    "color": "blue",
                    "name": "Option A",
                },
                "selTvmx6xRumPDwa7": {
                    "id": "selTvmx6xRumPDwa7",
                    "color": "cyan",
                    "name": "Option B",
                },
                "selRvipUxtrC2Wc6g": {
                    "id": "selRvipUxtrC2Wc6g",
                    "color": "teal",
                    "name": "Option C",
                },
            },
            "disableColors": False,
        },
    },
    "collaborator": {
        "id": "fldLobeVXHF0LkGUd",
        "name": "Collaborator",
        "type": "collaborator",
        "typeOptions": {
            "shouldNotify": False,
            "canAddNonBaseCollaborators": False,
            "createdAsPrimaryKeyForPeopleTable": False,
        },
    },
    "date": {
        "id": "fldVzq9v4wQr4vbFv",
        "name": "Date",
        "type": "date",
        "typeOptions": {"isDateTime": False, "dateFormat": "Local"},
    },
    "phone": {"id": "fldfANyudw6u1hWaE", "name": "Phone", "type": "phone"},
    "number": {
        "id": "fld94jstPyHsXcXmE",
        "name": "Number",
        "type": "number",
        "typeOptions": {
            "format": "decimal",
            "precision": 1,
            "negative": False,
            "validatorName": "positive",
            "separatorFormat": "local",
            "shouldShowThousandsSeparator": True,
        },
    },
    "duration": {
        "id": "fld94jstPyHsXcXmE",
        "name": "Number",
        "type": "number",
        "typeOptions": {"format": "duration", "durationFormat": "h:mm"},
    },
    "rating": {
        "id": "fldB84fL8kshHAOLm",
        "name": "Rating",
        "type": "rating",
        "typeOptions": {"color": "yellow", "icon": "star", "max": 5},
    },
    "autoNumber": {
        "id": "fldU0DnfRMRewuH71",
        "name": "ID",
        "type": "autoNumber",
        "typeOptions": {"maxUsedAutoNumber": 3},
    },
    "foreignKey": {
        "id": "fldX30z0jmPZFKGPl",
        "name": "Table 2",
        "type": "foreignKey",
        "typeOptions": {
            "foreignTableId": "tbllhx9chTN5MFEwH",
            "relationship": "many",
            "unreversed": True,
            "symmetricColumnId": "fldDERrIKuv3ACdr6",
        },
    },
}

ROW_ID_MAPPING = {
    "tbllhx9chTN5MFEwH": {
        "rect9vRzdJvCLrRg8": 1,
        "rect9vRzdJvCLrRg9": 2,
    }
}

ALL_AIRTABLE_FILTERS_PER_TYPE = {
    "text": [
        {
            "operator": "contains",
            "value": "1",
            "baserow_filter_type": "contains",
            "baserow_value": "1",
        },
        {
            "operator": "doesNotContain",
            "value": "1",
            "baserow_filter_type": "contains_not",
            "baserow_value": "1",
        },
        {
            "operator": "=",
            "value": "1",
            "baserow_filter_type": "equal",
            "baserow_value": "1",
        },
        {
            "operator": "!=",
            "value": "1",
            "baserow_filter_type": "not_equal",
            "baserow_value": "1",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "multilineText": [
        {
            "operator": "contains",
            "value": "1",
            "baserow_filter_type": "contains",
            "baserow_value": "1",
        },
        {
            "operator": "doesNotContain",
            "value": "1",
            "baserow_filter_type": "contains_not",
            "baserow_value": "1",
        },
        {
            "operator": "=",
            "value": "1",
            "baserow_filter_type": "equal",
            "baserow_value": "1",
        },
        {
            "operator": "!=",
            "value": "1",
            "baserow_filter_type": "not_equal",
            "baserow_value": "1",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "multipleAttachment": [
        {
            "operator": "filename",
            "value": "test",
            "baserow_filter_type": "filename_contains",
            "baserow_value": "test",
        },
        {
            "operator": "filetype",
            "value": "image",
            "baserow_filter_type": "has_file_type",
            "baserow_value": "image",
        },
        {
            "operator": "filetype",
            "value": "text",
            "baserow_filter_type": "has_file_type",
            "baserow_value": "document",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "checkbox": [
        {
            "operator": "=",
            "value": True,
            "baserow_filter_type": "boolean",
            "baserow_value": "true",
        },
        {
            "operator": "=",
            "value": False,
            "baserow_filter_type": "boolean",
            "baserow_value": "false",
        },
    ],
    "multiSelect": [
        {
            "operator": "|",
            "value": ["selNkxVarxxS8tRkS"],
            "baserow_skip": True,
        },
        {
            "operator": "&",
            "value": ["selFSuP84urXClrlS"],
            "baserow_skip": True,
        },
        {
            "operator": "=",
            "value": ["selvostaiXnRkaHXI"],
            "baserow_filter_type": "multiple_select_has",
            "baserow_value": "fldE3rb2UYv3a605v_selvostaiXnRkaHXI",
        },
        {
            "operator": "=",
            "value": None,
            "baserow_filter_type": "multiple_select_has",
            "baserow_value": "",
        },
        {
            "operator": "doesNotContain",
            "value": ["selvostaiXnRkaHXI"],
            "baserow_filter_type": "multiple_select_has_not",
            "baserow_value": "fldE3rb2UYv3a605v_selvostaiXnRkaHXI",
        },
        {
            "operator": "doesNotContain",
            "value": None,
            "baserow_filter_type": "multiple_select_has_not",
            "baserow_value": "",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "select": [
        {
            "operator": "=",
            "value": "sela2TITKl8Ng946B",
            "baserow_filter_type": "single_select_equal",
            "baserow_value": "fldWmh0gNFmvYHLwy_sela2TITKl8Ng946B",
        },
        {
            "operator": "!=",
            "value": "selRvipUxtrC2Wc6g",
            "baserow_filter_type": "single_select_not_equal",
            "baserow_value": "fldWmh0gNFmvYHLwy_selRvipUxtrC2Wc6g",
        },
        {
            "operator": "isAnyOf",
            "value": ["selTvmx6xRumPDwa7", "selTvmx6xRumPDwa8"],
            "baserow_filter_type": "single_select_is_any_of",
            "baserow_value": "fldWmh0gNFmvYHLwy_selTvmx6xRumPDwa7,fldWmh0gNFmvYHLwy_selTvmx6xRumPDwa8",
        },
        {
            "operator": "isAnyOf",
            "value": None,
            "baserow_filter_type": "single_select_is_any_of",
            "baserow_value": "",
        },
        {
            "operator": "isNoneOf",
            "value": ["selTvmx6xRumPDwa7", "selTvmx6xRumPDwa8"],
            "baserow_filter_type": "single_select_is_none_of",
            "baserow_value": "fldWmh0gNFmvYHLwy_selTvmx6xRumPDwa7,fldWmh0gNFmvYHLwy_selTvmx6xRumPDwa8",
        },
        {
            "operator": "isNoneOf",
            "value": None,
            "baserow_filter_type": "single_select_is_none_of",
            "baserow_value": "",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "collaborator": [
        {
            "operator": "=",
            "value": "usrGIN77VWdhm7LKk",
            "baserow_filter_type": "multiple_collaborators_has",
            "baserow_value": "usrGIN77VWdhm7LKk",
        },
        {
            "operator": "!=",
            "value": "usrGIN77VWdhm7LKk",
            "baserow_filter_type": "multiple_collaborators_has_not",
            "baserow_value": "usrGIN77VWdhm7LKk",
        },
        {
            "operator": "isAnyOf",
            "value": ["usrGIN77VWdhm7LKk"],
            "baserow_skip": True,
        },
        {
            "operator": "isNoneOf",
            "value": ["usrGIN77VWdhm7LKk"],
            "baserow_skip": True,
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "date": [
        {
            "operator": "=",
            "value": {
                "mode": "exactDate",
                "exactDate": "2025-02-05T00:00:00.000Z",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam?2025-02-05?exact_date",
        },
        {
            "operator": "=",
            "value": {
                "mode": "tomorrow",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam??tomorrow",
        },
        {
            "operator": "=",
            "value": {
                "mode": "today",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam??today",
        },
        {
            "operator": "=",
            "value": {
                "mode": "yesterday",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam??yesterday",
        },
        {
            "operator": "=",
            "value": {
                "mode": "oneWeekAgo",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam?1?nr_weeks_ago",
        },
        {
            "operator": "=",
            "value": {
                "mode": "oneWeekFromNow",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam?1?nr_weeks_from_now",
        },
        {
            "operator": "=",
            "value": {
                "mode": "oneMonthAgo",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam??one_month_ago",
        },
        {
            "operator": "=",
            "value": {
                "mode": "oneMonthFromNow",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam?1?nr_months_from_now",
        },
        {
            "operator": "=",
            "value": {
                "mode": "daysAgo",
                "numberOfDays": 1,
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam?1?nr_days_ago",
        },
        {
            "operator": "=",
            "value": {
                "mode": "daysFromNow",
                "numberOfDays": 1,
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is",
            "baserow_value": "Europe/Amsterdam?1?nr_days_from_now",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "pastWeek",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam?1?nr_weeks_ago",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "pastMonth",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam?1?nr_months_ago",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "pastYear",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam?1?nr_years_ago",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "nextWeek",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam??next_week",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "nextYear",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam??next_year",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "nextMonth",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam??next_month",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "thisCalendarYear",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam??this_year",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "thisCalendarMonth",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam??this_month",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "thisCalendarWeek",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam??this_week",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "nextNumberOfDays",
                "numberOfDays": 1,
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam?1?nr_days_from_now",
        },
        {
            "operator": "isWithin",
            "value": {
                "mode": "pastNumberOfDays",
                "numberOfDays": 1,
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_within",
            "baserow_value": "Europe/Amsterdam?1?nr_days_ago",
        },
        {
            "operator": "<",
            "value": {
                "mode": "exactDate",
                "exactDate": "2025-02-04T00:00:00.000Z",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_before",
            "baserow_value": "Europe/Amsterdam?2025-02-04?exact_date",
        },
        {
            "operator": ">",
            "value": {
                "mode": "exactDate",
                "exactDate": "2025-02-13T00:00:00.000Z",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_after",
            "baserow_value": "Europe/Amsterdam?2025-02-13?exact_date",
        },
        {
            "operator": "<=",
            "value": {
                "mode": "exactDate",
                "exactDate": "2025-02-02T00:00:00.000Z",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_on_or_before",
            "baserow_value": "Europe/Amsterdam?2025-02-02?exact_date",
        },
        {
            "operator": ">=",
            "value": {
                "mode": "exactDate",
                "exactDate": "2025-02-05T00:00:00.000Z",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_on_or_after",
            "baserow_value": "Europe/Amsterdam?2025-02-05?exact_date",
        },
        {
            "operator": "!=",
            "value": {
                "mode": "exactDate",
                "exactDate": "2025-02-05T00:00:00.000Z",
                "timeZone": "Europe/Amsterdam",
                "shouldUseCorrectTimeZoneForFormulaicColumn": True,
            },
            "baserow_filter_type": "date_is_not",
            "baserow_value": "Europe/Amsterdam?2025-02-05?exact_date",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "id": "fltzpQ8PlY7w2DKb4",
            "columnId": "fldVzq9v4wQr4vbFv",
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "phone": [
        {
            "operator": "contains",
            "value": "1",
            "baserow_filter_type": "contains",
            "baserow_value": "1",
        },
        {
            "operator": "doesNotContain",
            "value": "1",
            "baserow_filter_type": "contains_not",
            "baserow_value": "1",
        },
        {
            "operator": "=",
            "value": "1",
            "baserow_filter_type": "equal",
            "baserow_value": "1",
        },
        {
            "operator": "!=",
            "value": "1",
            "baserow_filter_type": "not_equal",
            "baserow_value": "1",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "number": [
        {
            "operator": "=",
            "value": 1,
            "baserow_filter_type": "equal",
            "baserow_value": "1",
        },
        {
            "operator": "!=",
            "value": 1,
            "baserow_filter_type": "not_equal",
            "baserow_value": "1",
        },
        {
            "operator": "<",
            "value": 1,
            "baserow_filter_type": "lower_than",
            "baserow_value": "1",
        },
        {
            "operator": ">",
            "value": 1,
            "baserow_filter_type": "higher_than",
            "baserow_value": "1",
        },
        {
            "operator": "<=",
            "value": 1,
            "baserow_filter_type": "lower_than_or_equal",
            "baserow_value": "1",
        },
        {
            "operator": ">=",
            "value": 1,
            "baserow_filter_type": "higher_than_or_equal",
            "baserow_value": "1",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "duration": [
        {
            "operator": "=",
            "value": 86399999913600,
            "baserow_filter_type": "equal",
            "baserow_value": "86399999913600",
        },
        {
            "operator": "=",
            "value": 86399999913601,
            "baserow_filter_type": "equal",
            "baserow_skip": True,
        },
        {
            "operator": "!=",
            "value": 86399999913601,
            "baserow_filter_type": "not_equal",
            "baserow_skip": True,
        },
        {
            "operator": "<",
            "value": 86399999913601,
            "baserow_filter_type": "lower_than",
            "baserow_skip": True,
        },
        {
            "operator": ">",
            "value": 86399999913601,
            "baserow_filter_type": "higher_than",
            "baserow_skip": True,
        },
        {
            "operator": "<=",
            "value": 86399999913601,
            "baserow_filter_type": "lower_than_or_equal",
            "baserow_skip": True,
        },
        {
            "operator": ">=",
            "value": 86399999913601,
            "baserow_filter_type": "higher_than_or_equal",
            "baserow_skip": True,
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "rating": [
        {
            "operator": "=",
            "value": 1,
            "baserow_filter_type": "equal",
            "baserow_value": "1",
        },
        {
            "operator": "!=",
            "value": 1,
            "baserow_filter_type": "not_equal",
            "baserow_value": "1",
        },
        {
            "operator": "<",
            "value": 1,
            "baserow_filter_type": "lower_than",
            "baserow_value": "1",
        },
        {
            "operator": ">",
            "value": 1,
            "baserow_filter_type": "higher_than",
            "baserow_value": "1",
        },
        {
            "operator": "<=",
            "value": 1,
            "baserow_filter_type": "lower_than_or_equal",
            "baserow_value": "1",
        },
        {
            "operator": ">=",
            "value": 1,
            "baserow_filter_type": "higher_than_or_equal",
            "baserow_value": "1",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "autoNumber": [
        {
            "operator": "=",
            "value": 1,
            "baserow_filter_type": "equal",
            "baserow_value": "1",
        },
        {
            "operator": "!=",
            "value": 1,
            "baserow_filter_type": "not_equal",
            "baserow_value": "1",
        },
        {
            "operator": "<",
            "value": 1,
            "baserow_filter_type": "lower_than",
            "baserow_value": "1",
        },
        {
            "operator": ">",
            "value": 1,
            "baserow_filter_type": "higher_than",
            "baserow_value": "1",
        },
        {
            "operator": "<=",
            "value": 1,
            "baserow_filter_type": "lower_than_or_equal",
            "baserow_value": "1",
        },
        {
            "operator": ">=",
            "value": 1,
            "baserow_filter_type": "higher_than_or_equal",
            "baserow_value": "1",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
    "foreignKey": [
        {
            "operator": "|",
            "value": ["rect9vRzdJvCLrRg9"],
            "baserow_skip": True,
        },
        {
            "operator": "&",
            "value": ["rect9vRzdJvCLrRg9"],
            "baserow_skip": True,
        },
        {
            "operator": "=",
            "value": ["rect9vRzdJvCLrRg9"],
            "baserow_filter_type": "link_row_has",
            "baserow_value": "2",
        },
        {
            "operator": "=",
            "value": ["not_existing_id"],
            "baserow_filter_type": "link_row_has",
            "baserow_value": "",
        },
        {
            "operator": "=",
            "value": ["rect9vRzdJvCLrRg9", "rect9vRzdJvCLrRg8"],
            "baserow_skip": True,
        },
        {
            "operator": "isNoneOf",
            "value": ["rect9vRzdJvCLrRg9"],
            "baserow_skip": True,
        },
        {
            "operator": "contains",
            "value": "1",
            "baserow_filter_type": "link_row_contains",
            "baserow_value": "1",
        },
        {
            "operator": "doesNotContain",
            "value": "1",
            "baserow_filter_type": "link_row_not_contains",
            "baserow_value": "1",
        },
        {
            "operator": "isEmpty",
            "value": None,
            "baserow_filter_type": "empty",
            "baserow_value": "",
        },
        {
            "operator": "isNotEmpty",
            "value": None,
            "baserow_filter_type": "not_empty",
            "baserow_value": "",
        },
    ],
}


def test_if_all_airtable_filter_operators_are_in_tests():
    all_filter_operators_in_tests = {
        airtable_filter["operator"]
        for airtable_column_type, airtable_filters in ALL_AIRTABLE_FILTERS_PER_TYPE.items()
        for airtable_filter in airtable_filters
    }

    for filter_operator in airtable_filter_operator_registry.get_all():
        assert filter_operator.type in all_filter_operators_in_tests, (
            f"{filter_operator.type} must be included in the "
            f"`test_if_all_airtable_filter_operators_are_in_tests` test"
        )


def test_all_airtable_filters():
    for airtable_column_type, airtable_filters in ALL_AIRTABLE_FILTERS_PER_TYPE.items():
        airtable_column = AIRTABLE_COLUMN_PER_TYPE[airtable_column_type]
        for airtable_filter in airtable_filters:
            has_baserow_skip = "baserow_skip" in airtable_filter
            has_baserow_filter = (
                "baserow_filter_type" in airtable_filter
                and "baserow_value" in airtable_filter
            )

            if not has_baserow_skip and not has_baserow_filter:
                assert False, f"No baserow_ property in {airtable_filter}"

            import_report = AirtableImportReport()
            airtable_table = deepcopy(AIRTABLE_TABLE)
            airtable_table["primaryColumnId"] = airtable_column["id"]
            airtable_table["columns"].append(airtable_column)
            airtable_filter = deepcopy(airtable_filter)
            airtable_filter["id"] = "flt1234"
            airtable_filter["columnId"] = airtable_column["id"]

            (
                baserow_field,
                airtable_column_type,
            ) = airtable_column_type_registry.from_airtable_column_to_serialized(
                {},
                airtable_column,
                AirtableImportConfig(),
                AirtableImportReport(),
            )

            filter_operator = airtable_filter_operator_registry.get(
                airtable_filter["operator"]
            )
            args = (
                ROW_ID_MAPPING,
                airtable_table,
                airtable_column,
                baserow_field,
                import_report,
                airtable_filter["value"],
            )

            if has_baserow_skip:
                with pytest.raises(AirtableSkipFilter):
                    try:
                        filter_operator.to_baserow_filter_and_value(*args)
                    except NotImplementedError:
                        assert False, (
                            f"not implemented {json.dumps(airtable_filter, indent=4)}"
                            f"{json.dumps(airtable_column, indent=4)}"
                        )

            if has_baserow_filter:
                try:
                    filter_type, value = filter_operator.to_baserow_filter_and_value(
                        *args
                    )
                except NotImplementedError:
                    assert False, (
                        f"not implemented {json.dumps(airtable_filter, indent=4)}"
                        f"{json.dumps(airtable_column, indent=4)}"
                    )

                except AirtableSkipFilter:
                    assert False, (
                        f"unexpected skip filter"
                        f" {json.dumps(airtable_filter, indent=4)}"
                        f"{json.dumps(airtable_column, indent=4)}"
                    )
                assert filter_type.type == airtable_filter["baserow_filter_type"], (
                    f"filter type mismatch {json.dumps(airtable_filter, indent=4)}"
                    f"{json.dumps(airtable_column, indent=4)}"
                )
                assert value == airtable_filter["baserow_value"], (
                    f"value mismatch {json.dumps(airtable_filter, indent=4)}"
                    f"{json.dumps(airtable_column, indent=4)}"
                )
