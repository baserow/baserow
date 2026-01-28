import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class BuilderSearchType extends BaseSearchType {
  constructor(context = {}) {
    super(context)
    this.type = 'builder'
    this.name = 'Builder'
    this.icon = 'baserow-icon-application'
    this.priority = 2
  }

  _getApplicationWithPages(result, context) {
    const appId = this._getApplicationId(result)
    if (!appId) {
      return null
    }
    const application = this.app.$store.getters['application/get'](appId)
    if (!application) {
      return null
    }
    const pages = this.app.$store.getters['page/getVisiblePages'](application)
    if (pages && pages.length > 0) {
      return { application, pages }
    }
    return null
  }

  buildUrl(result, context = null) {
    const data = this._getApplicationWithPages(result, context)
    if (!data) {
      return null
    }
    return {
      name: 'builder-page',
      params: { builderId: data.application.id, pageId: data.pages[0].id },
    }
  }

  isNavigable(result, context = null) {
    return this._getApplicationWithPages(result, context) !== null
  }
}
