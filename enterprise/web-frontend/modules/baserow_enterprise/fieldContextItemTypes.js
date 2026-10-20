import { Registerable } from '@baserow/modules/core/registry'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const FieldPermissionsContextItem = lazyComponent(
  () =>
    import('@baserow_enterprise/components/fieldPermissions/FieldPermissionsContextItem')
)

export class FieldPermissionsContextItemType extends Registerable {
  static getType() {
    return 'field-permissions'
  }

  getComponent() {
    return FieldPermissionsContextItem
  }
}
