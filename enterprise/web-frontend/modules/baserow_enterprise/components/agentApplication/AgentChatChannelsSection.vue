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
        :icon="channelTypeIcon(channel)"
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
            <template v-if="channel.type === 'slack'">
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
              <FormGroup
                small-label
                :label="$t('agentChannels.manifestLabel')"
                :helper-text="$t('agentChannels.manifestHelp')"
                class="margin-bottom-2"
              >
                <Button
                  type="secondary"
                  icon="iconoir-download"
                  @click="downloadManifest(channel)"
                >
                  {{ $t('agentChannels.downloadManifest') }}
                </Button>
              </FormGroup>
              <div class="agent-configuration__hint">
                {{ $t('agentChannels.activeHint') }}
              </div>
              <AgentSlackSetupSteps created />
            </template>
            <template
              v-else-if="channel.type === 'web' || channel.type === 'website'"
            >
              <FormGroup
                v-if="channel.type === 'website'"
                small-label
                :label="$t('agentChannels.embedCodeLabel')"
                :helper-text="$t('agentChannels.embedCodeHelp')"
                class="margin-bottom-2"
              >
                <div class="agent-configuration__channel-url">
                  <pre class="agent-configuration__channel-url-box">{{
                    embedCode(channel)
                  }}</pre>
                  <a
                    class="agent-configuration__channel-url-copy"
                    :title="$t('agentChannels.copyCode')"
                    @click="copyText(channel, embedCode(channel))"
                  >
                    <i class="iconoir-copy"></i>
                    <Copied :ref="`copied-${channel.id}`"></Copied>
                  </a>
                </div>
                <a
                  class="agent-configuration__channel-preview-link"
                  :href="publicUrl(channel)"
                  target="_blank"
                  rel="noopener"
                >
                  <i class="iconoir-open-new-window"></i>
                  {{ $t('agentChannels.previewChat') }}
                </a>
              </FormGroup>
              <FormGroup
                v-if="channel.type === 'web'"
                small-label
                :label="$t('agentChannels.publicLinkLabel')"
                :helper-text="$t('agentChannels.publicLinkHelp')"
                class="margin-bottom-2"
              >
                <div class="agent-configuration__channel-url">
                  <div class="agent-configuration__channel-url-box">
                    {{ publicUrl(channel) }}
                  </div>
                  <a
                    class="agent-configuration__channel-url-copy"
                    :title="$t('agentChannels.copyUrl')"
                    @click="copyPublicUrl(channel)"
                  >
                    <i class="iconoir-copy"></i>
                    <Copied :ref="`copied-${channel.id}`"></Copied>
                  </a>
                </div>
                <ButtonText
                  v-if="canUpdateChannel"
                  icon="iconoir-refresh"
                  class="margin-top-1"
                  @click="askRotateLink(channel)"
                >
                  {{ $t('agentChannels.rotateLink') }}
                </ButtonText>
              </FormGroup>
              <div
                v-if="channel.type === 'web'"
                class="agent-configuration__switch-row agent-configuration__switch-row--plain"
              >
                <i class="agent-configuration__switch-icon iconoir-lock"></i>
                <div class="agent-configuration__switch-text">
                  <div class="agent-configuration__switch-title">
                    {{ $t('agentChannels.passwordProtected') }}
                  </div>
                  <div class="agent-configuration__switch-description">
                    {{ $t('agentChannels.passwordProtectedDescription') }}
                  </div>
                </div>
                <SwitchInput
                  small
                  :value="!!channel.config.has_password"
                  :disabled="!canUpdateChannel"
                  @input="onPasswordToggle(channel, $event)"
                ></SwitchInput>
              </div>
              <FormGroup
                small-label
                :label="$t('agentChannels.titleLabel')"
                class="margin-bottom-2 margin-top-2"
              >
                <FormInput
                  v-model="channelDrafts[channel.id].title"
                  :disabled="!canUpdateChannel"
                  :placeholder="agentName"
                  @input="onWebConfigChanged(channel)"
                ></FormInput>
              </FormGroup>
              <FormGroup
                small-label
                :label="$t('agentChannels.welcomeTextLabel')"
                :helper-text="$t('agentChannels.welcomeTextHelp')"
                class="margin-bottom-2"
              >
                <FormTextarea
                  v-model="channelDrafts[channel.id].welcomeText"
                  :rows="3"
                  :disabled="!canUpdateChannel"
                  :placeholder="$t('agentChannels.welcomeTextPlaceholder')"
                  @input="onWebConfigChanged(channel)"
                ></FormTextarea>
              </FormGroup>
              <template v-if="channel.type === 'website'">
                <FormGroup
                  small-label
                  :label="$t('agentChannels.buttonTextLabel')"
                  class="margin-bottom-2"
                >
                  <FormInput
                    v-model="channelDrafts[channel.id].buttonText"
                    :disabled="!canUpdateChannel"
                    :placeholder="$t('agentChannels.buttonTextPlaceholder')"
                    @input="onWebConfigChanged(channel)"
                  ></FormInput>
                </FormGroup>
                <div class="agent-configuration__field-row margin-bottom-2">
                  <FormGroup
                    small-label
                    :label="$t('agentChannels.buttonColorLabel')"
                  >
                    <ColorInput
                      v-model="channelDrafts[channel.id].buttonColor"
                      small
                      :allow-opacity="false"
                      :disabled="!canUpdateChannel"
                      @update:model-value="onWebConfigChanged(channel)"
                    ></ColorInput>
                  </FormGroup>
                  <FormGroup
                    small-label
                    :label="$t('agentChannels.buttonPositionLabel')"
                  >
                    <Dropdown
                      v-model="channelDrafts[channel.id].buttonPosition"
                      :show-search="false"
                      :fixed-items="true"
                      :disabled="!canUpdateChannel"
                      @update:model-value="onWebConfigChanged(channel)"
                    >
                      <DropdownItem
                        v-for="option in buttonPositions"
                        :key="option.value"
                        :name="option.name"
                        :value="option.value"
                      />
                    </Dropdown>
                  </FormGroup>
                </div>
              </template>
              <div class="agent-configuration__hint">
                {{
                  channel.type === 'website'
                    ? $t('agentChannels.websiteHint')
                    : $t('agentChannels.webHint')
                }}
              </div>
            </template>
          </ReadOnlyForm>
        </template>
        <template v-if="canDeleteChannel" #footer>
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
        :title="draft.name || channelTypeName(draft)"
        :image="channelTypeImage(draft)"
        :icon="channelTypeIcon(draft)"
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
        <template v-if="draft.type === 'slack'">
          <div class="agent-configuration__hint margin-bottom-2">
            {{ $t('agentChannels.slackCreateHint') }}
          </div>
          <AgentSlackSetupSteps />
        </template>
        <div v-else class="agent-configuration__hint margin-bottom-2">
          {{
            draft.type === 'website'
              ? $t('agentChannels.websiteCreateHint')
              : $t('agentChannels.webCreateHint')
          }}
        </div>
        <div class="agent-configuration__channel-draft-actions">
          <Button
            type="primary"
            :loading="createLoading"
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
    <Modal ref="rotateModal" small>
      <h2 class="box__title">{{ $t('agentChannels.rotateLinkTitle') }}</h2>
      <p>{{ $t('agentChannels.rotateLinkText') }}</p>
      <div class="actions actions--right actions--gap margin-bottom-0">
        <Button type="secondary" @click="$refs.rotateModal.hide()">
          {{ $t('agentChannels.cancel') }}
        </Button>
        <Button type="danger" :loading="rotating" @click="rotateLink">
          {{ $t('agentChannels.rotateLinkConfirm') }}
        </Button>
      </div>
    </Modal>
    <Modal ref="passwordModal" small @hidden="passwordDraft = ''">
      <h2 class="box__title">{{ $t('agentChannels.passwordTitle') }}</h2>
      <form @submit.prevent="savePassword">
        <FormGroup
          small-label
          :label="$t('agentChannels.passwordLabel')"
          required
          class="margin-bottom-2"
        >
          <FormInput
            ref="passwordInput"
            v-model="passwordDraft"
            type="password"
            :placeholder="$t('agentChannels.passwordPlaceholder')"
          ></FormInput>
        </FormGroup>
        <div class="actions actions--right actions--gap margin-bottom-0">
          <Button tag="a" type="secondary" @click="$refs.passwordModal.hide()">
            {{ $t('agentChannels.cancel') }}
          </Button>
          <Button
            type="primary"
            :loading="savingPassword"
            :disabled="passwordDraft.trim() === ''"
          >
            {{ $t('agentChannels.passwordSave') }}
          </Button>
        </div>
      </form>
    </Modal>
    <template v-if="canUpdateChannel">
      <Context
        ref="addChannelContext"
        class="agent-configuration__add-context"
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
import AgentSlackSetupSteps from '@baserow_enterprise/components/agentApplication/AgentSlackSetupSteps'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { downloadJson } from '@baserow_enterprise/utils/download'
import slackImage from '@baserow/modules/integrations/slack/assets/images/slack.svg?url'
import { AgentContextMixin } from '@baserow_enterprise/composables/useAgentContext'

const BUTTON_POSITIONS = [
  'bottom-right',
  'bottom-left',
  'top-right',
  'top-left',
]

export default {
  name: 'AgentChatChannelsSection',
  mixins: [AgentContextMixin],
  components: {
    AgentConfigurationCard,
    AgentGroupedAddMenu,
    AgentSlackSetupSteps,
    ReadOnlyForm,
  },
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
      // The channel whose link is being replaced / password set, for the
      // shared modals.
      rotateChannel: null,
      rotating: false,
      passwordChannel: null,
      passwordDraft: '',
      savingPassword: false,
      // `${channelId}-${configKey}` of the secrets being saved.
      savingSecrets: [],
      // Local editable copies per channel id, so a save response can never
      // clobber what the user is still typing. The secret fields are always
      // seeded empty because the server only returns whether they are set.
      channelDrafts: {},
      channelSeeds: {},
    }
  },
  computed: {
    buttonPositions() {
      return BUTTON_POSITIONS.map((value) => ({
        value,
        name: this.$t(`agentChannels.position_${value}`),
      }))
    },
    canUpdateChannel() {
      return this.hasAgentPermission(
        'agent_application.update_chat_channel',
        this.application,
        this.application.workspace.id
      )
    },
    canDeleteChannel() {
      return this.hasAgentPermission(
        'agent_application.delete_chat_channel',
        this.application,
        this.application.workspace.id
      )
    },
    channels() {
      return this.$store.getters[
        `${this.storePrefix}agentApplication/getChannels`
      ]
    },
    agentName() {
      return (
        this.$store.getters[`${this.storePrefix}agentApplication/getAgent`]
          ?.name || this.application.name
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
              id: 'channel-web',
              label: this.$t('agentChannels.web'),
              value: 'web',
              icon: 'iconoir-globe',
              iconColor: 'muted-blue',
              description: this.$t('agentChannels.webDescription'),
            },
            {
              id: 'channel-website',
              label: this.$t('agentChannels.website'),
              value: 'website',
              icon: 'iconoir-code',
              iconColor: 'muted-blue',
              description: this.$t('agentChannels.websiteDescription'),
            },
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
    this.debouncedConfigSaves = {}
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
    Object.values(this.debouncedConfigSaves).forEach((save) => save.flush())
  },
  // The channels are fetched by the page together with the triggers and
  // tools.
  methods: {
    channelTypeImage(channel) {
      return channel.type === 'slack' ? slackImage : ''
    },
    channelTitle(channel) {
      const draftName = this.channelDrafts[channel.id]?.name
      return (draftName ?? channel.name) || this.$t('agentChannels.slack')
    },
    seedFor(channel) {
      return {
        name: channel.name || '',
        botToken: '',
        signingSecret: '',
        title: channel.config?.title || '',
        welcomeText: channel.config?.welcome_text || '',
        buttonText: channel.config?.button_text || '',
        buttonColor: channel.config?.button_color || '#5190ef',
        buttonPosition: channel.config?.button_position || 'bottom-right',
      }
    },
    // A draft follows the server value (another user's edit, an undo) as
    // long as this user hasn't changed it; their own typing always wins.
    ensureDraft(channel) {
      const seed = this.seedFor(channel)
      const serialized = JSON.stringify(seed)
      const draft = this.channelDrafts[channel.id]
      const untouched =
        draft === undefined ||
        JSON.stringify(draft) === this.channelSeeds[channel.id]
      if (untouched && serialized !== this.channelSeeds[channel.id]) {
        this.channelDrafts[channel.id] = seed
      }
      this.channelSeeds[channel.id] = serialized
    },
    channelTypeName(channel) {
      return this.$t(`agentChannels.${channel.type}`)
    },
    channelTypeIcon(channel) {
      return (
        { web: 'iconoir-globe', website: 'iconoir-code' }[channel.type] || ''
      )
    },
    embedCode(channel) {
      // Split so the closing tag can't end this component's own script
      // block when the template is compiled.
      return (
        `<script src="${channel.config.embed_script_url}" async></scr` + `ipt>`
      )
    },
    publicUrl(channel) {
      return (
        this.$config.public.baserowEmbeddedShareUrl +
        this.$router.resolve({
          name: 'agent-public-chat',
          params: { slug: channel.config.slug },
        }).href
      )
    },
    copyPublicUrl(channel) {
      copyToClipboard(this.publicUrl(channel))
      this.$refs[`copied-${channel.id}`]?.[0]?.show()
    },
    askRotateLink(channel) {
      this.rotateChannel = channel
      this.$refs.rotateModal.show()
    },
    async rotateLink() {
      if (!this.rotateChannel) {
        return
      }
      this.rotating = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/rotateChannelSlug`,
          {
            channelId: this.rotateChannel.id,
          }
        )
        this.$refs.rotateModal.hide()
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.rotating = false
      }
    },
    async onPasswordToggle(channel, enabled) {
      if (enabled) {
        this.passwordChannel = channel
        this.$refs.passwordModal.show()
        this.$nextTick(() => this.$refs.passwordInput?.focus())
        return
      }
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateChannel`,
          {
            channelId: channel.id,
            values: { config: { password: '' } },
          }
        )
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    async savePassword() {
      if (!this.passwordChannel || this.passwordDraft.trim() === '') {
        return
      }
      this.savingPassword = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateChannel`,
          {
            channelId: this.passwordChannel.id,
            values: { config: { password: this.passwordDraft } },
          }
        )
        this.$refs.passwordModal.hide()
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.savingPassword = false
      }
    },
    onWebConfigChanged(channel) {
      if (!this.canUpdateChannel) {
        return
      }
      if (!this.debouncedConfigSaves[channel.id]) {
        this.debouncedConfigSaves[channel.id] = debounce(
          () => this.saveWebConfig(channel.id),
          1000
        )
      }
      this.debouncedConfigSaves[channel.id]()
    },
    async saveWebConfig(channelId) {
      const channel = this.channels.find((c) => c.id === channelId)
      const draft = this.channelDrafts[channelId]
      if (!channel || !draft) {
        return
      }
      const values = { title: draft.title, welcome_text: draft.welcomeText }
      if (channel.type === 'website') {
        values.button_text = draft.buttonText
        values.button_color = draft.buttonColor
        values.button_position = draft.buttonPosition
      }
      const unchanged = Object.entries(values).every(
        ([key, value]) => value === (channel.config?.[key] || '')
      )
      if (unchanged) {
        return
      }
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateChannel`,
          {
            channelId,
            values: { config: values },
          }
        )
      } catch (error) {
        notifyIf(error, 'application')
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
        this.draft = { type: item.value, name: '' }
      }
    },
    async createChannel() {
      this.createLoading = true
      try {
        const channel = await this.$store.dispatch(
          `${this.storePrefix}agentApplication/createChannel`,
          {
            applicationId: this.application.id,
            values: {
              type: this.draft.type,
              name: this.draft.name,
              config: {},
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
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateChannel`,
          {
            channelId: channel.id,
            values: { enabled },
          }
        )
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
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/deleteChannel`,
          {
            channelId: channel.id,
          }
        )
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
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateChannel`,
          {
            channelId,
            values: { name: draft.name },
          }
        )
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
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateChannel`,
          {
            channelId: channel.id,
            values: { config: { [configKey]: value } },
          }
        )
        // The response only reports that the secret is set, so clear the
        // input back to the saved placeholder state.
        draft[draftKey] = ''
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.savingSecrets = this.savingSecrets.filter((item) => item !== key)
      }
    },
    downloadManifest(channel) {
      const name = (channel.name || this.application.name || 'slack-app')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
      downloadJson(channel.manifest, `${name}-slack-manifest.json`)
    },
    copyText(channel, text) {
      copyToClipboard(text)
      const copied = this.$refs[`copied-${channel.id}`]
      const instance = Array.isArray(copied) ? copied[0] : copied
      instance?.show()
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
