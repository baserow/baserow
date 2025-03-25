from copy import deepcopy

from django.contrib.contenttypes.models import ContentType

import pytest

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.import_report import (
    SCOPE_VIEW,
    SCOPE_VIEW_COLOR,
    SCOPE_VIEW_GROUP_BY,
    SCOPE_VIEW_SORT,
    AirtableImportReport,
)
from baserow.contrib.database.airtable.registry import airtable_view_type_registry
from baserow.contrib.database.fields.field_types import FileFieldType, TextFieldType
from baserow.contrib.database.fields.models import FileField, TextField

RAW_AIRTABLE_VIEW = {
    "id": "viwcpYeEpAs6kZspktV",
    "name": "Grid view",
    "type": "grid",
    "personalForUserId": None,
    "description": None,
    "createdByUserId": "usrdGm7k7NIVWhK7W7L",
}
RAW_AIRTABLE_TABLE = {
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
ROW_ID_MAPPING = {}
FIELD_MAPPING = {
    "fldwSc9PqedIhTSqhi1": {
        "baserow_field": TextField(
            id="fldwSc9PqedIhTSqhi1", pk="fldwSc9PqedIhTSqhi1", name="Single line text"
        ),
        "baserow_field_type": TextFieldType(),
        "raw_airtable_column": RAW_AIRTABLE_TABLE["columns"][0],
        "airtable_column_type": None,
    },
    "fldwSc9PqedIhTSqhi2": {
        "baserow_field": TextField(
            id="fldwSc9PqedIhTSqhi2", pk="fldwSc9PqedIhTSqhi2", name="Single line text"
        ),
        "baserow_field_type": TextFieldType(),
        "raw_airtable_column": RAW_AIRTABLE_TABLE["columns"][1],
        "airtable_column_type": None,
    },
}
RAW_AIRTABLE_GRID_VIEW_DATA = {
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
RAW_AIRTABLE_GALLERY_VIEW_DATA = {
    "id": "viwcpYeEpAs6kZspktV",
    "frozenColumnCount": 1,
    "columnOrder": [
        {"columnId": "fldwSc9PqedIhTSqhi1", "visibility": True},
        {"columnId": "fldwSc9PqedIhTSqhi2", "visibility": False},
    ],
    "filters": None,
    "lastSortsApplied": None,
    "groupLevels": None,
    "colorConfig": None,
    "sharesById": {},
    "metadata": {"gallery": {"coverColumnId": None, "coverFitType": "fit"}},
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
            "conjunction": "and",
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
    "conjunction": "or",
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
RAW_VIEW_COLOR_CONFIG_SELECT_COLUMN = {
    "type": "selectColumn",
    "selectColumnId": "fldwSc9PqedIhTSqhi1",
    "colorDefinitions": None,
    "defaultColor": None,
}
RAW_VIEW_COLOR_CONFIG_COLOR_DEFINITIONS = {
    "type": "colorDefinitions",
    "colorDefinitions": [
        {
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
                    "conjunction": "and",
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
                        {
                            "id": "flthuYL0uubbDF2Xz",
                            "type": "nested",
                            "conjunction": "or",
                            "filterSet": [
                                {
                                    "id": "flt70g1l245672xRi",
                                    "columnId": "fldwSc9PqedIhTSqhi1",
                                    "operator": "!=",
                                    "value": "test",
                                },
                            ],
                        },
                    ],
                },
            ],
            "conjunction": "or",
            "color": "yellow",
        }
    ],
    "defaultColor": "teal",
}


def test_import_grid_view():
    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        RAW_AIRTABLE_GRID_VIEW_DATA,
        AirtableImportConfig(),
        AirtableImportReport(),
    )

    assert serialized_view == {
        "decorations": [],
        "field_options": [
            {
                "id": "viwcpYeEpAs6kZspktV_columnOrder_0",
                "field_id": "fldwSc9PqedIhTSqhi1",
                "width": 172,
                "hidden": False,
                "order": 1,
                "aggregation_type": "",
                "aggregation_raw_type": "",
            },
            {
                "id": "viwcpYeEpAs6kZspktV_columnOrder_1",
                "field_id": "fldwSc9PqedIhTSqhi2",
                "width": 200,
                "hidden": False,
                "order": 2,
                "aggregation_type": "",
                "aggregation_raw_type": "",
            },
        ],
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


def test_import_personal_view():
    raw_airtable_table = deepcopy(RAW_AIRTABLE_TABLE)
    raw_airtable_table["views"][0]["personalForUserId"] = "usr1234"
    raw_airtable_view = raw_airtable_table["views"][0]

    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        raw_airtable_table,
        raw_airtable_view,
        RAW_AIRTABLE_GRID_VIEW_DATA,
        AirtableImportConfig(),
        import_report,
    )

    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Grid view"
    assert import_report.items[0].scope == SCOPE_VIEW
    assert import_report.items[0].table == "Data"
    assert serialized_view["name"] == "Grid view (Personal)"


def test_import_locked_view():
    raw_airtable_table = deepcopy(RAW_AIRTABLE_TABLE)
    raw_airtable_table["views"][0]["lock"] = {
        "lockLevelToEditViewName": "locked",
        "lockLevelToEditViewDescription": "locked",
        "lockLevelToEditViewLayout": "locked",
        "lockLevelToEditViewConfig": "locked",
        "lockLevelToCreateShareLink": "locked",
        "lockLevelToDestroyView": "locked",
        "allowFormSubmitterToIgnoreLockLevel": False,
        "shouldWorkflowsRespectLockLevel": False,
        "userId": "usripyu12348WK3n",
        "description": None,
    }
    raw_airtable_view = raw_airtable_table["views"][0]

    import_report = AirtableImportReport()
    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        raw_airtable_table,
        raw_airtable_view,
        RAW_AIRTABLE_GRID_VIEW_DATA,
        AirtableImportConfig(),
        import_report,
    )

    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Grid view"
    assert import_report.items[0].scope == SCOPE_VIEW
    assert import_report.items[0].table == "Data"
    assert serialized_view["name"] == "Grid view"


def test_import_grid_view_xlarge_row_height():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    view_data["metadata"]["grid"]["rowHeight"] = "xlarge"

    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )

    assert serialized_view["row_height_size"] == "large"


def test_import_grid_view_unknown_row_height():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    view_data["metadata"]["grid"]["rowHeight"] = "unknown"

    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )

    assert serialized_view["row_height_size"] == "small"


def test_import_grid_view_sorts():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    view_data["lastSortsApplied"] = RAW_VIEW_DATA_SORTS
    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
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
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert serialized_view["sortings"] == [
        {"id": "srtglUy98ghs5ou8D", "field_id": "fldwSc9PqedIhTSqhi1", "order": "DESC"}
    ]


def test_import_grid_view_sort_field_not_found():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    view_data["lastSortsApplied"] = RAW_VIEW_DATA_SORTS
    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        {},
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )
    assert serialized_view["sortings"] == []
    assert len(import_report.items) == 1
    assert (
        import_report.items[0].object_name
        == 'View "Grid view", Field ID "Single line text"'
    )
    assert import_report.items[0].scope == SCOPE_VIEW_SORT
    assert import_report.items[0].table == "Data"


def test_import_grid_view_sort_field_unsupported():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    field_mapping["fldwSc9PqedIhTSqhi1"]["baserow_field_type"]._can_order_by_types = []

    view_data["lastSortsApplied"] = RAW_VIEW_DATA_SORTS
    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )
    assert serialized_view["sortings"] == []
    assert len(import_report.items) == 1
    assert (
        import_report.items[0].object_name
        == 'View "Grid view", Field "Single line text"'
    )
    assert import_report.items[0].scope == SCOPE_VIEW_SORT
    assert import_report.items[0].table == "Data"


def test_import_grid_view_group_bys():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    view_data["groupLevels"] = RAW_VIEW_DATA_GROUPS
    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert serialized_view["group_bys"] == [
        {"id": "glvvqP2okySUA2345", "field_id": "fldwSc9PqedIhTSqhi1", "order": "ASC"}
    ]

    view_data["groupLevels"][0]["order"] = "descending"
    airtable_view_type = airtable_view_type_registry.get("grid")
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert serialized_view["group_bys"] == [
        {"id": "glvvqP2okySUA2345", "field_id": "fldwSc9PqedIhTSqhi1", "order": "DESC"}
    ]


def test_import_grid_view_group_by_field_not_found():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    view_data["groupLevels"] = RAW_VIEW_DATA_GROUPS
    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        {},
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )
    assert serialized_view["group_bys"] == []
    assert len(import_report.items) == 1
    assert (
        import_report.items[0].object_name
        == 'View "Grid view", Field ID "Single line text"'
    )
    assert import_report.items[0].scope == SCOPE_VIEW_GROUP_BY
    assert import_report.items[0].table == "Data"


def test_import_grid_view_group_by_field_unsupported():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    field_mapping["fldwSc9PqedIhTSqhi1"]["baserow_field_type"]._can_group_by = False

    view_data["groupLevels"] = RAW_VIEW_DATA_GROUPS
    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )
    assert serialized_view["group_bys"] == []
    assert len(import_report.items) == 1
    assert (
        import_report.items[0].object_name
        == 'View "Grid view", Field "Single line text"'
    )
    assert import_report.items[0].scope == SCOPE_VIEW_GROUP_BY
    assert import_report.items[0].table == "Data"


def test_import_grid_view_group_by_order_unsupported():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    view_data["groupLevels"] = RAW_VIEW_DATA_GROUPS
    airtable_view_type = airtable_view_type_registry.get("grid")

    view_data["groupLevels"][0]["order"] = "UNKNOWN"
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )
    assert serialized_view["group_bys"] == []
    assert len(import_report.items) == 1
    assert (
        import_report.items[0].object_name
        == 'View "Grid view", Field "Single line text"'
    )
    assert import_report.items[0].scope == SCOPE_VIEW_GROUP_BY
    assert import_report.items[0].table == "Data"


def test_import_grid_view_field_order_and_visibility():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    airtable_view_type = airtable_view_type_registry.get("grid")

    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )

    assert serialized_view["field_options"] == [
        {
            "id": "viwcpYeEpAs6kZspktV_columnOrder_0",
            "field_id": "fldwSc9PqedIhTSqhi1",
            "width": 172,
            "hidden": False,
            "order": 1,
            "aggregation_type": "",
            "aggregation_raw_type": "",
        },
        {
            "id": "viwcpYeEpAs6kZspktV_columnOrder_1",
            "field_id": "fldwSc9PqedIhTSqhi2",
            "width": 200,
            "hidden": False,
            "order": 2,
            "aggregation_type": "",
            "aggregation_raw_type": "",
        },
    ]


@pytest.mark.django_db
def test_import_grid_view_filters_and_groups():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    for field_object in field_mapping.values():
        field_object["baserow_field"].content_type = ContentType.objects.get_for_model(
            field_object["baserow_field"]
        )

    view_data["filters"] = RAW_VIEW_DATA_FILTERS

    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )

    assert serialized_view["filter_type"] == "OR"
    assert serialized_view["filters_disabled"] is False

    assert serialized_view["filters"] == [
        {
            "id": "fltp2gabc8P91234f",
            "field_id": "fldwSc9PqedIhTSqhi1",
            "type": "not_empty",
            "value": "",
            "group": None,
        },
        {
            "id": "flt70g1l245672xRi",
            "field_id": "fldwSc9PqedIhTSqhi1",
            "type": "not_equal",
            "value": "test",
            "group": "flthuYL0uubbDF2Xy",
        },
        {
            "id": "fltVg238719fbIKqC",
            "field_id": "fldwSc9PqedIhTSqhi2",
            "type": "not_equal",
            "value": "test2",
            "group": "flthuYL0uubbDF2Xy",
        },
    ]
    assert serialized_view["filter_groups"] == [
        {"id": "flthuYL0uubbDF2Xy", "filter_type": "AND", "parent_group": None}
    ]


@pytest.mark.django_db
def test_import_grid_view_empty_filters():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    for field_object in field_mapping.values():
        field_object["baserow_field"].content_type = ContentType.objects.get_for_model(
            field_object["baserow_field"]
        )

    view_data["filters"] = {"filterSet": [], "conjunction": "and"}

    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )

    assert serialized_view["filter_type"] == "AND"
    assert serialized_view["filters_disabled"] is False
    assert serialized_view["filters"] == []
    assert serialized_view["filter_groups"] == []


@pytest.mark.django_db
def test_import_grid_view_color_config_select_column_not_existing_column():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    for field_object in field_mapping.values():
        field_object["baserow_field"].content_type = ContentType.objects.get_for_model(
            field_object["baserow_field"]
        )

    view_data["colorConfig"] = deepcopy(RAW_VIEW_COLOR_CONFIG_SELECT_COLUMN)
    view_data["colorConfig"]["selectColumnId"] = "fld123"

    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Grid view"
    assert import_report.items[0].scope == SCOPE_VIEW_COLOR
    assert import_report.items[0].table == "Data"


@pytest.mark.django_db
def test_import_grid_view_color_config_select_column():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    for field_object in field_mapping.values():
        field_object["baserow_field"].content_type = ContentType.objects.get_for_model(
            field_object["baserow_field"]
        )

    view_data["colorConfig"] = RAW_VIEW_COLOR_CONFIG_SELECT_COLUMN

    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 0

    assert serialized_view["decorations"] == [
        {
            "id": "viwcpYeEpAs6kZspktV_decoration",
            "type": "left_border_color",
            "value_provider_type": "single_select_color",
            "value_provider_conf": {"field_id": "fldwSc9PqedIhTSqhi1"},
            "order": 1,
        }
    ]


@pytest.mark.django_db
def test_import_grid_view_color_config_color_definitions():
    view_data = deepcopy(RAW_AIRTABLE_GRID_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    for field_object in field_mapping.values():
        field_object["baserow_field"].content_type = ContentType.objects.get_for_model(
            field_object["baserow_field"]
        )

    view_data["colorConfig"] = RAW_VIEW_COLOR_CONFIG_COLOR_DEFINITIONS

    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        RAW_AIRTABLE_VIEW,
        view_data,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 0

    assert serialized_view["decorations"] == [
        {
            "id": "viwcpYeEpAs6kZspktV_decoration",
            "type": "left_border_color",
            "value_provider_type": "conditional_color",
            "value_provider_conf": {
                "colors": [
                    {
                        "filter_groups": [
                            {
                                "id": "flthuYL0uubbDF2Xy",
                                "filter_type": "AND",
                                "parent_group": None,
                            },
                            {
                                "id": "flthuYL0uubbDF2Xz",
                                "filter_type": "OR",
                                "parent_group": "flthuYL0uubbDF2Xy",
                            },
                        ],
                        "filters": [
                            {
                                "id": "fltp2gabc8P91234f",
                                "type": "not_empty",
                                "field": "fldwSc9PqedIhTSqhi1",
                                "group": None,
                                "value": "",
                            },
                            {
                                "id": "flt70g1l245672xRi",
                                "type": "not_equal",
                                "field": "fldwSc9PqedIhTSqhi1",
                                "group": "flthuYL0uubbDF2Xy",
                                "value": "test",
                            },
                            {
                                "id": "fltVg238719fbIKqC",
                                "type": "not_equal",
                                "field": "fldwSc9PqedIhTSqhi2",
                                "group": "flthuYL0uubbDF2Xy",
                                "value": "test2",
                            },
                            {
                                "id": "flt70g1l245672xRi",
                                "type": "not_equal",
                                "field": "fldwSc9PqedIhTSqhi1",
                                "group": "flthuYL0uubbDF2Xz",
                                "value": "test",
                            },
                        ],
                        "operator": "OR",
                        "color": "light-yellow",
                    },
                    {
                        "filter_groups": [],
                        "filters": [],
                        "operator": "AND",
                        "color": "light-pink",
                    },
                ]
            },
            "order": 1,
        }
    ]


def test_import_gallery_view():
    view_data = deepcopy(RAW_AIRTABLE_GALLERY_VIEW_DATA)
    field_mapping = deepcopy(FIELD_MAPPING)
    airtable_view_type = airtable_view_type_registry.get("gallery")

    raw_airtable_view = deepcopy(RAW_AIRTABLE_VIEW)
    raw_airtable_view["name"] = "Gallery view"
    raw_airtable_view["type"] = "gallery"

    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        RAW_AIRTABLE_TABLE,
        raw_airtable_view,
        view_data,
        AirtableImportConfig(),
        import_report,
    )

    assert len(import_report.items) == 0
    assert serialized_view == {
        "id": "viwcpYeEpAs6kZspktV",
        "type": "gallery",
        "name": "Gallery view",
        "order": 1,
        "ownership_type": "collaborative",
        "owned_by": None,
        "filter_type": "AND",
        "filters_disabled": False,
        "filters": [],
        "filter_groups": [],
        "sortings": [],
        "decorations": [],
        "public": False,
        "field_options": [
            {
                "id": "viwcpYeEpAs6kZspktV_columnOrder_0",
                "field_id": "fldwSc9PqedIhTSqhi1",
                "hidden": False,
                "order": 1,
            },
            {
                "id": "viwcpYeEpAs6kZspktV_columnOrder_1",
                "field_id": "fldwSc9PqedIhTSqhi2",
                "hidden": True,
                "order": 2,
            },
        ],
    }


def test_import_gallery_view_with_cover_column():
    airtable_view_type = airtable_view_type_registry.get("gallery")

    view_data = deepcopy(RAW_AIRTABLE_GALLERY_VIEW_DATA)
    view_data["metadata"]["gallery"]["coverColumnId"] = "fldwSc9PqedIhTSqhi3"
    view_data["metadata"]["gallery"]["coverFitType"] = "crop"

    raw_airtable_view = deepcopy(RAW_AIRTABLE_VIEW)
    raw_airtable_view["name"] = "Gallery view"
    raw_airtable_view["type"] = "gallery"

    raw_airtable_table = deepcopy(RAW_AIRTABLE_TABLE)
    raw_airtable_table["columns"].append(
        {"id": "fldwSc9PqedIhTSqhi3", "name": "File", "type": "multipleAttachment"},
    )

    field_mapping = deepcopy(FIELD_MAPPING)
    field_mapping["fldwSc9PqedIhTSqhi3"] = {
        "baserow_field": FileField(
            id="fldwSc9PqedIhTSqhi3", pk="fldwSc9PqedIhTSqhi3", name="File"
        ),
        "baserow_field_type": FileFieldType(),
        "raw_airtable_column": raw_airtable_table["columns"][2],
        "airtable_column_type": None,
    }

    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        raw_airtable_table,
        raw_airtable_view,
        view_data,
        AirtableImportConfig(),
        import_report,
    )

    assert len(import_report.items) == 0
    assert serialized_view["card_cover_image_field_id"] == "fldwSc9PqedIhTSqhi3"


def test_import_gallery_view_with_unknown_cover_column():
    airtable_view_type = airtable_view_type_registry.get("gallery")

    view_data = deepcopy(RAW_AIRTABLE_GALLERY_VIEW_DATA)
    view_data["metadata"]["gallery"]["coverColumnId"] = "fldwSc9PqedIhTSqhi3"

    raw_airtable_view = deepcopy(RAW_AIRTABLE_VIEW)
    raw_airtable_view["name"] = "Gallery view"
    raw_airtable_view["type"] = "gallery"

    raw_airtable_table = deepcopy(RAW_AIRTABLE_TABLE)

    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        raw_airtable_table,
        raw_airtable_view,
        view_data,
        AirtableImportConfig(),
        import_report,
    )

    assert "card_cover_image_field_id" not in serialized_view
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Gallery view"
    assert import_report.items[0].scope == SCOPE_VIEW
    assert import_report.items[0].table == "Data"


def test_import_gallery_view_with_incompatible_cover_column():
    airtable_view_type = airtable_view_type_registry.get("gallery")

    view_data = deepcopy(RAW_AIRTABLE_GALLERY_VIEW_DATA)
    view_data["metadata"]["gallery"]["coverColumnId"] = "fldwSc9PqedIhTSqhi2"

    raw_airtable_view = deepcopy(RAW_AIRTABLE_VIEW)
    raw_airtable_view["name"] = "Gallery view"
    raw_airtable_view["type"] = "gallery"

    raw_airtable_table = deepcopy(RAW_AIRTABLE_TABLE)

    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        raw_airtable_table,
        raw_airtable_view,
        view_data,
        AirtableImportConfig(),
        import_report,
    )

    assert "card_cover_image_field_id" not in serialized_view
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Gallery view"
    assert import_report.items[0].scope == SCOPE_VIEW
    assert import_report.items[0].table == "Data"


def test_import_gallery_view_with_cover_column_type_fit():
    airtable_view_type = airtable_view_type_registry.get("gallery")

    view_data = deepcopy(RAW_AIRTABLE_GALLERY_VIEW_DATA)
    view_data["metadata"]["gallery"]["coverColumnId"] = "fldwSc9PqedIhTSqhi3"
    view_data["metadata"]["gallery"]["coverFitType"] = "fit"

    raw_airtable_view = deepcopy(RAW_AIRTABLE_VIEW)
    raw_airtable_view["name"] = "Gallery view"
    raw_airtable_view["type"] = "gallery"

    raw_airtable_table = deepcopy(RAW_AIRTABLE_TABLE)
    raw_airtable_table["columns"].append(
        {"id": "fldwSc9PqedIhTSqhi3", "name": "File", "type": "multipleAttachment"},
    )

    field_mapping = deepcopy(FIELD_MAPPING)
    field_mapping["fldwSc9PqedIhTSqhi3"] = {
        "baserow_field": FileField(
            id="fldwSc9PqedIhTSqhi3", pk="fldwSc9PqedIhTSqhi3", name="File"
        ),
        "baserow_field_type": FileFieldType(),
        "raw_airtable_column": raw_airtable_table["columns"][2],
        "airtable_column_type": None,
    }

    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        field_mapping,
        ROW_ID_MAPPING,
        raw_airtable_table,
        raw_airtable_view,
        view_data,
        AirtableImportConfig(),
        import_report,
    )

    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Gallery view"
    assert import_report.items[0].scope == SCOPE_VIEW
    assert import_report.items[0].table == "Data"
    assert serialized_view["card_cover_image_field_id"] == "fldwSc9PqedIhTSqhi3"


def test_import_view_in_section_order():
    raw_airtable_table = deepcopy(RAW_AIRTABLE_TABLE)
    raw_airtable_table["viewOrder"] = ["vsc0001", "vsc0002", "viw00005"]
    raw_airtable_table["viewSectionsById"] = {
        "vsc0001": {
            "id": "vsc0001",
            "name": "Section 1",
            "createdByUserId": "usr0001",
            "pinnedForUserId": None,
            "viewOrder": ["viw00001", "viw00002"],
        },
        "vsc0002": {
            "id": "vsc0001",
            "name": "Section 1",
            "createdByUserId": "usr0001",
            "pinnedForUserId": None,
            "viewOrder": [RAW_AIRTABLE_VIEW["id"], "viw00004"],
        },
    }

    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        raw_airtable_table,
        RAW_AIRTABLE_VIEW,
        RAW_AIRTABLE_GRID_VIEW_DATA,
        AirtableImportConfig(),
        import_report,
    )

    assert serialized_view["order"] == 3


def test_import_view_in_section_name():
    raw_airtable_table = deepcopy(RAW_AIRTABLE_TABLE)
    raw_airtable_table["viewOrder"] = ["vsc0001", "vsc0002", "viw00005"]
    raw_airtable_table["viewSectionsById"] = {
        "vsc0001": {
            "id": "vsc0001",
            "name": "Section 1",
            "createdByUserId": "usr0001",
            "pinnedForUserId": None,
            "viewOrder": ["viw00001", "viw00002"],
        },
        "vsc0002": {
            "id": "vsc0001",
            "name": "Section 2",
            "createdByUserId": "usr0001",
            "pinnedForUserId": None,
            "viewOrder": [RAW_AIRTABLE_VIEW["id"], "viw00004"],
        },
    }

    airtable_view_type = airtable_view_type_registry.get("grid")
    import_report = AirtableImportReport()
    serialized_view = airtable_view_type.to_serialized_baserow_view(
        FIELD_MAPPING,
        ROW_ID_MAPPING,
        raw_airtable_table,
        RAW_AIRTABLE_VIEW,
        RAW_AIRTABLE_GRID_VIEW_DATA,
        AirtableImportConfig(),
        import_report,
    )

    assert serialized_view["name"] == "Section 2 / Grid view"
