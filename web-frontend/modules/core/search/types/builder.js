import { BaseSearchType } from './base'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'

export class BuilderSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'builder'
    this.name = 'Builder'
    this.icon = new BuilderApplicationType().getIconClass()
    this.priority = 2
  }

  buildUrl(result, context = null) {
    if (!result.metadata || !result.metadata.builder_id) {
      return null
    }

    return `/builder/${result.metadata.builder_id}`
  }
}
