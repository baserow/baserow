import { Registerable } from '@baserow/modules/core/registry'
import FieldPermissionsContextItem from '@baserow_enterprise/components/fieldPermissions/FieldPermissionsContextItem'

export class FieldPermissionsContextItemType extends Registerable {
  static getType() {
    return 'field-permissions'
  }

  getComponent() {
    return FieldPermissionsContextItem
  }
}
