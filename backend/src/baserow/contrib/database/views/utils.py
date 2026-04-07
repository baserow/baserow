from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser
from django.db.models.aggregates import Aggregate, Count

from baserow.core.exceptions import PermissionDenied, PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.registries import OperationType
from baserow.core.types import PermissionCheck

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import Table
    from baserow.contrib.database.views.models import View


class AnnotatedAggregation:
    """
    A simple wrapper class for combining multiple annotations with an aggregation.
    This can be used in places where typically just an aggregation is returned,
    but must optionally be able to apply annotations to the same queryset.
    """

    def __init__(self, annotations: Dict[str, Any], aggregation: Aggregate):
        """
        :param annotations: The annotation which can be applied to the queryset.
        :param aggregation: The aggregate which must be applied to the queryset.
        """

        self.annotations = annotations
        self.aggregation = aggregation


class DistributionAggregation:
    """
    Performs the equivalent of a SELECT field, count(*) FROM table GROUP BY field
    on the provided queryset.
    """

    def __init__(self, group_by):
        """
        :param group_by: The name of the queryset field that contains the values
            that need to be grouped by
        """

        self.group_by = group_by

    def calculate(self, queryset, limit=10):
        """
        Calculates the distribution of values in the `group_by` field in the queryset.
        Returns the top tep results, sorted by count descending.
        :param queryset: The queryset to calculate the distribution on
        :param limit: The number of results to return.
        """

        # Disable prefetch behaviors for this query
        queryset._multi_field_prefetch_related_funcs = []
        return list(
            queryset.values(self.group_by)
            .annotate(count=Count("*"))
            .order_by("-count", self.group_by)
            .values_list(self.group_by, "count")[:limit]
        )


def serialize_row_for_action(row, model) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build the serialized values dict and fields metadata for a row, to be used
    when registering form-related actions for the audit log.

    :param row: The row instance.
    :param model: The generated table model.
    :return: A tuple of (serialized_values, fields_metadata).
    """

    from baserow.contrib.database.rows.handler import RowHandler

    row_handler = RowHandler()
    fields_metadata = row_handler.get_fields_metadata_for_rows(
        [row], model.get_fields()
    )[row.id]
    cache = {}
    serialized_values = {
        f["name"]: f["type"].get_export_serialized_value(
            row, f["name"], cache=cache, files_zip=None, storage=None
        )
        for f in model.get_field_objects()
        if not f["type"].read_only
    }
    return serialized_values, fields_metadata


def check_permissions_with_view_fallback(
    table_operation: OperationType,
    view_operation: OperationType,
    user: AbstractUser,
    table: "Table",
    view: Optional["View"],
    row_ids: Optional[List[int]] = None,
):
    """
    Checks if the user has permission to the provided table object. If not, it will
    fall back to the view permissions, if the view ownership type allows it, then
    check if the user has permissions to the view.

    :param table_operation: The permission on table level to check. If this check
        passes, then no exception will be raised.
    :param view_operation: The permission on view level to check. If both this check
        succeeds and the view ownership type allows it, then no exception will be
        raised.
    :param user: The user on whose behalf the permissions are checked.
    :param table: The table where to check the permissions for.
    :param view: Optionally provide the view where to check permissions for as
        fallback.
    :param row_ids: Optionally the row ids that are modified.
    :raises PermissionDenied: If the user does not have access to both the table
        and view.
    """

    from baserow.contrib.database.views.registries import view_ownership_type_registry

    table_check = PermissionCheck(
        user,
        table_operation,
        context=table,
    )
    view_check = PermissionCheck(
        user,
        view_operation,
        context=view,
    )

    checks = [table_check]
    if view is not None:
        checks.append(view_check)

    # Check multiple permissions regardless because if a view is provided, we don't
    # want to execute multiple queries in order to check if the permission check
    # should fall back on the view.
    check_results = CoreHandler().check_multiple_permissions(
        checks,
        workspace=table.database.workspace,
        return_permissions_exceptions=True,
    )

    if check_results[table_check] is True:
        return

    if (
        view is not None
        # Because the user wants to access rows in a specific table, we must make
        # sure that the provided view belongs to that table. Otherwise, it would
        # result in a security bug.
        and view.table_id == table.id
        # The view ownership type should also allow accessing rows directly in
        # the view. The rows are provided because some additional permission
        # checks might need to be done in order to make sure that the user is
        # allowed to access the provided rows.
        and view_ownership_type_registry.get(view.ownership_type).can_modify_rows(
            view,
            row_ids,
        )
        and check_results[view_check] is True
    ):
        return

    if isinstance(check_results[table_check], PermissionException):
        raise check_results[table_check]

    if view is not None and isinstance(check_results[view_check], PermissionException):
        raise check_results[view_check]

    raise PermissionDenied(actor=user)
