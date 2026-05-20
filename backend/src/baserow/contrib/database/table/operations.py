from abc import ABC

from baserow.contrib.database.operations import DatabaseOperationType


class DatabaseTableOperationType(DatabaseOperationType, ABC):
    context_scope_name = "database_table"


class ReadDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.read"


class UpdateDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.update"


class UpdateDatabaseTableLockOperationType(DatabaseTableOperationType):
    type = "database.table.update_lock"


class DuplicateDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.duplicate"


class DeleteDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.delete"


class ListenToAllDatabaseTableEventsOperationType(DatabaseTableOperationType):
    type = "database.table.listen_to_all"


class RestoreDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.restore"


class ListRowsDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.list_rows"


class ListRowNamesDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.list_row_names"


class CreateRowDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.create_row"


class ImportRowsDatabaseTableOperationType(DatabaseTableOperationType):
    type = "database.table.import_rows"
