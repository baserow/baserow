import { Registerable } from '@baserow/modules/core/registry'

export class UserSourceType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The integration type necessary to access this service.
   */
  get integrationType() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The image associated to this userSource .
   */
  get image() {
    throw new Error('Must be set on the type.')
  }

  /**
   * Returns a summary to be used in the user source list.
   * @param {Object} useSource the user source we want the summary for.
   * @returns
   */
  getSummary(userSource) {
    return ''
  }

  /**
   * Return the generated uid for this data source. Should reflect the backend
   * generation.
   */
  genUid(userSource) {
    throw new Error('Must be set on the type.')
  }

  /**
   * The form to edit this user source.
   */
  get formComponent() {
    return null
  }

  /**
   * Should return the login option to display the right auth form.
   */
  getLoginOptions(userSource) {
    throw new Error('Must be set on the type.')
  }

  getOrder() {
    return 0
  }
}
