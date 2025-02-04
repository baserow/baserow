import { Registerable } from '@baserow/modules/core/registry'

export class QueryParamType extends Registerable {
  get name() {
    return null
  }

  get icon() {
    return null
  }
}

export class TextQueryParamType extends QueryParamType {
  static getType() {
    return 'text'
  }

  getOrder() {
    return 10
  }

  get name() {
    return this.app.i18n.t('queryParamTypes.textName')
  }

  get icon() {
    return 'font'
  }
}

export class NumericQueryParamType extends QueryParamType {
  static getType() {
    return 'numeric'
  }

  getOrder() {
    return 20
  }

  get name() {
    return this.app.i18n.t('queryParamTypes.numericName')
  }

  get icon() {
    return 'hashtag'
  }
}
