from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.registries import TrashableItemType

from .exceptions import InvalidDashboardFilterValues
from .handler import DashboardFilterHandler
from .models import DashboardFilter
from .operations import RestoreDashboardFilterOperationType
from .signals import dashboard_filters_updated


class DashboardFilterTrashableItemType(TrashableItemType):
    type = "dashboard_filter"
    model_class = DashboardFilter

    def get_parent(self, trashed_item):
        return trashed_item.dashboard

    def get_name(self, trashed_item):
        return trashed_item.label

    def trash(self, item_to_trash, requesting_user, trash_entry):
        conditions = DashboardFilterHandler().remove_source_conditions(item_to_trash)
        trash_entry.additional_restoration_data["source_conditions"] = conditions
        trash_entry.save(update_fields=["additional_restoration_data"])
        super().trash(item_to_trash, requesting_user, trash_entry)

    def restore(self, trashed_item, trash_entry):
        DashboardHandler().get_dashboard_for_update(trashed_item.dashboard_id)
        try:
            DashboardFilterHandler().validate_values(
                trashed_item.dashboard, trashed_item.values, exclude_id=trashed_item.id
            )
        except InvalidDashboardFilterValues as exc:
            raise TrashItemRestorationDisallowed(str(exc)) from exc
        super().restore(trashed_item, trash_entry)
        DashboardFilterHandler().restore_source_conditions(
            trashed_item,
            trash_entry.additional_restoration_data.get("source_conditions", []),
        )
        dashboard_filters_updated.send(self, dashboard=trashed_item.dashboard)

    def get_restore_operation_type(self):
        return RestoreDashboardFilterOperationType.type

    def permanently_delete_item(self, trashed_item, trash_item_lookup_cache=None):
        DashboardFilterHandler().delete_filter(trashed_item)
