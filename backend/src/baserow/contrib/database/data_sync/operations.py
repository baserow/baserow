from baserow.contrib.database.table.operations import DatabaseTableOperationType


class SyncTableOperationType(DatabaseTableOperationType):
    type = "database.data_sync.sync_table"


class ListPropertiesOperationType(DatabaseTableOperationType):
    type = "database.data_sync.list_properties"


# If a user has permissions to this operation, then it will expose the saved properties,
# which include data like PostgreSQL hosts, API tokens, etc. Only fields that are in
# `public_fields` will be exposed.
class GetIncludingPublicValuesOperationType(DatabaseTableOperationType):
    type = "database.data_sync.get"
