from baserow.contrib.database.views.operations import ViewOperationType


class ListenToAllRestrictedViewEventsOperationType(ViewOperationType):
    type = "database.table.view.listen_to_all_restricted_view"
