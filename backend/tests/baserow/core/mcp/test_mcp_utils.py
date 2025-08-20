from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.contrib.database.api.tables.serializers import TableSerializer
from baserow.contrib.database.api.views.serializers import CreateViewSerializer
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.mcp.utils import serializer_to_openapi_inline


def test_serializer_to_openapi_inline():
    assert serializer_to_openapi_inline(TableSerializer) == {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "readOnly": True},
            "name": {"type": "string", "maxLength": 255},
            "order": {
                "type": "integer",
                "maximum": 2147483647,
                "minimum": 0,
                "description": "Lowest first.",
            },
            "database_id": {"type": "integer", "readOnly": True},
            "data_sync": {
                "type": "object",
                # Confirm that the child serializers are not rendered as `$ref`, but
                # rather fully inline.
                "properties": {
                    "auto_add_new_properties": {
                        "description": "If enabled and new properties are detected on sync, then they're automatically added. Note that this means all properties will always be added.",
                        "type": "boolean",
                    },
                    "two_way_sync": {
                        "description": "If enabled, then it's possible to make changes to the synced table. They will automatically be synced with the source data. Note that this is only possible if the data sync type has a two-way sync strategy.",
                        "type": "boolean",
                    },
                    "id": {"type": "integer", "readOnly": True},
                    "type": {"type": "string", "readOnly": True},
                    "synced_properties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field_id": {"type": "integer", "readOnly": True},
                                "key": {
                                    "type": "string",
                                    "description": "The matching `key` of the `DataSyncProperty`.",
                                    "maxLength": 255,
                                },
                                "unique_primary": {
                                    "type": "boolean",
                                    "description": "Indicates whether the data sync property is used for unique identification when syncing.",
                                },
                            },
                            "required": ["field_id", "key"],
                        },
                    },
                    "last_sync": {
                        "type": "string",
                        "format": "date-time",
                        "nullable": True,
                        "description": "Timestamp when the table was last synced.",
                    },
                    "last_error": {"type": "string", "nullable": True},
                },
                "required": [
                    "id",
                    "synced_properties",
                    "type",
                ],
            },
        },
        "required": ["data_sync", "database_id", "id", "name", "order"],
    }


def test_polymorphic_serializer_to_openapi_inline():
    assert serializer_to_openapi_inline(
        DiscriminatorCustomFieldsMappingSerializer(
            view_type_registry, CreateViewSerializer
        )
    ) == {
        # Confirm that the function is compatible with OpenAPI extensions, and the
        # `DiscriminatorCustomFieldsMappingSerializer` in particular.
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "type": {
                        "enum": [
                            "grid",
                            "gallery",
                            "form",
                            "kanban",
                            "calendar",
                            "timeline",
                        ],
                        "type": "string",
                        "description": "* `grid` - grid\n* `gallery` - gallery\n* `form` - form\n* `kanban` - kanban\n* `calendar` - calendar\n* `timeline` - timeline",
                        "x-spec-enum-id": "bc45559484b1f708",
                    },
                    "ownership_type": {
                        "enum": ["collaborative", "personal", "restricted"],
                        "type": "string",
                        "description": "* `collaborative` - collaborative\n* `personal` - personal\n* `restricted` - restricted",
                        "x-spec-enum-id": "c917b297d9d9ef1b",
                        "default": "collaborative",
                    },
                    "filter_type": {
                        "enum": ["AND", "OR"],
                        "type": "string",
                        "x-spec-enum-id": "04b3a389dad7c22c",
                        "description": "Indicates whether all the rows should apply to all filters (AND) or to any filter (OR).\n\n* `AND` - And\n* `OR` - Or",
                    },
                    "filters_disabled": {
                        "type": "boolean",
                        "description": "Allows users to see results unfiltered while still keeping the filters saved for the view.",
                    },
                    "row_identifier_type": {
                        "enum": ["id", "count"],
                        "type": "string",
                        "description": "* `id` - Id\n* `count` - Count",
                        "x-spec-enum-id": "a3569210bd7d4ead",
                    },
                    "row_height_size": {
                        "enum": ["small", "medium", "large"],
                        "type": "string",
                        "description": "* `small` - Small\n* `medium` - Medium\n* `large` - Large",
                        "x-spec-enum-id": "e1be587fa89889c6",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Indicates whether the view is publicly accessible to visitors.",
                    },
                    "slug": {
                        "type": "string",
                        "readOnly": True,
                        "description": "The unique slug that can be used to construct a public URL.",
                    },
                },
                "required": ["name", "slug", "type"],
            },
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "type": {
                        "enum": [
                            "grid",
                            "gallery",
                            "form",
                            "kanban",
                            "calendar",
                            "timeline",
                        ],
                        "type": "string",
                        "description": "* `grid` - grid\n* `gallery` - gallery\n* `form` - form\n* `kanban` - kanban\n* `calendar` - calendar\n* `timeline` - timeline",
                        "x-spec-enum-id": "bc45559484b1f708",
                    },
                    "ownership_type": {
                        "enum": ["collaborative", "personal", "restricted"],
                        "type": "string",
                        "description": "* `collaborative` - collaborative\n* `personal` - personal\n* `restricted` - restricted",
                        "x-spec-enum-id": "c917b297d9d9ef1b",
                        "default": "collaborative",
                    },
                    "filter_type": {
                        "enum": ["AND", "OR"],
                        "type": "string",
                        "x-spec-enum-id": "04b3a389dad7c22c",
                        "description": "Indicates whether all the rows should apply to all filters (AND) or to any filter (OR).\n\n* `AND` - And\n* `OR` - Or",
                    },
                    "filters_disabled": {
                        "type": "boolean",
                        "description": "Allows users to see results unfiltered while still keeping the filters saved for the view.",
                    },
                    "card_cover_image_field": {
                        "type": "integer",
                        "nullable": True,
                        "description": "References a file field of which the first image must be shown as card cover image.",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Indicates whether the view is publicly accessible to visitors.",
                    },
                    "slug": {
                        "type": "string",
                        "readOnly": True,
                        "description": "The unique slug that can be used to construct a public URL.",
                    },
                },
                "required": ["name", "slug", "type"],
            },
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "type": {
                        "enum": [
                            "grid",
                            "gallery",
                            "form",
                            "kanban",
                            "calendar",
                            "timeline",
                        ],
                        "type": "string",
                        "description": "* `grid` - grid\n* `gallery` - gallery\n* `form` - form\n* `kanban` - kanban\n* `calendar` - calendar\n* `timeline` - timeline",
                        "x-spec-enum-id": "bc45559484b1f708",
                    },
                    "ownership_type": {
                        "enum": ["collaborative", "personal", "restricted"],
                        "type": "string",
                        "description": "* `collaborative` - collaborative\n* `personal` - personal\n* `restricted` - restricted",
                        "x-spec-enum-id": "c917b297d9d9ef1b",
                        "default": "collaborative",
                    },
                    "filter_type": {
                        "enum": ["AND", "OR"],
                        "type": "string",
                        "x-spec-enum-id": "04b3a389dad7c22c",
                        "description": "Indicates whether all the rows should apply to all filters (AND) or to any filter (OR).\n\n* `AND` - And\n* `OR` - Or",
                    },
                    "filters_disabled": {
                        "type": "boolean",
                        "description": "Allows users to see results unfiltered while still keeping the filters saved for the view.",
                    },
                    "title": {
                        "type": "string",
                        "description": "The title that is displayed at the beginning of the form.",
                    },
                    "description": {
                        "type": "string",
                        "description": "The description that is displayed at the beginning of the form.",
                    },
                    "mode": {
                        "enum": ["form", "survey"],
                        "type": "string",
                        "x-spec-enum-id": "51edacc237baaffe",
                        "description": "Configurable mode of the form.\n\n* `form` - form\n* `survey` - survey",
                    },
                    "cover_image": {
                        "type": "object",
                        "properties": {
                            "size": {
                                "type": "integer",
                                "maximum": 9223372036854775807,
                                "minimum": 0,
                                "format": "int64",
                            },
                            "mime_type": {"type": "string", "maxLength": 127},
                            "is_image": {"type": "boolean"},
                            "image_width": {
                                "type": "integer",
                                "maximum": 2147483647,
                                "minimum": 0,
                                "nullable": True,
                            },
                            "image_height": {
                                "type": "integer",
                                "maximum": 2147483647,
                                "minimum": 0,
                                "nullable": True,
                            },
                            "uploaded_at": {
                                "type": "string",
                                "format": "date-time",
                                "readOnly": True,
                            },
                            "url": {
                                "type": "string",
                                "format": "uri",
                                "readOnly": True,
                            },
                            "thumbnails": {
                                "type": "object",
                                "additionalProperties": {},
                                "readOnly": True,
                            },
                            "name": {"type": "string", "readOnly": True},
                            "original_name": {"type": "string", "maxLength": 255},
                        },
                        "required": [
                            "name",
                            "original_name",
                            "size",
                            "thumbnails",
                            "uploaded_at",
                            "url",
                        ],
                        "nullable": True,
                        "description": "The cover image that must be displayed at the top of the form.",
                    },
                    "logo_image": {
                        "type": "object",
                        "properties": {
                            "size": {
                                "type": "integer",
                                "maximum": 9223372036854775807,
                                "minimum": 0,
                                "format": "int64",
                            },
                            "mime_type": {"type": "string", "maxLength": 127},
                            "is_image": {"type": "boolean"},
                            "image_width": {
                                "type": "integer",
                                "maximum": 2147483647,
                                "minimum": 0,
                                "nullable": True,
                            },
                            "image_height": {
                                "type": "integer",
                                "maximum": 2147483647,
                                "minimum": 0,
                                "nullable": True,
                            },
                            "uploaded_at": {
                                "type": "string",
                                "format": "date-time",
                                "readOnly": True,
                            },
                            "url": {
                                "type": "string",
                                "format": "uri",
                                "readOnly": True,
                            },
                            "thumbnails": {
                                "type": "object",
                                "additionalProperties": {},
                                "readOnly": True,
                            },
                            "name": {"type": "string", "readOnly": True},
                            "original_name": {"type": "string", "maxLength": 255},
                        },
                        "required": [
                            "name",
                            "original_name",
                            "size",
                            "thumbnails",
                            "uploaded_at",
                            "url",
                        ],
                        "nullable": True,
                        "description": "The logo image that must be displayed at the top of the form.",
                    },
                    "submit_text": {
                        "type": "string",
                        "description": "The text displayed on the submit button.",
                    },
                    "submit_action": {
                        "enum": ["MESSAGE", "REDIRECT"],
                        "type": "string",
                        "x-spec-enum-id": "a7241a3e2e370277",
                        "description": "The action that must be performed after the visitor has filled out the form.\n\n* `MESSAGE` - Message\n* `REDIRECT` - Redirect",
                    },
                    "submit_action_message": {
                        "type": "string",
                        "description": "If the `submit_action` is MESSAGE, then this message will be shown to the visitor after submitting the form.",
                    },
                    "submit_action_redirect_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "If the `submit_action` is REDIRECT,then the visitors will be redirected to the this URL after submitting the form.",
                        "maxLength": 2000,
                    },
                    "receive_notification_on_submit": {
                        "type": "boolean",
                        "readOnly": True,
                        "description": "A boolean indicating if the current user should be notified when the form is submitted.",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Indicates whether the view is publicly accessible to visitors.",
                    },
                    "slug": {
                        "type": "string",
                        "readOnly": True,
                        "description": "The unique slug that can be used to construct a public URL.",
                    },
                },
                "required": ["name", "receive_notification_on_submit", "slug", "type"],
            },
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "type": {
                        "enum": [
                            "grid",
                            "gallery",
                            "form",
                            "kanban",
                            "calendar",
                            "timeline",
                        ],
                        "type": "string",
                        "description": "* `grid` - grid\n* `gallery` - gallery\n* `form` - form\n* `kanban` - kanban\n* `calendar` - calendar\n* `timeline` - timeline",
                        "x-spec-enum-id": "bc45559484b1f708",
                    },
                    "ownership_type": {
                        "enum": ["collaborative", "personal", "restricted"],
                        "type": "string",
                        "description": "* `collaborative` - collaborative\n* `personal` - personal\n* `restricted` - restricted",
                        "x-spec-enum-id": "c917b297d9d9ef1b",
                        "default": "collaborative",
                    },
                    "filter_type": {
                        "enum": ["AND", "OR"],
                        "type": "string",
                        "x-spec-enum-id": "04b3a389dad7c22c",
                        "description": "Indicates whether all the rows should apply to all filters (AND) or to any filter (OR).\n\n* `AND` - And\n* `OR` - Or",
                    },
                    "filters_disabled": {
                        "type": "boolean",
                        "description": "Allows users to see results unfiltered while still keeping the filters saved for the view.",
                    },
                    "single_select_field": {"type": "integer", "nullable": True},
                    "card_cover_image_field": {
                        "type": "integer",
                        "nullable": True,
                        "description": "References a file field of which the first image must be shown as card cover image.",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Indicates whether the view is publicly accessible to visitors.",
                    },
                    "slug": {
                        "type": "string",
                        "readOnly": True,
                        "description": "The unique slug that can be used to construct a public URL.",
                    },
                },
                "required": ["name", "slug", "type"],
            },
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "type": {
                        "enum": [
                            "grid",
                            "gallery",
                            "form",
                            "kanban",
                            "calendar",
                            "timeline",
                        ],
                        "type": "string",
                        "description": "* `grid` - grid\n* `gallery` - gallery\n* `form` - form\n* `kanban` - kanban\n* `calendar` - calendar\n* `timeline` - timeline",
                        "x-spec-enum-id": "bc45559484b1f708",
                    },
                    "ownership_type": {
                        "enum": ["collaborative", "personal", "restricted"],
                        "type": "string",
                        "description": "* `collaborative` - collaborative\n* `personal` - personal\n* `restricted` - restricted",
                        "x-spec-enum-id": "c917b297d9d9ef1b",
                        "default": "collaborative",
                    },
                    "filter_type": {
                        "enum": ["AND", "OR"],
                        "type": "string",
                        "x-spec-enum-id": "04b3a389dad7c22c",
                        "description": "Indicates whether all the rows should apply to all filters (AND) or to any filter (OR).\n\n* `AND` - And\n* `OR` - Or",
                    },
                    "filters_disabled": {
                        "type": "boolean",
                        "description": "Allows users to see results unfiltered while still keeping the filters saved for the view.",
                    },
                    "date_field": {"type": "integer", "nullable": True},
                    "ical_feed_url": {
                        "type": "string",
                        "readOnly": True,
                        "description": "Read-only field with ICal feed endpoint. Note: this url will not be active if ical_public value is set to False.",
                    },
                    "ical_public": {
                        "type": "boolean",
                        "nullable": True,
                        "description": "A flag to show if ical feed is exposed. Set this field to True when modifying this resource to enable ICal feed url.",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Indicates whether the view is publicly accessible to visitors.",
                    },
                    "slug": {
                        "type": "string",
                        "readOnly": True,
                        "description": "The unique slug that can be used to construct a public URL.",
                    },
                },
                "required": ["ical_feed_url", "name", "slug", "type"],
            },
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "type": {
                        "enum": [
                            "grid",
                            "gallery",
                            "form",
                            "kanban",
                            "calendar",
                            "timeline",
                        ],
                        "type": "string",
                        "description": "* `grid` - grid\n* `gallery` - gallery\n* `form` - form\n* `kanban` - kanban\n* `calendar` - calendar\n* `timeline` - timeline",
                        "x-spec-enum-id": "bc45559484b1f708",
                    },
                    "ownership_type": {
                        "enum": ["collaborative", "personal", "restricted"],
                        "type": "string",
                        "description": "* `collaborative` - collaborative\n* `personal` - personal\n* `restricted` - restricted",
                        "x-spec-enum-id": "c917b297d9d9ef1b",
                        "default": "collaborative",
                    },
                    "filter_type": {
                        "enum": ["AND", "OR"],
                        "type": "string",
                        "x-spec-enum-id": "04b3a389dad7c22c",
                        "description": "Indicates whether all the rows should apply to all filters (AND) or to any filter (OR).\n\n* `AND` - And\n* `OR` - Or",
                    },
                    "filters_disabled": {
                        "type": "boolean",
                        "description": "Allows users to see results unfiltered while still keeping the filters saved for the view.",
                    },
                    "start_date_field": {"type": "integer", "nullable": True},
                    "end_date_field": {"type": "integer", "nullable": True},
                    "timescale": {
                        "enum": ["day", "week", "month", "year"],
                        "type": "string",
                        "x-spec-enum-id": "b47bd58ee0e62834",
                        "description": "The timescale that the timeline should be displayed in.\n\n* `day` - Day\n* `week` - Week\n* `month` - Month\n* `year` - Year",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Indicates whether the view is publicly accessible to visitors.",
                    },
                    "slug": {
                        "type": "string",
                        "readOnly": True,
                        "description": "The unique slug that can be used to construct a public URL.",
                    },
                },
                "required": ["name", "slug", "type"],
            },
        ],
        "discriminator": {"propertyName": "type", "mapping": {}},
    }
