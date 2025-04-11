import { Registerable } from '@baserow/modules/core/registry'
import FieldPermissionMenuItem from '@baserow_enterprise/components/field-permissions/FieldPermissionMenuItem'

export class FieldPermissionMenuItemType extends Registerable {
  static getType() {
    return 'field-permission'
  }

  getComponent() {
    return FieldPermissionMenuItem
  }
}
