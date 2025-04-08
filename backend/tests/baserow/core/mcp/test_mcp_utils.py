from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.mcp.utils import serializer_to_openapi_inline
from baserow.contrib.database.api.tables.serializers import TableSerializer
from baserow.contrib.database.api.views.serializers import ViewSerializer, \
    CreateViewSerializer


def test_serializer_to_openapi_inline():
    assert serializer_to_openapi_inline(TableSerializer) == {
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True
            },
            "name": {
                "type": "string",
                "maxLength": 255
            },
            "order": {
                "type": "integer",
                "maximum": 2147483647,
                "minimum": 0,
                "description": "Lowest first."
            },
            "database_id": {
                "type": "integer",
                "readOnly": True
            },
            "data_sync": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "readOnly": True
                    },
                    "type": {
                        "type": "string",
                        "readOnly": True
                    },
                    "synced_properties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field_id": {
                                    "type": "integer",
                                    "readOnly": True
                                },
                                "key": {
                                    "type": "string",
                                    "description": "The matching `key` of the `DataSyncProperty`.",
                                    "maxLength": 255
                                },
                                "unique_primary": {
                                    "type": "boolean",
                                    "description": "Indicates whether the data sync property is used for unique identification when syncing."
                                }
                            },
                            "required": [
                                "field_id",
                                "key"
                            ]
                        }
                    },
                    "last_sync": {
                        "type": "string",
                        "format": "date-time",
                        "nullable": True,
                        "description": "Timestamp when the table was last synced."
                    },
                    "last_error": {
                        "type": "string",
                        "nullable": True
                    }
                },
                "required": [
                    "id",
                    "synced_properties",
                    "type"
                ]
            }
        },
        "required": [
            "data_sync",
            "database_id",
            "id",
            "name",
            "order"
        ]
    }


def test_polymorphic_serializer_to_openapi_inline():
    assert serializer_to_openapi_inline(DiscriminatorCustomFieldsMappingSerializer(
        view_type_registry, CreateViewSerializer
    )) == {}
