from baserow.contrib.database.table.operations import DatabaseTableOperationType


class ReadFieldRuleOperationType(DatabaseTableOperationType):
    type = "database.table.field_rules.read_field_rules"


class SetFieldRuleOperationType(DatabaseTableOperationType):
    type = "database.table.field_rules.set_field_rules"
