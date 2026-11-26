import { markRaw } from 'vue'
import { AgentChannelType } from '@baserow/modules/agent/agentChannelTypes'
import AgentPublicChatForm from '@baserow_enterprise/components/agent/AgentPublicChatForm'
import AgentWebsiteWidgetForm from '@baserow_enterprise/components/agent/AgentWebsiteWidgetForm'

const PublicChatForm = markRaw(AgentPublicChatForm)
const WebsiteWidgetForm = markRaw(AgentWebsiteWidgetForm)

export class PublicChatAgentChannelType extends AgentChannelType {
  static getType() {
    return 'public_chat'
  }

  get name() {
    return this.app.$i18n.t('agentChannels.publicChat')
  }

  get description() {
    return this.app.$i18n.t('agentChannels.publicChatDescription')
  }

  get icon() {
    return 'iconoir-multi-bubble'
  }

  get formComponent() {
    return PublicChatForm
  }

  getFormProps({ savePassword }) {
    return { savePassword }
  }

  getChannelName(channel) {
    return channel.title || this.name
  }

  getOrder() {
    return 10
  }
}

export class WebsiteWidgetAgentChannelType extends PublicChatAgentChannelType {
  static getType() {
    return 'website_widget'
  }

  get name() {
    return this.app.$i18n.t('agentChannels.websiteWidget')
  }

  get description() {
    return this.app.$i18n.t('agentChannels.websiteWidgetDescription')
  }

  get icon() {
    return 'iconoir-code-brackets'
  }

  get formComponent() {
    return WebsiteWidgetForm
  }

  getFormProps() {
    return {}
  }

  /**
   * @param {object} channel A website widget.
   * @returns {string} The script tag a website adds to show the widget.
   */
  getEmbedCode(channel) {
    const src = `${this.app.$config.public.publicBackendUrl}/api/agent/public-chat/${channel.slug}/widget.js`
    return `<script src="${src}" async></script>`
  }

  getOrder() {
    return 20
  }
}
