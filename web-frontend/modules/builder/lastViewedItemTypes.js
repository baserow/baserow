import { ApplicationLastViewedItemType } from '@baserow/modules/core/lastViewedItemTypes'

export class BuilderPageLastViewedItemType extends ApplicationLastViewedItemType {
  static getType() {
    return 'builder_page'
  }

  getOrder() {
    return 70
  }

  getApplicationTypeName() {
    return 'builder'
  }

  getName() {
    return this.app.$i18n.t('lastViewedItemType.builderPage')
  }

  getRoute(entry) {
    return {
      name: 'builder-page',
      params: { builderId: entry.application.id, pageId: entry.item.id },
    }
  }
}
