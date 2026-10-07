import { Registerable } from '@baserow/modules/core/registry'
import slackImage from '@baserow/modules/integrations/slack/assets/images/slack.svg?url'
import AgentSlackChannelCard from '@baserow_enterprise/components/agentApplication/channels/AgentSlackChannelCard'
import AgentSlackChannelDraft from '@baserow_enterprise/components/agentApplication/channels/AgentSlackChannelDraft'
import AgentWebChannelCard from '@baserow_enterprise/components/agentApplication/channels/AgentWebChannelCard'
import AgentWebChannelDraft from '@baserow_enterprise/components/agentApplication/channels/AgentWebChannelDraft'
import AgentEmailChannelCard from '@baserow_enterprise/components/agentApplication/channels/AgentEmailChannelCard'
import AgentEmailChannelDraft from '@baserow_enterprise/components/agentApplication/channels/AgentEmailChannelDraft'
import AgentMailboxChannelCard from '@baserow_enterprise/components/agentApplication/channels/AgentMailboxChannelCard'
import AgentMailboxChannelDraft from '@baserow_enterprise/components/agentApplication/channels/AgentMailboxChannelDraft'

/**
 * A surface through which people talk to an agent (Slack, a public page, an
 * email address). The channels section renders every type through this
 * interface: the add menu entry, the card of a saved channel and the body
 * shown while one is being created.
 */
export class AgentChatChannelType extends Registerable {
  get name() {
    return this.app.$i18n.t(`agentChannels.${this.getType()}`)
  }

  get description() {
    return this.app.$i18n.t(`agentChannels.${this.getType()}Description`)
  }

  get icon() {
    return ''
  }

  get image() {
    return ''
  }

  get iconColor() {
    return 'muted-blue'
  }

  /**
   * The group of the add menu this type is listed under.
   */
  get group() {
    return {
      id: 'chat-apps',
      label: this.app.$i18n.t('agentChannels.chatAppsGroup'),
      icon: 'iconoir-chat-bubble',
      iconColor: 'muted-blue',
    }
  }

  /**
   * Whether the type can be added on this installation, e.g. the hosted
   * email address needs the inbound email receiver.
   */
  isAvailable() {
    return true
  }

  /**
   * Why `isAvailable` says no, shown in the add menu.
   */
  get unavailableReason() {
    return ''
  }

  /**
   * Renders the saved channel's settings. It receives `channel`,
   * `application`, `draft` (the editable local copy) and `canUpdate`.
   */
  get cardComponent() {
    return null
  }

  /**
   * Renders the body of the card while the channel is being created. It
   * receives the `draft` and may fill `draft.config`.
   */
  get draftComponent() {
    return null
  }

  /**
   * The local editable copy of a channel's settings. The section replaces
   * it with the server value until the user changes it.
   */
  seedDraft(channel) {
    return { name: channel.name || '' }
  }

  /**
   * Whether a draft holds what the backend needs to create the channel.
   */
  canCreate(draft) {
    return true
  }

  getOrder() {
    return 50
  }
}

export class WebAgentChatChannelType extends AgentChatChannelType {
  static getType() {
    return 'web'
  }

  get icon() {
    return 'iconoir-globe'
  }

  get cardComponent() {
    return AgentWebChannelCard
  }

  get draftComponent() {
    return AgentWebChannelDraft
  }

  seedDraft(channel) {
    return {
      ...super.seedDraft(channel),
      title: channel.config?.title || '',
      welcomeText: channel.config?.welcome_text || '',
    }
  }

  getOrder() {
    return 10
  }
}

export class WebsiteWidgetAgentChatChannelType extends WebAgentChatChannelType {
  static getType() {
    return 'website'
  }

  get icon() {
    return 'iconoir-code'
  }

  seedDraft(channel) {
    return {
      ...super.seedDraft(channel),
      buttonText: channel.config?.button_text || '',
      buttonColor: channel.config?.button_color || '#5190ef',
      buttonPosition: channel.config?.button_position || 'bottom-right',
    }
  }

  getOrder() {
    return 20
  }
}

export class SlackAgentChatChannelType extends AgentChatChannelType {
  static getType() {
    return 'slack'
  }

  get image() {
    return slackImage
  }

  get cardComponent() {
    return AgentSlackChannelCard
  }

  get draftComponent() {
    return AgentSlackChannelDraft
  }

  seedDraft(channel) {
    return { ...super.seedDraft(channel), botToken: '', signingSecret: '' }
  }

  getOrder() {
    return 30
  }
}

/**
 * What the three email channels share in the add menu.
 */
class EmailAgentChatChannelTypeBase extends AgentChatChannelType {
  get group() {
    return {
      id: 'email',
      label: this.app.$i18n.t('agentChannels.emailGroup'),
      icon: 'iconoir-mail',
      iconColor: 'muted-red',
    }
  }

  get iconColor() {
    return 'muted-red'
  }

  seedDraft(channel) {
    return {
      ...super.seedDraft(channel),
      allowedSenderDomains: (channel.config?.allowed_sender_domains || []).join(
        ', '
      ),
    }
  }
}

export class EmailAgentChatChannelType extends EmailAgentChatChannelTypeBase {
  static getType() {
    return 'email'
  }

  get icon() {
    return 'iconoir-mail'
  }

  isAvailable() {
    return (
      this.app.$store.getters['settings/get']?.inbound_email_enabled === true
    )
  }

  canCreate() {
    return this.isAvailable()
  }

  get unavailableReason() {
    return this.app.$i18n.t('agentChannels.emailUnavailable')
  }

  get cardComponent() {
    return AgentEmailChannelCard
  }

  get draftComponent() {
    return AgentEmailChannelDraft
  }

  seedDraft(channel) {
    return {
      ...super.seedDraft(channel),
      localpart: channel.config?.localpart || '',
      fromName: channel.config?.from_name || '',
      fromEmail: channel.config?.from_email || '',
    }
  }

  getOrder() {
    return 40
  }
}

class MailboxAgentChatChannelType extends EmailAgentChatChannelTypeBase {
  /**
   * The integration type whose connected account is the mailbox.
   */
  get integrationType() {
    throw new Error('Must be set on the type.')
  }

  get cardComponent() {
    return AgentMailboxChannelCard
  }

  get draftComponent() {
    return AgentMailboxChannelDraft
  }

  seedDraft(channel) {
    return {
      ...super.seedDraft(channel),
      alias: channel.config?.alias || '',
    }
  }

  canCreate(draft) {
    return Boolean(draft.config?.integration_id)
  }
}

export class GmailAgentChatChannelType extends MailboxAgentChatChannelType {
  static getType() {
    return 'gmail'
  }

  get icon() {
    return 'iconoir-google'
  }

  get integrationType() {
    return this.app.$registry.get('integration', 'google')
  }

  seedDraft(channel) {
    return { ...super.seedDraft(channel), label: channel.config?.label || '' }
  }

  getOrder() {
    return 41
  }
}

export class OutlookAgentChatChannelType extends MailboxAgentChatChannelType {
  static getType() {
    return 'outlook'
  }

  get icon() {
    return 'iconoir-windows'
  }

  get integrationType() {
    return this.app.$registry.get('integration', 'microsoft')
  }

  seedDraft(channel) {
    return {
      ...super.seedDraft(channel),
      folder: channel.config?.folder || 'inbox',
    }
  }

  getOrder() {
    return 42
  }
}
