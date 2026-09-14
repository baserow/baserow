<template>
  <Context ref="context" :hide-on-click-outside="true">
    <ul class="context__menu">
      <li v-if="canUpdate" class="context__menu-item">
        <a class="context__menu-item-link" @click="togglePinned()">
          <i class="context__menu-item-icon iconoir-pin"></i>
          {{
            chat.pinned
              ? $t('agentConversationList.unpin')
              : $t('agentConversationList.pin')
          }}
        </a>
      </li>
      <li v-if="canUpdate" class="context__menu-item">
        <a class="context__menu-item-link" @click="rename()">
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('agentConversationList.rename') }}
        </a>
      </li>
      <li v-if="canDelete" class="context__menu-item">
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          :class="{ 'context__menu-item-link--loading': deleting }"
          @click="deleteChat()"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('agentConversationList.delete') }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'AgentConversationContext',
  mixins: [context],
  props: {
    application: {
      type: Object,
      required: true,
    },
    chat: {
      type: Object,
      required: true,
    },
  },
  emits: ['rename'],
  data() {
    return { deleting: false }
  },
  computed: {
    canUpdate() {
      return this.$hasPermission(
        'agent_application.update_chat',
        this.application,
        this.application.workspace.id
      )
    },
    canDelete() {
      return (
        !this.chat.status?.startsWith('in_progress') &&
        this.$hasPermission(
          'agent_application.delete_chat',
          this.application,
          this.application.workspace.id
        )
      )
    },
  },
  methods: {
    async togglePinned() {
      this.hide()
      try {
        await this.$store.dispatch('agentHistory/updateChat', {
          chatUuid: this.chat.uuid,
          values: { pinned: !this.chat.pinned },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    rename() {
      this.hide()
      this.$emit('rename')
    },
    async deleteChat() {
      if (this.deleting) {
        return
      }
      this.deleting = true
      try {
        await this.$store.dispatch('agentHistory/deleteChat', {
          chat: this.chat,
        })
        this.hide()
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.deleting = false
      }
    },
  },
}
</script>
