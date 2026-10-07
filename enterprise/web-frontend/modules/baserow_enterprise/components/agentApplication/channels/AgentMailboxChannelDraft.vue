<template>
  <div>
    <div class="agent-configuration__hint margin-bottom-2">
      {{ $t(`agentChannels.${draft.type}CreateHint`) }}
    </div>
    <FormGroup
      small-label
      required
      :label="$t('agentChannels.mailboxIntegrationLabel')"
      :helper-text="$t('agentChannels.mailboxIntegrationHelp')"
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="draft.config.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="channelType.integrationType"
        :allow-editing="true"
      />
    </FormGroup>
  </div>
</template>

<script>
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'

export default {
  name: 'AgentMailboxChannelDraft',
  components: { IntegrationDropdown },
  props: {
    draft: {
      type: Object,
      required: true,
    },
    application: {
      type: Object,
      required: true,
    },
  },
  computed: {
    channelType() {
      return this.$registry.get('agentChatChannel', this.draft.type)
    },
    integrations() {
      const type = this.channelType.integrationType.type
      return this.$store.getters['integration/getIntegrations'](
        this.application
      ).filter((integration) => integration.type === type)
    },
  },
}
</script>
