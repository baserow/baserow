import { defineAsyncComponent, hydrateOnIdle } from 'vue'

import { Registerable } from '@baserow/modules/core/registry'

const FieldPermissionsContextItem = defineAsyncComponent({
  loader: () =>
    import('@baserow_enterprise/components/fieldPermissions/FieldPermissionsContextItem'),
  hydrate: hydrateOnIdle(),
})

export class FieldPermissionsContextItemType extends Registerable {
  static getType() {
    return 'field-permissions'
  }

  getComponent() {
    return FieldPermissionsContextItem
  }
}
