<template>
  <div>
    <FormGroup
      small-label
      required
      :label="$t('agentChannels.mailboxIntegrationLabel')"
      :helper-text="$t('agentChannels.mailboxIntegrationHelp')"
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        :model-value="channel.config.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="channelType.integrationType"
        :allow-editing="canUpdate"
        :disabled="!canUpdate"
        @update:model-value="
          updateChannel({ config: { integration_id: $event } })
        "
      />
      <Alert
        v-if="integration && !integration.has_refresh_token"
        type="warning"
      >
        <p>{{ $t('agentChannels.mailboxNotConnected') }}</p>
      </Alert>
    </FormGroup>
    <FormGroup
      v-if="channel.type === 'gmail'"
      small-label
      :label="$t('agentChannels.gmailLabelLabel')"
      :helper-text="$t('agentChannels.gmailLabelHelp')"
      class="margin-bottom-2"
    >
      <FormInput
        v-model="draft.label"
        :disabled="!canUpdate"
        :placeholder="$t('agentChannels.gmailLabelPlaceholder')"
        @input="onConfigChanged"
      ></FormInput>
    </FormGroup>
    <FormGroup
      v-else
      small-label
      :label="$t('agentChannels.outlookFolderLabel')"
      :helper-text="$t('agentChannels.outlookFolderHelp')"
      class="margin-bottom-2"
    >
      <FormInput
        v-model="draft.folder"
        :disabled="!canUpdate"
        placeholder="inbox"
        @input="onConfigChanged"
      ></FormInput>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('agentChannels.aliasLabel')"
      :helper-text="$t('agentChannels.aliasHelp')"
      class="margin-bottom-2"
    >
      <FormInput
        v-model="draft.alias"
        :disabled="!canUpdate"
        placeholder="support@company.com"
        @input="onConfigChanged"
      ></FormInput>
    </FormGroup>
    <AgentEmailSharedFields
      :channel="channel"
      :can-update="canUpdate"
      :allowed-sender-domains="draft.allowedSenderDomains"
      @update:require-approval="
        updateChannel({ config: { require_approval: $event } })
      "
      @update:allowed-sender-domains="
        (value) => {
          draft.allowedSenderDomains = value
          onConfigChanged()
        }
      "
    />
    <div class="agent-configuration__hint">
      {{
        channel.config.polling
          ? $t('agentChannels.mailboxPollingHint')
          : $t('agentChannels.mailboxWaitingHint')
      }}
    </div>
  </div>
</template>

<script>
import agentChannelCard from '@baserow_enterprise/mixins/agentChannelCard'
import AgentEmailSharedFields from '@baserow_enterprise/components/agentApplication/channels/AgentEmailSharedFields'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'

export default {
  name: 'AgentMailboxChannelCard',
  components: { AgentEmailSharedFields, IntegrationDropdown },
  mixins: [agentChannelCard],
  computed: {
    channelType() {
      return this.$registry.get('agentChatChannel', this.channel.type)
    },
    integrations() {
      const type = this.channelType.integrationType.type
      return this.$store.getters['integration/getIntegrations'](
        this.application
      ).filter((integration) => integration.type === type)
    },
    integration() {
      return this.integrations.find(
        (integration) => integration.id === this.channel.config.integration_id
      )
    },
  },
  methods: {
    draftConfigValues() {
      const values = {
        alias: this.draft.alias.trim().toLowerCase(),
        allowed_sender_domains: this.draft.allowedSenderDomains
          .split(',')
          .map((domain) => domain.trim().toLowerCase())
          .filter(Boolean),
      }
      if (this.channel.type === 'gmail') {
        values.label = this.draft.label.trim()
      } else {
        values.folder = this.draft.folder.trim() || 'inbox'
      }
      return values
    },
  },
}
</script>
