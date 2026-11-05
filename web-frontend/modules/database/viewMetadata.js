import { Registerable } from '@baserow/modules/core/registry'

export const DATABASE_VIEW_METADATA = {
  grid: {
    type: 'grid',
    iconClass: 'iconoir-menu',
    colorClass: 'color-primary',
    name: 'viewType.grid',
  },
  gallery: {
    type: 'gallery',
    iconClass: 'baserow-icon-gallery',
    colorClass: 'color-error',
    name: 'viewType.gallery',
  },
  form: {
    type: 'form',
    iconClass: 'baserow-icon-form',
    colorClass: 'color-warning',
    name: 'viewType.form',
  },
}

/** Names and icons used by recent items before any Database UI is loaded. */
export function registerViewMetadata(app, definitions) {
  for (const definition of Object.values(definitions)) {
    class ViewMetadata extends Registerable {
      static getType() {
        return definition.type
      }
      getName() {
        return this.app.$i18n.t(definition.name)
      }
      getIconClass() {
        return definition.iconClass
      }
      getColorClass() {
        return definition.colorClass
      }
    }
    const metadata = new ViewMetadata({ app })
    metadata.iconClass = definition.iconClass
    metadata.colorClass = definition.colorClass
    app.$registry.register('view', metadata)
  }
}
