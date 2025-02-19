from copy import deepcopy

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.import_report import AirtableImportReport
from baserow.contrib.database.airtable.registry import airtable_view_type_registry

RAW_AIRTABLE_VIEW = {
    "id": "viwcpYeEpAs6kZspktV",
    "name": "Grid view",
    "type": "grid",
    "personalForUserId": None,
    "description": None,
    "createdByUserId": "usrdGm7k7NIVWhK7W7L",
}
RAW_AIRTABLE_TABLE = raw_airtable_table = {
    "id": "tbl7glLIGtH8C8zGCzb",
    "name": "Data",
    "primaryColumnId": "fldwSc9PqedIhTSqhi1",
    "columns": [
        {"id": "fldwSc9PqedIhTSqhi1", "name": "Single line text", "type": "text"},
        {"id": "fldwSc9PqedIhTSqhi2", "name": "Single line text", "type": "text"},
    ],
    "meaningfulColumnOrder": [
        {"columnId": "fldwSc9PqedIhTSqhi1", "visibility": True},
        {"columnId": "fldwSc9PqedIhTSqhi2", "visibility": True},
    ],
    "views": [RAW_AIRTABLE_VIEW],
    "viewOrder": [RAW_AIRTABLE_VIEW["id"]],
    "viewsById": {
        RAW_AIRTABLE_VIEW["id"]: RAW_AIRTABLE_VIEW,
    },
    "viewSectionsById": {},
    "schemaChecksum": "46f523a43433afe37d63e00d1a0f36c64310f06e4e0af2c32b6e99f26ab0e51a",
}
RAW_AIRTABLE_VIEW_DATA = {
    "id": "viwcpYeEpAs6kZspktV",
    "frozenColumnCount": 1,
    "columnOrder": [
        {"columnId": "fldwSc9PqedIhTSqhi1", "visibility": True, "width": 172},
        {"columnId": "fldwSc9PqedIhTSqhi2", "visibility": True},
    ],
    "filters": None,
    "lastSortsApplied": None,
    "groupLevels": None,
    "colorConfig": None,
    "sharesById": {},
    "metadata": {"grid": {"rowHeight": "medium"}},
    "description": None,
    "createdByUserId": "usrdGm7k7NIVWhK7W7L",
    "applicationTransactionNumber": 284,
    "rowOrder": [
        {"rowId": "recAAA5JwFXBk4swkfB", "visibility": True},
        {"rowId": "rec9Imz1INvNXgRIXn1", "visibility": True},
        {"rowId": "recyANUudYjDqIXdq9Z", "visibility": True},
        {"rowId": "rec2O9BdjKJO6dgj6QF", "visibility": True},
    ],
}
RAW_VIEW_DATA_FILTERS = {
    "filterSet": [
        {
            "id": "fltp2gabc8P91234f",
            "columnId": "fldwSc9PqedIhTSqhi1",
            "operator": "isNotEmpty",
            "value": None,
        },
        {
            "id": "flthuYL0uubbDF2Xy",
            "type": "nested",
            "conjunction": "or",
            "filterSet": [
                {
                    "id": "flt70g1l245672xRi",
                    "columnId": "fldwSc9PqedIhTSqhi1",
                    "operator": "!=",
                    "value": "test",
                },
                {
                    "id": "fltVg238719fbIKqC",
                    "columnId": "fldwSc9PqedIhTSqhi2",
                    "operator": "!=",
                    "value": "test2",
                },
            ],
        },
    ],
    "conjunction": "and",
}
RAW_VIEW_DATA_SORTS = {
    "sortSet": [
        {
            "id": "srtglUy98ghs5ou8D",
            "columnId": "fldwSc9PqedIhTSqhi1",
            "ascending": True,
        }
    ],
    "shouldAutoSort": True,
    "appliedTime": "2025-02-18T19:16:10.999Z",
}
RAW_VIEW_DATA_GROUPS = [
    {
        "id": "glvvqP2okySUA2345",
        "columnId": "fldwSc9PqedIhTSqhi1",
        "order": "ascending",
        "emptyGroupState": "hidden",
    }
]


def test_import_grid_view():
    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        RAW_AIRTABLE_VIEW_DATA,
        AirtableImportConfig(),
        AirtableImportReport(),
    )

    assert serialized_view == {
        "decorations": [],
        "field_options": [],
        "filter_groups": [],
        "filter_type": "AND",
        "filters": [],
        "filters_disabled": False,
        "group_bys": [],
        "id": "viwcpYeEpAs6kZspktV",
        "name": "Grid view",
        "order": 1,
        "owned_by": None,
        "ownership_type": "collaborative",
        "public": False,
        "row_height_size": "medium",
        "row_identifier_type": "count",
        "sortings": [],
        "type": "grid",
    }


def test_import_grid_view_xlarge_row_height():
    view_data = deepcopy(RAW_AIRTABLE_VIEW_DATA)
    view_data["metadata"]["grid"]["rowHeight"] = "xlarge"

    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )

    assert serialized_view["row_height_size"] == "large"


def test_import_grid_view_unknown_row_height():
    view_data = deepcopy(RAW_AIRTABLE_VIEW_DATA)
    view_data["metadata"]["grid"]["rowHeight"] = "unknown"

    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )

    assert serialized_view["row_height_size"] == "small"


# def test_import_grid_view_filters_and_filter_groups():
#     view_data = deepcopy(RAW_AIRTABLE_VIEW_DATA)
#     view_data["filters"] = RAW_VIEW_DATA_FILTERS
#
#     airtable_view_type = airtable_view_type_registry.get("grid")
#     serialized_view = airtable_view_type.to_serialized_baserow_view(
#         RAW_AIRTABLE_TABLE,
#         RAW_AIRTABLE_VIEW,
#         view_data,
#         AirtableImportConfig(),
#         AirtableImportReport(),
#     )
#
#     import json
#     print(json.dumps(serialized_view, indent=4))
#
#     assert False


def test_import_grid_view_sorts():
    view_data = deepcopy(RAW_AIRTABLE_VIEW_DATA)
    view_data["lastSortsApplied"] = RAW_VIEW_DATA_SORTS
    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert serialized_view["sortings"] == [
        {"id": "srtglUy98ghs5ou8D", "field_id": "fldwSc9PqedIhTSqhi1", "order": "ASC"}
    ]

    view_data["lastSortsApplied"]["sortSet"][0]["ascending"] = False
    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert serialized_view["sortings"] == [
        {"id": "srtglUy98ghs5ou8D", "field_id": "fldwSc9PqedIhTSqhi1", "order": "DESC"}
    ]


def test_import_grid_view_group_bys():
    assert False


def test_import_grid_view_decorations():
    assert False
