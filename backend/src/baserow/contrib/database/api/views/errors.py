from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

ERROR_VIEW_DOES_NOT_EXIST = (
    "ERROR_VIEW_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested view does not exist.",
)
ERROR_VIEW_NOT_IN_TABLE = (
    "ERROR_VIEW_NOT_IN_TABLE",
    HTTP_400_BAD_REQUEST,
    "The view id {e.view_id} does not belong to the table.",
)
ERROR_VIEW_FILTER_DOES_NOT_EXIST = (
    "ERROR_VIEW_FILTER_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The view filter does not exist.",
)
ERROR_VIEW_FILTER_NOT_SUPPORTED = (
    "ERROR_VIEW_FILTER_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "Filtering is not supported for the view type.",
)
ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST = (
    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The view filter type {e.type_name} doesn't exist.",
)
ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD = (
    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
    HTTP_400_BAD_REQUEST,
    "The filter {e.filter_type} is not compatible with field type {e.field_type}.",
)
ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST = (
    "ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The view filter group does not exist.",
)
ERROR_VIEW_SORT_DOES_NOT_EXIST = (
    "ERROR_VIEW_SORT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The view sort does not exist.",
)
ERROR_VIEW_SORT_NOT_SUPPORTED = (
    "ERROR_VIEW_SORT_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "Sorting is not supported for the view type.",
)
ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS = (
    "ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS",
    HTTP_400_BAD_REQUEST,
    "A sort with the field already exists in the view.",
)
ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED = (
    "ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "The field does not support view sorting on the given type.",
)
ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST = (
    "ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The view group by does not exist.",
)
ERROR_VIEW_GROUP_BY_NOT_SUPPORTED = (
    "ERROR_VIEW_GROUP_BY_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "Grouping is not supported for the view type.",
)
ERROR_VIEW_GROUP_BY_FIELD_ALREADY_EXISTS = (
    "ERROR_VIEW_GROUP_BY_FIELD_ALREADY_EXISTS",
    HTTP_400_BAD_REQUEST,
    "A group by for the field already exists in the view.",
)
ERROR_VIEW_GROUP_BY_FIELD_NOT_SUPPORTED = (
    "ERROR_VIEW_GROUP_BY_FIELD_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "The field does not support view grouping.",
)
ERROR_UNRELATED_FIELD = (
    "ERROR_UNRELATED_FIELD",
    HTTP_400_BAD_REQUEST,
    "The field is not related to the provided view.",
)
ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS = (
    "ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS",
    HTTP_400_BAD_REQUEST,
    "This view model does not support field options.",
)
ERROR_AGGREGATION_TYPE_DOES_NOT_EXIST = (
    "ERROR_AGGREGATION_TYPE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The specified aggregation type does not exist.",
)
ERROR_VIEW_DECORATION_DOES_NOT_EXIST = (
    "ERROR_VIEW_DECORATION_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The view decoration does not exist.",
)
ERROR_VIEW_DECORATION_NOT_SUPPORTED = (
    "ERROR_VIEW_DECORATION_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "Decoration is not supported for the view type.",
)
ERROR_VIEW_DECORATION_VALUE_PROVIDER_NOT_COMPATIBLE = (
    "ERROR_VIEW_DECORATION_VALUE_PROVIDER_NOT_COMPATIBLE",
    HTTP_400_BAD_REQUEST,
    "The value provider is not compatible with the decorator type.",
)
ERROR_CANNOT_SHARE_VIEW_TYPE = (
    "ERROR_CANNOT_SHARE_VIEW_TYPE",
    HTTP_400_BAD_REQUEST,
    "This view type does not support sharing.",
)
ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW = (
    "ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW",
    HTTP_401_UNAUTHORIZED,
    "The user does not have the permissions to see this password protected shared view.",
)
ERROR_VIEW_OWNERSHIP_TYPE_DOES_NOT_EXIST = (
    "ERROR_VIEW_OWNERSHIP_TYPE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The view ownership type does not exist.",
)
ERROR_VIEW_DOES_NOT_SUPPORT_LISTING_ROWS = (
    "ERROR_VIEW_DOES_NOT_SUPPORT_LISTING_ROWS",
    HTTP_400_BAD_REQUEST,
    "This view type does not support listing rows.",
)
