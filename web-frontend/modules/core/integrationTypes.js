import _ from 'lodash'
import { Registerable } from '@baserow/modules/core/registry'

export class IntegrationType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The image associated to this integration.
   */
  get image() {
    return null
  }

  /**
   * The icon associated with this integration.
   */
  get iconClass() {
    return null
  }

  /**
   * The color family applied to this integration's service icons.
   */
  get iconColor() {
    return null
  }

  /**
   * Return a summary describing the integration in one sentence.
   *
   * @param {object} integration The integration we want the summary for.
   * @returns A string description.
   */
  getSummary(integration) {
    return this.name
  }

  /**
   * Return a sentence that tells what a workspace integration acts as in every
   * application of the workspace, when the type has such an identity, or null.
   * It's shown wherever a workspace integration is listed or picked.
   *
   * @param {object} integration The workspace integration.
   * @returns {string|null} The hint, if any.
   */
  getWorkspaceHint(integration) {
    return null
  }

  /**
   * Return a sentence that tells what the integration will act as once it's made
   * available to the whole workspace, when the type has such an identity, or
   * null. It's shown before an app-level integration is promoted, so the admin
   * knows what every application of the workspace will use.
   *
   * @param {object} integration The app-level integration to promote.
   * @returns {string|null} The hint, if any.
   */
  getPromotionHint(integration) {
    return null
  }

  /**
   * Returns why this integration can't be used as it is, or null when it's
   * valid. Services, applications and settings built on top of an integration
   * use this to show the user where a misconfiguration comes from.
   *
   * @param {object} integration The integration to validate.
   * @returns {string|null} The error message, if any.
   */
  getErrorMessage(integration) {
    return null
  }

  /**
   * Override `getErrorMessage` instead of this method so an invalid
   * integration also provides a user-facing explanation.
   *
   * @param {object} integration The integration to validate.
   * @returns {boolean} If the integration is in error.
   */
  isInError(integration) {
    return Boolean(this.getErrorMessage(integration))
  }

  /**
   * The form to edit this integration.
   */
  get formComponent() {
    return null
  }

  /**
   * An optional warning to display when editing this integration
   */
  get warning() {
    return ''
  }

  /**
   * Whether the integration's form creates the integration itself, e.g. once
   * the person signed in with another service, instead of the create button
   * of the modal around it. Such a form emits `created` with the integration.
   */
  get createsItself() {
    return false
  }

  /**
   * Default values on integration creation.
   *
   * @returns an object with the default values.
   */
  getDefaultValues() {
    return {}
  }

  /**
   * Returns the form values that changed since the integration was opened.
   */
  getUpdatedValues(values, initialValues) {
    return Object.fromEntries(
      Object.entries(values).filter(
        ([key, value]) => !_.isEqual(value, initialValues[key])
      )
    )
  }

  getOrder() {
    return 0
  }
}
