<template>
  <div>
    <FormGroup
      small-label
      :label="$t('agentChannels.botTokenLabel')"
      class="margin-bottom-2"
    >
      <FormInput
        v-model="draft.botToken"
        type="password"
        :disabled="!canUpdate"
        :loading="savingSecrets.includes('bot_token')"
        :placeholder="secretPlaceholder('bot_token_set', 'botToken')"
        @blur="saveSecret('bot_token', 'botToken')"
      ></FormInput>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('agentChannels.signingSecretLabel')"
      class="margin-bottom-2"
    >
      <FormInput
        v-model="draft.signingSecret"
        type="password"
        :disabled="!canUpdate"
        :loading="savingSecrets.includes('signing_secret')"
        :placeholder="secretPlaceholder('signing_secret_set', 'signingSecret')"
        @blur="saveSecret('signing_secret', 'signingSecret')"
      ></FormInput>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('agentChannels.eventsUrlLabel')"
      :helper-text="$t('agentChannels.eventsUrlHelp')"
      class="margin-bottom-2"
    >
      <div class="agent-configuration__channel-url">
        <div class="agent-configuration__channel-url-box">
          {{ channel.events_url }}
        </div>
        <a
          class="agent-configuration__channel-url-copy"
          :title="$t('agentChannels.copyUrl')"
          @click="copyText(channel.events_url)"
        >
          <i class="iconoir-copy"></i>
          <Copied ref="copied"></Copied>
        </a>
      </div>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('agentChannels.manifestLabel')"
      :helper-text="$t('agentChannels.manifestHelp')"
      class="margin-bottom-2"
    >
      <Button
        type="secondary"
        icon="iconoir-download"
        @click="downloadManifest"
      >
        {{ $t('agentChannels.downloadManifest') }}
      </Button>
    </FormGroup>
    <div class="agent-configuration__hint">
      {{ $t('agentChannels.activeHint') }}
    </div>
    <AgentSlackSetupSteps created />
  </div>
</template>

<script>
import agentChannelCard from '@baserow_enterprise/mixins/agentChannelCard'
import AgentSlackSetupSteps from '@baserow_enterprise/components/agentApplication/AgentSlackSetupSteps'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { downloadJson } from '@baserow_enterprise/utils/download'

export default {
  name: 'AgentSlackChannelCard',
  components: { AgentSlackSetupSteps },
  mixins: [agentChannelCard],
  data() {
    return { savingSecrets: [] }
  },
  methods: {
    secretPlaceholder(setKey, draftKey) {
      // An empty input keeps the stored secret, so show that one is saved.
      if (this.channel.config?.[setKey]) {
        return this.$t('agentChannels.secretSavedPlaceholder')
      }
      return draftKey === 'botToken'
        ? this.$t('agentChannels.botTokenPlaceholder')
        : this.$t('agentChannels.signingSecretPlaceholder')
    },
    async saveSecret(configKey, draftKey) {
      const value = this.draft[draftKey]?.trim()
      if (!this.canUpdate || !value || this.savingSecrets.includes(configKey)) {
        return
      }
      this.savingSecrets = [...this.savingSecrets, configKey]
      try {
        await this.updateChannel({ config: { [configKey]: value } })
        // The response only reports that the secret is set.
        this.draft[draftKey] = ''
      } finally {
        this.savingSecrets = this.savingSecrets.filter((k) => k !== configKey)
      }
    },
    downloadManifest() {
      const name = (this.channel.name || this.application.name || 'slack-app')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
      downloadJson(this.channel.manifest, `${name}-slack-manifest.json`)
    },
    copyText(text) {
      copyToClipboard(text)
      this.$refs.copied?.show()
    },
  },
}
</script>
