from baserow.contrib.database.fields.operations import FieldOperationType


class UpdateFieldPermissionsOperationType(FieldOperationType):
    type = "database.table.field.update_permissions"


class ReadFieldPermissionsOperationType(FieldOperationType):
    type = "database.table.field.read_permissions"
