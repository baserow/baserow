import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class BuilderSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'builder'
    this.name = 'Builder'
    this.icon = 'baserow-icon-application'
    this.priority = 2
  }

  _getApplicationWithPages(result, context) {
    if (!context?.store) {
      return null
    }
    const application = context.store.getters['application/get'](
      parseInt(result.id)
    )
    if (!application) {
      return null
    }
    const pages = context.store.getters['page/getVisiblePages'](application)
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
    return `/builder/${data.application.id}/page/${data.pages[0].id}`
  }

  isNavigable(result, context = null) {
    return this._getApplicationWithPages(result, context) !== null
  }

  focusInSidebar(result, context = null) {
    if (!context?.store) {
      return false
    }
    const application = context.store.getters['application/get'](
      parseInt(result.id)
    )
    if (application) {
      context.store.dispatch('application/select', application)
      return true
    }
    return false
  }
}
