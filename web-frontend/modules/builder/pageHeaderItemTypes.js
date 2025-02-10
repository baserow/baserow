import { Registerable } from '@baserow/modules/core/registry'
import ElementsContext from '@baserow/modules/builder/components/page/header/ElementsContext'
import DataSourceContext from '@baserow/modules/builder/components/page/header/DataSourceContext'
import VariablesContext from '@baserow/modules/builder/components/page/header/VariablesContext'
import PageSettingsModal from '@baserow/modules/builder/components/page/settings/PageSettingsModal'

export class PageHeaderItemType extends Registerable {
  get label() {
    return null
  }

  get icon() {
    return null
  }

  /**
   * This is the component that will be opened when the icon is clicked. Usually this
   * is either a context or a modal.
   */
  get component() {
    return null
  }

  /**
   * Returns whether the component which this page header is responsible for
   * contains invalid properties. This is to add a visual indicator icon to
   * name so the user can see that something is wrong.
   * @returns {boolean} - If the page header is valid.
   */
  isInError({ builder, page }) {
    return false
  }

  /**
   * By default, we will assume that the component is a context menu and will be
   * positioned next to the icon clicked on.
   */
  onClick(component, button) {
    component.toggle(button, 'bottom', 'left', 4)
  }

  getOrder() {
    return 0
  }
}

export class ElementsPageHeaderItemType extends PageHeaderItemType {
  static getType() {
    return 'elements'
  }

  get label() {
    return this.app.i18n.t('pageHeaderItemTypes.labelElements')
  }

  get icon() {
    return 'iconoir-selection'
  }

  get component() {
    return ElementsContext
  }

  getOrder() {
    return 10
  }
}

export class DataSourcesPageHeaderItemType extends PageHeaderItemType {
  static getType() {
    return 'data_sources'
  }

  get label() {
    return this.app.i18n.t('pageHeaderItemTypes.labelDataSource')
  }

  get icon() {
    return 'iconoir-table'
  }

  get component() {
    return DataSourceContext
  }

  /**
   * Determines if any of the data sources associated with this page are in error.
   * We will use this to add an error indicator icon next to the Data label.
   * @returns {boolean} - If the data sources header is in error.
   */
  isInError({ builder, page }) {
    const pages = [page, this.app.store.getters['page/getSharedPage'](builder)]
    const dataSources = this.app.store.getters[
      'dataSource/getPagesDataSources'
    ](pages).filter((dataSource) => dataSource.type)
    return dataSources.some((dataSource) => {
      const serviceType = this.app.$registry.get('service', dataSource.type)
      return serviceType.isInError({ service: dataSource })
    })
  }

  getOrder() {
    return 20
  }
}

export class VariablesPageHeaderItemType extends PageHeaderItemType {
  static getType() {
    return 'variables'
  }

  get label() {
    return this.app.i18n.t('pageHeaderItemTypes.labelVariables')
  }

  get icon() {
    return 'baserow-icon-formula'
  }

  get component() {
    return VariablesContext
  }

  getOrder() {
    return 30
  }
}

export class SettingsPageHeaderItemType extends PageHeaderItemType {
  static getType() {
    return 'settings'
  }

  get label() {
    return this.app.i18n.t('pageHeaderItemTypes.labelSettings')
  }

  get icon() {
    return 'iconoir-settings'
  }

  get component() {
    return PageSettingsModal
  }

  onClick(component, button) {
    component.show()
  }

  getOrder() {
    return 40
  }
}
