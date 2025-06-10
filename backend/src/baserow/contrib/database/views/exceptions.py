from baserow.core.exceptions import (
    InstanceTypeAlreadyRegistered,
    InstanceTypeDoesNotExist,
)


class ViewDoesNotExist(Exception):
    """Raised when trying to get a view that doesn't exist."""


class CannotShareViewTypeError(Exception):
    """Raised when trying to a share a view that cannot be shared"""


class ViewNotInTable(Exception):
    """Raised when a provided view does not belong to a table."""

    def __init__(self, view_id=None, *args, **kwargs):
        self.view_id = view_id
        super().__init__(
            f"The view {view_id} does not belong to the table.",
            *args,
            **kwargs,
        )


class UnrelatedFieldError(Exception):
    """
    Raised when a field is not related to the view. For example when someone tries to
    update field options of a field that does not belong to the view's table.
    """


class ViewTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass


class ViewTypeDoesNotExist(InstanceTypeDoesNotExist):
    pass


class ViewFilterDoesNotExist(Exception):
    """Raised when trying to get a view filter that does not exist."""


class ViewFilterGroupDoesNotExist(Exception):
    """Raised when trying to get a view filter that does not exist."""


class ViewFilterNotSupported(Exception):
    """Raised when the view type does not support filters."""


class ViewFilterTypeNotAllowedForField(Exception):
    """Raised when the view filter type is compatible with the field type."""

    def __init__(self, filter_type=None, field_type=None, *args, **kwargs):
        self.filter_type = filter_type
        self.field_type = field_type
        super().__init__(
            f"The view filter type {filter_type} is not compatible with field type "
            f"{field_type}.",
            *args,
            **kwargs,
        )


class ViewFilterTypeDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when the view filter type was not found in the registry."""


class ViewFilterTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    """Raised when the view filter type is already registered in the registry."""


class ViewSortDoesNotExist(Exception):
    """Raised when trying to get a view sort that does not exist."""


class ViewSortNotSupported(Exception):
    """Raised when the view type does not support sorting."""


class ViewSortFieldAlreadyExist(Exception):
    """Raised when a view sort with the field type already exists."""


class ViewSortFieldNotSupported(Exception):
    """Raised when a field does not support sorting in a view."""


class ViewGroupByDoesNotExist(Exception):
    """Raised when trying to get a view group by that does not exist."""


class ViewGroupByNotSupported(Exception):
    """Raised when the view type does not support grouping."""


class ViewGroupByFieldAlreadyExist(Exception):
    """Raised when a view group by with the field type already exists."""


class ViewGroupByFieldNotSupported(Exception):
    """Raised when a field does not support grouping in a view."""


class ViewDoesNotSupportFieldOptions(Exception):
    """Raised when a view type does not support field options."""


class ViewDoesNotSupportListingRows(Exception):
    """Raised when a view type does not support listing rows."""


class FieldAggregationNotSupported(Exception):
    """Raised when the view type does not support field aggregation."""


class AggregationTypeDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when trying to get an aggregation type that does not exist."""


class AggregationTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    """Raised when trying to register an aggregation type that exists already."""


class DecoratorValueProviderTypeDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when trying to get a decorator value provider type that does not exist."""


class DecoratorValueProviderTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    """
    Raised when trying to register a decorator value provider type that exists
    already.
    """


class DecoratorTypeDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when trying to get a decorator type that does not exist."""


class DecoratorTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    """
    Raised when trying to register a decorator type that exists
    already.
    """


class GridViewAggregationDoesNotSupportField(Exception):
    """
    Raised when someone tries to use an aggregation type that doesn't support the
    given field.
    """

    def __init__(self, aggregation_type, *args, **kwargs):
        self.aggregation_type = aggregation_type
        super().__init__(
            (
                f"The aggregation type {aggregation_type} is not compatible with the "
                " given field."
            ),
            *args,
            **kwargs,
        )


class ViewDecorationDoesNotExist(Exception):
    """Raised when trying to get a view decoration that does not exist."""


class ViewDecorationNotSupported(Exception):
    """Raised when the view type does not support aggregations."""


class DecoratorValueProviderTypeNotCompatible(Exception):
    """
    Raised when a value provider type is not compatible with the current
    decorator.
    """


class FormViewFieldTypeIsNotSupported(Exception):
    """Raised when someone tries to enable an unsupported form view field."""

    def __init__(self, field_type, *args, **kwargs):
        self.field_type = field_type
        super().__init__(
            f"The field type {field_type} is not compatible with the form view.",
            *args,
            **kwargs,
        )


class FormViewReadOnlyFieldIsNotSupported(Exception):
    """Raised when someone tries to enable a read only field."""

    def __init__(self, field_name, *args, **kwargs):
        self.field_name = field_name
        super().__init__(
            f"The field {field_name} is read only and compatible with the form"
            f"view.",
            *args,
            **kwargs,
        )


class NoAuthorizationToPubliclySharedView(Exception):
    """
    Raised when someone tries to access a view without a valid authorization
    token.
    """


class ViewOwnershipTypeDoesNotExist(InstanceTypeDoesNotExist):
    """
    Raised when trying to get a view ownership type
    that does not exist.
    """


class InvalidAPIGroupedFiltersFormatException(ValueError):
    """
    Raised when the provided view filters format is invalid.
    """
