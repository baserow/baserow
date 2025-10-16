import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class BuilderSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'builder'
    this.name = 'Builder'
    this.icon = 'baserow-icon-application'
    this.priority = 2
  }

  buildUrl(result, context = null) {
    if (!context || !context.store) {
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
      return `/builder/${application.id}/page/${pages[0].id}`
    }
    return null
  }
}
