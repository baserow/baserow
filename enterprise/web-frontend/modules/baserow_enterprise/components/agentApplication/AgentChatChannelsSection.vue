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
        :default-expanded="cardInitiallyExpanded(channel, channels)"
        :title="channelTitle(channel)"
        :image="channelType(channel).image"
        :icon="channelType(channel).icon"
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
            <component
              :is="channelType(channel).cardComponent"
              v-if="channelType(channel).cardComponent"
              :channel="channel"
              :application="application"
              :draft="channelDrafts[channel.id]"
              :can-update="canUpdateChannel"
            />
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
        :title="draft.name || channelType(draft).name"
        :image="channelType(draft).image"
        :icon="channelType(draft).icon"
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
        <component
          :is="channelType(draft).draftComponent"
          v-if="channelType(draft).draftComponent"
          :draft="draft"
          :application="application"
        />
        <div class="agent-configuration__channel-draft-actions">
          <Button
            type="primary"
            :loading="createLoading"
            :disabled="!channelType(draft).canCreate(draft)"
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
import agentCollapsibleCards from '@baserow_enterprise/mixins/agentCollapsibleCards'
import debounce from 'lodash/debounce'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AgentGroupedAddMenu from '@baserow_enterprise/components/agentApplication/AgentGroupedAddMenu'
import AgentConfigurationCard from '@baserow_enterprise/components/agentApplication/AgentConfigurationCard'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { AgentContextMixin } from '@baserow_enterprise/composables/useAgentContext'

/**
 * Lists the agent's chat channels. Everything type-specific comes from the
 * `agentChatChannel` registry: the add menu entry, the saved channel's
 * settings card and the body shown while creating one.
 */
export default {
  name: 'AgentChatChannelsSection',
  components: {
    AgentConfigurationCard,
    AgentGroupedAddMenu,
    ReadOnlyForm,
  },
  mixins: [AgentContextMixin, agentCollapsibleCards],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      // A single not-yet-persisted channel being configured.
      draft: null,
      createLoading: false,
      deletingIds: [],
      // Local editable copies per channel id, so a save response can never
      // clobber what the user is still typing.
      channelDrafts: {},
      channelSeeds: {},
    }
  },
  computed: {
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
      const groups = []
      for (const type of this.$registry.getOrderedList('agentChatChannel')) {
        let group = groups.find((g) => g.id === type.group.id)
        if (!group) {
          group = { ...type.group, children: [] }
          groups.push(group)
        }
        const available = type.isAvailable()
        group.children.push({
          id: `channel-${type.getType()}`,
          label: type.name,
          value: type.getType(),
          icon: type.icon,
          image: type.image,
          iconColor: type.iconColor,
          description: available ? type.description : type.unavailableReason,
          disabled: !available,
        })
      }
      return groups
    },
  },
  watch: {
    channels(channels) {
      channels.forEach((channel) => this.ensureDraft(channel))
    },
  },
  created() {
    this.debouncedNameSaves = {}
  },
  mounted() {
    this.channels.forEach((channel) => this.ensureDraft(channel))
  },
  beforeUnmount() {
    Object.values(this.debouncedNameSaves).forEach((save) => save.flush())
  },
  // The channels are fetched by the page together with the triggers and
  // tools.
  methods: {
    channelType(channel) {
      return this.$registry.get('agentChatChannel', channel.type)
    },
    channelTitle(channel) {
      const draftName = this.channelDrafts[channel.id]?.name
      return (draftName ?? channel.name) || this.channelType(channel).name
    },
    // A draft follows the server value (another user's edit, an undo) as
    // long as this user hasn't changed it; their own typing always wins.
    ensureDraft(channel) {
      const seed = this.channelType(channel).seedDraft(channel)
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
    onAddChannelSelect(item) {
      this.$refs.addChannelContext.hide()
      if (this.draft === null && !item.disabled) {
        this.draft = { type: item.value, name: '', config: {} }
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
              config: this.draft.config,
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
          { channelId: channel.id, values: { enabled } }
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
          { channelId: channel.id }
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
          { channelId, values: { name: draft.name } }
        )
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
