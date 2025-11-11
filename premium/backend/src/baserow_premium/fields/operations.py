from baserow.contrib.database.table.operations import DatabaseTableOperationType


class GenerateAIValuesOperationType(DatabaseTableOperationType):
    type = "database.table.generate_ai_values"
    object_scope_name = "database_field"
