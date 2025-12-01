<template>
  <div class="assistant">
    <div class="assistant__header">
      <a
        v-if="messages.length"
        :title="$t('assistantPanel.back')"
        class="assistant__header-icon"
        @click.prevent="clearChat"
      >
        <i class="iconoir-nav-arrow-left"></i>
      </a>
      <div class="assistant__title">
        <i class="iconoir-sparks"></i>
        <span v-if="!currentChatTitle">{{ $t('assistantPanel.title') }}</span>
        <span v-else>{{ currentChatTitle }}</span>
      </div>
      <div class="assistant__header-actions">
        <AssistantChatHistoryContext
          ref="chatHistory"
          :current-chat-id="currentChatId"
          :chats="chats"
          :loading="isLoadingChats"
          @select-chat="selectAndCloseChat($event)"
        />
        <a
          ref="chatHistoryButton"
          :title="$t('assistantPanel.history')"
          class="assistant__header-icon"
          @click.prevent="toggleChatHistoryContext"
          ><i class="iconoir-clock-rotate-right"></i
        ></a>
        <div class="assistant__header-separator"></div>
        <a
          :title="$t('assistantPanel.close')"
          class="assistant__header-icon"
          @click.prevent="$bus.$emit('toggle-right-sidebar')"
          ><i class="iconoir-cancel"></i
        ></a>
      </div>
    </div>
    <div ref="scrollContainer" class="assistant__content">
      <AssistantMessageList
        v-if="currentChatId"
        :messages="messages"
      ></AssistantMessageList>
      <AssistantWelcomeMessage
        v-else
        :name="user.first_name"
        :ui-context="uiContext"
        @prompt="$refs.message.setCurrentMessage($event)"
      ></AssistantWelcomeMessage>
    </div>
    <div class="assistant__footer">
      <AssistantInputMessage
        ref="message"
        :ui-context="uiContext"
        :is-running="isAssistantRunning"
        :is-cancelling="isAssistantCancelling"
        :running-message="assistantRunningMessage"
        @send-message="handleSendMessage"
        @cancel-message="handleCancelMessage"
      ></AssistantInputMessage>
    </div>
  </div>
</template>

<script>
import AssistantWelcomeMessage from '@baserow_enterprise/components/assistant/AssistantWelcomeMessage'
import AssistantInputMessage from '@baserow_enterprise/components/assistant/AssistantInputMessage'
import AssistantMessageList from '@baserow_enterprise/components/assistant/AssistantMessageList'
import AssistantChatHistoryContext from './AssistantChatHistoryContext'
import { mapGetters, mapActions } from 'vuex'
import { waitFor } from '@baserow/modules/core/utils/queue'

export default {
  name: 'AssistantPanel',
  components: {
    AssistantWelcomeMessage,
    AssistantInputMessage,
    AssistantMessageList,
    AssistantChatHistoryContext,
  },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    ...mapGetters({
      user: 'auth/getUserObject',
      messages: 'assistant/messages',
      currentChat: 'assistant/currentChat',
      chats: 'assistant/chats',
      isLoadingChats: 'assistant/isLoadingChats',
      uiContext: 'assistant/uiContext',
      uiLocation: 'assistant/uiLocation',
    }),
    currentChatId() {
      return this.currentChat?.id
    },
    currentChatTitle() {
      return this.currentChat?.title
    },
    isAssistantRunning() {
      return Boolean(this.currentChat?.running)
    },
    isAssistantCancelling() {
      return Boolean(this.currentChat?.cancelling)
    },
    assistantRunningMessage() {
      return this.currentChat?.runningMessage || ''
    },
  },
  watch: {
    workspace: {
      handler(newWorkspace) {
        this.resetStore()
        this.fetchChats(newWorkspace.id)
      },
      immediate: true,
    },
    isAssistantRunning(newVal) {
      if (newVal) {
        // bring the new response into view
        this.$nextTick(() => {
          const container = this.$refs.scrollContainer
          container.scrollTop = container.scrollHeight
        })
      }
    },
    uiLocation: {
      handler(newLocation) {
        if (!newLocation) return

        if (newLocation.type === 'database-view') {
          // Don't navigate to deactivated views
          const viewType = this.$registry.get('view', newLocation.view_type)
          if (!viewType || viewType.isDeactivated(this.workspace.id)) {
            return
          }
        }

        const router = this.$router
        const store = this.$store
        if (
          newLocation.type === 'database-table' ||
          newLocation.type === 'database-view'
        ) {
          waitFor(() => {
            const database = store.getters['application/get'](
              newLocation.database_id
            )

            const isCurrentlyOnTable =
              this.$route.name === 'database-table' &&
              parseInt(this.$route.params.tableId) ===
                parseInt(newLocation.table_id)

            const tableLoaded =
              database &&
              database.tables.find((table) => table.id === newLocation.table_id)
            const viewLoaded = store.getters['view/get'](newLocation.view_id)
            return (
              tableLoaded &&
              (!isCurrentlyOnTable || !newLocation.view_id || viewLoaded)
            )
          }).then(() => {
            router.push({
              name: 'database-table',
              params: {
                workspaceId: this.workspace.id,
                databaseId: newLocation.database_id,
                tableId: newLocation.table_id,
                viewId: newLocation.view_id,
              },
            })
          })
        } else if (newLocation.type === 'workspace') {
          this.$router.push({
            name: 'workspace',
            params: {
              workspaceId: this.workspace.id,
            },
          })
        } else if (newLocation.type === 'automation-workflow') {
          waitFor(() => {
            const automation = store.getters['application/get'](
              newLocation.automation_id
            )

            return (
              automation &&
              automation.workflows.find(
                (workflow) => workflow.id === newLocation.workflow_id
              )
            )
          }).then(() => {
            this.$router.push({
              name: 'automation-workflow',
              params: {
                automationId: newLocation.automation_id,
                workflowId: newLocation.workflow_id,
              },
            })
          })
        }
      },
    },
  },
  mounted() {
    const container = this.$refs.scrollContainer
    let isUserScrolling = false

    // Detect user scroll
    container.addEventListener('scroll', () => {
      const atBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight <
        30
      isUserScrolling = !atBottom
    })

    // Watch for DOM changes
    const observer = new MutationObserver(() => {
      if (!isUserScrolling) {
        container.scrollTop = container.scrollHeight
      }
    })

    observer.observe(container, {
      childList: true,
      subtree: true,
    })

    // Store for cleanup
    this.scrollObserver = observer
  },

  beforeDestroy() {
    if (this.scrollObserver) {
      this.scrollObserver.disconnect()
    }
  },
  methods: {
    ...mapActions({
      sendMessage: 'assistant/sendMessage',
      cancelMessage: 'assistant/cancelMessage',
      createChat: 'assistant/createChat',
      selectChat: 'assistant/selectChat',
      clearChat: 'assistant/clearChat',
      fetchChats: 'assistant/fetchChats',
      resetStore: 'assistant/reset',
    }),

    async handleSendMessage(text) {
      const message = text
      if (!message || this.loading) return

      await this.sendMessage({
        message,
        workspace: this.workspace,
      })
    },

    async handleCancelMessage() {
      await this.cancelMessage()
    },

    toggleChatHistoryContext() {
      this.$refs.chatHistory.toggle(
        this.$refs.chatHistoryButton,
        'bottom',
        'left',
        10,
        4
      )
    },
    async selectAndCloseChat(chat) {
      await this.selectChat(chat)
      this.$refs.chatHistory.hide()
    },
  },
}
</script>
