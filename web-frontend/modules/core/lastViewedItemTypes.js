import { Registerable } from '@baserow/modules/core/registry'

/**
 * Separates the type from the sub type in a type filter value, like
 * `database_view:grid`. The backend understands the same notation.
 */
export const LAST_VIEWED_SUB_TYPE_SEPARATOR = ':'

/**
 * Frontend counterpart of the backend `LastViewedItemType` registry. An entry is one
 * result of the recently viewed listing and looks like
 * `{ type, sub_type, last_viewed, application, workspace, item }`, where `item`
 * holds what the backend type serializes for the leaf.
 */
export class LastViewedItemType extends Registerable {
  /**
   * A human readable label of the kind of item, like "Grid view" or "Page". The
   * entry is given because polymorphic types label their sub types differently.
   */
  getName(entry) {
    return null
  }

  /**
   * The classes of the `<i>` element that represents the item.
   */
  getIconClass(entry) {
    return null
  }

  /**
   * The color modifier of the box around the icon, see `ItemIcon`. Types that
   * color the icon itself through `getIconClass` return `null`.
   */
  getIconColor(entry) {
    return null
  }

  /**
   * The options this type contributes to the type filter dropdown. A polymorphic
   * type returns one option per sub type, with the value `type:sub_type`.
   */
  getFilterOptions() {
    return [
      {
        value: this.getType(),
        name: this.getName(),
        iconClass: this.getIconClass(),
      },
    ]
  }

  /**
   * The names of the parents shown next to the item, from the outer most one.
   * Most leaves only have the application as a parent.
   */
  getParentPath(entry) {
    return [entry.application.name]
  }

  /**
   * The route that opens the item.
   */
  getRoute(entry) {
    throw new Error('The route of a last viewed item type must be set.')
  }

  getOrder() {
    return 50
  }
}

/**
 * An item that borrows the icon and colour of the application type it belongs to,
 * which is every type whose items are not polymorphic.
 */
export class ApplicationLastViewedItemType extends LastViewedItemType {
  /**
   * The name of the application type this item lives in.
   */
  getApplicationTypeName() {
    throw new Error('The application type of a last viewed item must be set.')
  }

  getApplicationType() {
    return this.app.$registry.get('application', this.getApplicationTypeName())
  }

  getIconClass() {
    return this.getApplicationType().iconClass
  }

  getIconColor() {
    return this.getApplicationType().getIconColor()
  }
}
