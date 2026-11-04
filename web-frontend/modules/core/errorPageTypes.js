import { Registerable } from '@baserow/modules/core/registry'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const DefaultErrorPage = lazyComponent(
  () => import('@baserow/modules/core/components/DefaultErrorPage')
)

/**
 * This type allow plugins to register a custom error page.
 */
export class ErrorPageType extends Registerable {
  getComponent() {
    return null
  }

  /**
   * Receive the `error` object. Should decide whether or not this specific error type
   * should be used.
   * @param {Error} error the raised error.
   * @returns `true` if the page should be displayed.
   */
  isApplicable(_error) {
    return false
  }

  /**
   * The order in which the error page type is tested. The higher the first.
   */
  getOrder() {
    return 0
  }
}

export class DefaultErrorPageType extends ErrorPageType {
  getComponent() {
    return DefaultErrorPage
  }

  isApplicable() {
    return true
  }

  static getType() {
    return 'default'
  }

  getOrder() {
    // Should be the last error page
    return 0
  }
}
