import { Registerable } from '@baserow/modules/core/registry'
import DateDependencyMenuItem from '@baserow_enterprise/components/dateDependency/DateDependencyMenuItem.vue'

export class DateDepencencyContextItemType extends Registerable {
  static getType() {
    return 'date-dependency'
  }

  getComponent() {
    return DateDependencyMenuItem
  }
}
