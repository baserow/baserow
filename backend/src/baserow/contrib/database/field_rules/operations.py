from baserow.contrib.database.table.operations import DatabaseTableOperationType


class SetFieldRuleOperationType(DatabaseTableOperationType):
    type = "database.table.field_rules.set_field_rules"
