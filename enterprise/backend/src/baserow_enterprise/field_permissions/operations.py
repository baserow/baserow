from baserow.contrib.database.fields.operations import FieldOperationType


class AssignFieldPermissionsOperationType(FieldOperationType):
    type = "database.table.field.assign_permissions"


class ReadFieldPermissionsOperationType(FieldOperationType):
    type = "database.table.field.read_permissions"
