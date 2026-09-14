<template>
  <li
    class="agent-conversation-list__item"
    :class="{ 'agent-conversation-list__item--active': active }"
    @click="$emit('select')"
  >
    <span
      class="agent-conversation-list__item-status"
      :class="
        loading
          ? 'agent-conversation-list__item-status--loading'
          : statusModifier
      "
      :title="statusTitle"
    ></span>
    <span class="agent-conversation-list__item-title">
      <Editable
        ref="rename"
        :value="chat.title || $t('agentConversationList.untitled')"
        @change="renameChat($event)"
      ></Editable>
    </span>
    <a
      ref="menuButton"
      class="agent-conversation-list__item-menu"
      :title="$t('agentConversationList.menu')"
      @click.stop="$refs.context.toggle($refs.menuButton, 'bottom', 'right', 4)"
    >
      <i class="iconoir-more-vert"></i>
    </a>
    <AgentConversationContext
      ref="context"
      :application="application"
      :chat="chat"
      @rename="$refs.rename.edit()"
    />
  </li>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentConversationContext from '@baserow_enterprise/components/agentApplication/AgentConversationContext'

const RUNNING_STATUSES = ['in_progress', 'canceling']

export default {
  name: 'AgentConversationListItem',
  components: { AgentConversationContext },
  props: {
    application: {
      type: Object,
      required: true,
    },
    chat: {
      type: Object,
      required: true,
    },
    active: {
      type: Boolean,
      required: false,
      default: false,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['select'],
  computed: {
    statusModifier() {
      if (RUNNING_STATUSES.includes(this.chat.status)) {
        return 'agent-conversation-list__item-status--running'
      }
      return `agent-conversation-list__item-status--${this.chat.status.replace(
        '_',
        '-'
      )}`
    },
    statusTitle() {
      if (this.chat.status === 'awaiting_approval') {
        return this.$t('agentConversationList.awaitingApproval')
      }
      if (RUNNING_STATUSES.includes(this.chat.status)) {
        return this.$t('agentConversationList.running')
      }
      return null
    },
  },
  methods: {
    async renameChat({ value }) {
      const title = value.trim()
      if (title === '' || title === this.chat.title) {
        this.$refs.rename.set(this.chat.title || '')
        return
      }
      try {
        await this.$store.dispatch('agentHistory/updateChat', {
          chatUuid: this.chat.uuid,
          values: { title },
        })
      } catch (error) {
        this.$refs.rename.set(this.chat.title || '')
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
