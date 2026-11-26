import { Registerable } from '@baserow/modules/core/registry'

/**
 * A kind of place outside the Agent's page where people talk to it, under the
 * name of the backend's channel type. Tells members how to add and set it up.
 */
export class AgentChannelType extends Registerable {
  /** @returns {string} The name of the type. */
  get name() {
    throw new Error('The name of an Agent channel type must be set.')
  }

  /** @returns {string} What a channel of the type is, in one line. */
  get description() {
    return ''
  }

  /** @returns {string} The icon class of the type. */
  get icon() {
    throw new Error('The icon of an Agent channel type must be set.')
  }

  /**
   * The settings of one channel of the type. It takes `channel`, `agentName`
   * and `canEdit`, the props of `getFormProps`, and emits `update` with the
   * values to save.
   *
   * @returns {object} A component.
   */
  get formComponent() {
    throw new Error('The form of an Agent channel type must be set.')
  }

  /**
   * @param {object} context What the channel list offers the form.
   * @param {Function} context.savePassword Saves the channel's password and
   *   rejects when that fails.
   * @returns {object} The props the form takes beyond the common ones.
   */
  getFormProps(context) {
    return {}
  }

  /** @returns {object} The values a new channel of the type is created with. */
  getDefaultValues() {
    return {}
  }

  /**
   * @param {object} channel A channel of the type.
   * @returns {string} The name the channel shows.
   */
  getChannelName(channel) {
    return this.name
  }
}
