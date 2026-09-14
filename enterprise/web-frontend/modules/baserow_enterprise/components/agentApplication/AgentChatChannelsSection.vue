<template>
  <div>
    <div class="agent-configuration__subsection">
      <div class="agent-configuration__subsection-title">
        {{ $t('agentChannels.channels') }}
      </div>
      <ButtonText
        v-if="canUpdateChannel"
        icon="iconoir-plus"
        @click="
          $refs.addChannelContext.toggle(
            $event.currentTarget,
            'bottom',
            'right',
            4
          )
        "
      >
        {{ $t('agentChannels.addChannel') }}
      </ButtonText>
    </div>
    <div class="agent-configuration__intro">
      {{ $t('agentChannels.intro', { name: agentName }) }}
    </div>
    <div
      v-if="channels.length === 0 && draft === null"
      class="agent-configuration__placeholder"
    >
      {{ $t('agentChannels.empty') }}
    </div>
    <div
      v-if="channels.length > 0 || draft !== null"
      class="agent-configuration__card-list"
    >
      <AgentConfigurationCard
        v-for="channel in channels"
        :key="channel.id"
        :title="channelTitle(channel)"
        :image="channelTypeImage(channel)"
      >
        <template #header-right>
          <SwitchInput
            small
            :value="channel.enabled"
            :disabled="!canUpdateChannel"
            :title="$t('agentChannels.enabledLabel')"
            @input="onEnabledChange(channel, $event)"
          ></SwitchInput>
        </template>
        <template v-if="channelDrafts[channel.id]">
          <ReadOnlyForm :read-only="!canUpdateChannel">
            <FormGroup
              small-label
              :label="$t('agentChannels.nameLabel')"
              class="margin-bottom-2"
            >
              <FormInput
                v-model="channelDrafts[channel.id].name"
                :disabled="!canUpdateChannel"
                :placeholder="$t('agentChannels.namePlaceholder')"
                @input="onNameChanged(channel)"
              ></FormInput>
            </FormGroup>
            <FormGroup
              small-label
              :label="$t('agentChannels.botTokenLabel')"
              class="margin-bottom-2"
            >
              <FormInput
                v-model="channelDrafts[channel.id].botToken"
                type="password"
                :disabled="!canUpdateChannel"
                :loading="savingSecrets.includes(`${channel.id}-bot_token`)"
                :placeholder="
                  secretPlaceholder(channel, 'bot_token_set', 'botToken')
                "
                @blur="saveSecret(channel, 'bot_token', 'botToken')"
              ></FormInput>
            </FormGroup>
            <FormGroup
              small-label
              :label="$t('agentChannels.signingSecretLabel')"
              class="margin-bottom-2"
            >
              <FormInput
                v-model="channelDrafts[channel.id].signingSecret"
                type="password"
                :disabled="!canUpdateChannel"
                :loading="
                  savingSecrets.includes(`${channel.id}-signing_secret`)
                "
                :placeholder="
                  secretPlaceholder(
                    channel,
                    'signing_secret_set',
                    'signingSecret'
                  )
                "
                @blur="saveSecret(channel, 'signing_secret', 'signingSecret')"
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
                  @click="copyEventsUrl(channel)"
                >
                  <i class="iconoir-copy"></i>
                  <Copied :ref="`copied-${channel.id}`"></Copied>
                </a>
              </div>
            </FormGroup>
            <div class="agent-configuration__hint">
              {{ $t('agentChannels.activeHint') }}
            </div>
          </ReadOnlyForm>
        </template>
        <template v-if="canUpdateChannel" #footer>
          <ButtonText
            icon="iconoir-bin"
            :loading="deletingIds.includes(channel.id)"
            @click="deleteChannel(channel)"
          >
            {{ $t('agentChannels.delete') }}
          </ButtonText>
        </template>
      </AgentConfigurationCard>
      <AgentConfigurationCard
        v-if="draft !== null"
        :title="draft.name || $t('agentChannels.slack')"
        :image="channelTypeImage(draft)"
      >
        <FormGroup
          small-label
          :label="$t('agentChannels.nameLabel')"
          class="margin-bottom-2"
        >
          <FormInput
            v-model="draft.name"
            :placeholder="$t('agentChannels.namePlaceholder')"
          ></FormInput>
        </FormGroup>
        <FormGroup
          small-label
          :label="$t('agentChannels.botTokenLabel')"
          class="margin-bottom-2"
        >
          <FormInput
            v-model="draft.botToken"
            type="password"
            :placeholder="$t('agentChannels.botTokenPlaceholder')"
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
            :placeholder="$t('agentChannels.signingSecretPlaceholder')"
          ></FormInput>
        </FormGroup>
        <div class="agent-configuration__channel-draft-actions">
          <Button
            type="primary"
            :loading="createLoading"
            :disabled="
              draft.botToken.trim() === '' || draft.signingSecret.trim() === ''
            "
            @click="createChannel"
          >
            {{ $t('agentChannels.create') }}
          </Button>
          <Button type="secondary" @click="draft = null">
            {{ $t('agentChannels.cancel') }}
          </Button>
        </div>
      </AgentConfigurationCard>
    </div>
    <template v-if="canUpdateChannel">
      <Context
        ref="addChannelContext"
        max-height-if-outside-viewport
        @shown="$refs.addChannelMenu.focus()"
      >
        <AgentGroupedAddMenu
          ref="addChannelMenu"
          :items="channelMenuItems"
          :search-placeholder="$t('agentChannels.searchPlaceholder')"
          :empty-text="$t('agentChannels.noResults')"
          @select="onAddChannelSelect($event)"
          @close="$refs.addChannelContext.hide()"
        />
      </Context>
    </template>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AgentGroupedAddMenu from '@baserow_enterprise/components/agentApplication/AgentGroupedAddMenu'
import AgentConfigurationCard from '@baserow_enterprise/components/agentApplication/AgentConfigurationCard'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import slackImage from '@baserow/modules/integrations/slack/assets/images/slack.svg?url'

export default {
  name: 'AgentChatChannelsSection',
  components: { AgentConfigurationCard, AgentGroupedAddMenu, ReadOnlyForm },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      // A single not-yet-persisted channel being configured; Slack requires
      // both secrets at creation time, so the row can only be POSTed once
      // they are filled in.
      draft: null,
      createLoading: false,
      deletingIds: [],
      // `${channelId}-${configKey}` of the secrets being saved.
      savingSecrets: [],
      // Local editable copies per channel id, so a save response can never
      // clobber what the user is still typing. The secret fields are always
      // seeded empty because the server only returns whether they are set.
      channelDrafts: {},
    }
  },
  computed: {
    canUpdateChannel() {
      return this.$hasPermission(
        'agent_application.update_chat_channel',
        this.application,
        this.application.workspace.id
      )
    },
    channels() {
      return this.$store.getters['agentApplication/getChannels']
    },
    agentName() {
      return (
        this.$store.getters['agentApplication/getAgent']?.name ||
        this.application.name
      )
    },
    channelMenuItems() {
      return [
        {
          id: 'chat-apps',
          label: this.$t('agentChannels.chatAppsGroup'),
          icon: 'iconoir-chat-bubble',
          iconColor: 'muted-blue',
          children: [
            {
              id: 'channel-slack',
              label: this.$t('agentChannels.slack'),
              value: 'slack',
              image: slackImage,
              description: this.$t('agentChannels.slackDescription'),
            },
          ],
        },
      ]
    },
  },
  created() {
    this.debouncedNameSaves = {}
  },
  mounted() {
    this.channels.forEach((channel) => this.ensureDraft(channel))
  },
  watch: {
    channels(channels) {
      channels.forEach((channel) => this.ensureDraft(channel))
    },
  },
  beforeUnmount() {
    Object.values(this.debouncedNameSaves).forEach((save) => save.flush())
  },
  // The channels are fetched by the page together with the triggers and
  // tools.
  methods: {
    channelTypeImage() {
      // Slack is the only channel type for now.
      return slackImage
    },
    channelTitle(channel) {
      const draftName = this.channelDrafts[channel.id]?.name
      return (draftName ?? channel.name) || this.$t('agentChannels.slack')
    },
    ensureDraft(channel) {
      if (!this.channelDrafts[channel.id]) {
        this.channelDrafts[channel.id] = {
          name: channel.name || '',
          botToken: '',
          signingSecret: '',
        }
      }
    },
    secretPlaceholder(channel, setKey, draftKey) {
      // An empty input keeps the stored secret, so show that one is saved.
      if (channel.config?.[setKey]) {
        return this.$t('agentChannels.secretSavedPlaceholder')
      }
      return draftKey === 'botToken'
        ? this.$t('agentChannels.botTokenPlaceholder')
        : this.$t('agentChannels.signingSecretPlaceholder')
    },
    onAddChannelSelect(item) {
      this.$refs.addChannelContext.hide()
      if (this.draft === null) {
        this.draft = {
          type: item.value,
          name: '',
          botToken: '',
          signingSecret: '',
        }
      }
    },
    async createChannel() {
      this.createLoading = true
      try {
        const channel = await this.$store.dispatch(
          'agentApplication/createChannel',
          {
            applicationId: this.application.id,
            values: {
              type: this.draft.type,
              name: this.draft.name,
              config: {
                bot_token: this.draft.botToken,
                signing_secret: this.draft.signingSecret,
              },
            },
          }
        )
        this.draft = null
        this.ensureDraft(channel)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.createLoading = false
      }
    },
    async onEnabledChange(channel, enabled) {
      try {
        await this.$store.dispatch('agentApplication/updateChannel', {
          channelId: channel.id,
          values: { enabled },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    async deleteChannel(channel) {
      if (this.deletingIds.includes(channel.id)) {
        return
      }
      delete this.debouncedNameSaves[channel.id]
      this.deletingIds = [...this.deletingIds, channel.id]
      try {
        await this.$store.dispatch('agentApplication/deleteChannel', {
          channelId: channel.id,
        })
        delete this.channelDrafts[channel.id]
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.deletingIds = this.deletingIds.filter((id) => id !== channel.id)
      }
    },
    onNameChanged(channel) {
      if (!this.canUpdateChannel) {
        return
      }
      if (!this.debouncedNameSaves[channel.id]) {
        this.debouncedNameSaves[channel.id] = debounce(
          () => this.saveName(channel.id),
          1000
        )
      }
      this.debouncedNameSaves[channel.id]()
    },
    async saveName(channelId) {
      const channel = this.channels.find((c) => c.id === channelId)
      const draft = this.channelDrafts[channelId]
      if (!channel || !draft || draft.name === channel.name) {
        return
      }
      try {
        await this.$store.dispatch('agentApplication/updateChannel', {
          channelId,
          values: { name: draft.name },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    async saveSecret(channel, configKey, draftKey) {
      const draft = this.channelDrafts[channel.id]
      const value = draft?.[draftKey]?.trim()
      if (!this.canUpdateChannel || !value) {
        // An empty input means "keep the stored secret".
        return
      }
      const key = `${channel.id}-${configKey}`
      if (this.savingSecrets.includes(key)) {
        return
      }
      this.savingSecrets = [...this.savingSecrets, key]
      try {
        await this.$store.dispatch('agentApplication/updateChannel', {
          channelId: channel.id,
          values: { config: { [configKey]: value } },
        })
        // The response only reports that the secret is set, so clear the
        // input back to the saved placeholder state.
        draft[draftKey] = ''
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.savingSecrets = this.savingSecrets.filter((item) => item !== key)
      }
    },
    copyEventsUrl(channel) {
      copyToClipboard(channel.events_url)
      const copied = this.$refs[`copied-${channel.id}`]
      const instance = Array.isArray(copied) ? copied[0] : copied
      instance?.show()
    },
  },
}
</script>
