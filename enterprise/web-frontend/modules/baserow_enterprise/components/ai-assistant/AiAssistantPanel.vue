<template>
  <div class="ai-assistant">
    <div class="ai-assistant__header">
      <div class="ai-assistant__header-title">
        <ButtonIcon
          v-if="currentConversationUid"
          :style="{ border: 'none', boxShadow: 'none', marginRight: '8px' }"
          icon="iconoir-arrow-left"
          :title="$t('aiAssistantPanel.backToChats', 'Back to chats')"
          @click="clearConversation"
        />
        <i class="ai-assistant__header-icon iconoir-sparks"></i>
        <h3 class="ai-assistant__header-text">
          {{ $t('aiAssistantPanel.title', 'AI Assistant') }}
        </h3>
      </div>
      <div class="ai-assistant__header-actions">
        <!-- Chat History Dropdown -->
        <div class="ai-assistant__history-dropdown-wrapper">
          <ButtonIcon
            ref="historyButton"
            :style="{ border: 'none', boxShadow: 'none', marginRight: '8px' }"
            icon="iconoir-clock-rotate-right"
            :title="$t('aiAssistantPanel.recentChats', 'Recent chats')"
            @click="toggleHistoryDropdown"
          />

          <AiAssistantHistoryContext
            ref="history"
            :chats="chats"
            :loading="chatsLoading"
            @select-chat="selectConversationFromDropdown"
          />
        </div>

        <ButtonIcon
          :style="{ border: 'none', boxShadow: 'none' }"
          icon="iconoir-cancel"
          @click="$emit('close')"
        />
      </div>
    </div>

    <div class="ai-assistant__messages">
      <!-- Main content area -->
      <div ref="messagesContainer" class="ai-assistant__main-content">
        <!-- Welcome state when no conversation selected -->
        <AiAssistantWelcomeState
          v-if="!currentConversationUid"
          :user-first-name="userFirstName"
          :suggestions="suggestions"
          @send-message="sendMessage"
        />

        <!-- Messages or loading state when conversation exists -->
        <template v-else>
          <!-- Loading state while fetching messages -->
          <div
            v-if="messagesLoading && !messages?.length"
            class="ai-assistant__loading"
          >
            <i class="iconoir-system-restart ai-assistant__loading-icon"></i>
            <p class="ai-assistant__loading-text">Loading conversation...</p>
          </div>

          <!-- Messages list -->
          <AiAssistantMessageList
            v-else
            :messages="messages"
            @confirm-action="confirmPendingAction"
            @cancel-action="cancelPendingAction"
            @like-message="likeMessage"
            @dislike-message="dislikeMessage"
            @copy-message="copyMessage"
            @undo="undo"
            @table-navigation-done="tableNavigationDone"
          />
        </template>
      </div>
    </div>

    <!-- Input section at bottom (always visible) -->
    <AiAssistantInputSection
      :has-context="hasContext"
      :context-display="contextDisplay"
      :placeholder="
        $t(
          'aiAssistantPanel.placeholder',
          messages?.length
            ? 'Type your message...'
            : 'Ask me anything about your data...'
        )
      "
      :loading="loading"
      @send-message="sendMessage"
    />
  </div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import Button from '@baserow/modules/core/components/Button'
import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'
import AiAssistantWelcomeState from './AiAssistantWelcomeState'
import AiAssistantMessageList from './AiAssistantMessageList'
import AiAssistantInputSection from './AiAssistantInputSection'
import AiAssistantHistoryContext from './AiAssistantHistoryContext'

export default {
  name: 'AiAssistantPanel',
  components: {
    Button,
    ButtonIcon,
    AiAssistantWelcomeState,
    AiAssistantMessageList,
    AiAssistantInputSection,
    AiAssistantHistoryContext,
  },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    context: {
      type: Object,
      default: () => ({
        table: null,
        view: null,
        field: null,
      }),
    },
  },
  data() {
    return {
      messagesLoading: false,
      suggestions: [
        {
          id: 1,
          label: 'Create another view',
          text: 'Help me create a new view for my data',
          icon: 'iconoir-view-grid',
          description: 'Display your data in a different layout',
        },
        {
          id: 2,
          label: 'Filter rows in this view',
          text: 'Help me filter the data in this view',
          icon: 'iconoir-filter',
          description: 'Show only the rows that match your criteria',
        },
        {
          id: 3,
          label: 'Sort rows in the view',
          text: 'Help me sort the data in this view',
          icon: 'iconoir-sort',
          description: 'Reorder rows based on selected fields',
        },
      ],
    }
  },
  computed: {
    ...mapGetters({
      user: 'auth/getUserObject',
      messages: 'aiAssistant/messages',
      isLoading: 'aiAssistant/isLoading',
      hasPendingActions: 'aiAssistant/hasPendingActions',
      availableTools: 'aiAssistant/availableTools',
      selectedTools: 'aiAssistant/selectedTools',
      isToolSelected: 'aiAssistant/isToolSelected',
      currentConversationUid: 'aiAssistant/currentConversationUid',
      getCurrentScope: 'undoRedo/getCurrentScope',
      chats: 'aiAssistant/chats',
      chatsLoading: 'aiAssistant/chatsLoading',
    }),
    hasContext() {
      // Always show context section for now to debug
      return true
    },
    loading() {
      return this.isLoading
    },
    userFirstName() {
      if (this.user && this.user.first_name) {
        return this.user.first_name
      }
      return 'there'
    },
    contextDisplay() {
      // Get the current scope from undoRedo store
      const scope = this.getCurrentScope || {}

      // Show context based on priority: view > table > application > workspace
      if (scope.view) {
        // For views, show: table_name - view_name
        const view = this.$store.getters['view/get'](scope.view)
        if (view) {
          const table = this.$store.getters['table/getSelected']
          if (table && table.id === view.table_id) {
            return `${table.name} - ${view.name}`
          }
          return view.name
        }
      } else if (scope.table) {
        // For tables, show: table_name
        const table = this.$store.getters['table/getSelected']
        if (table && table.id === scope.table) {
          return table.name
        }
      } else if (scope.application) {
        // For applications/databases, show: application_name
        const application = this.$store.getters['application/get'](
          scope.application
        )
        if (application) {
          return application.name
        }
      } else if (scope.workspace) {
        // For workspaces, show: workspace_name
        const workspace = this.$store.getters['workspace/get'](scope.workspace)
        if (workspace) {
          return workspace.name
        }
        return `Workspace ${scope.workspace}`
      } else if (this.workspace) {
        // Fallback to workspace prop
        return this.workspace.name
      }

      return ''
    },
    contextData() {
      // Get the current scope from undoRedo store
      const scope = this.getCurrentScope || {}

      // Build context object based on what's available
      let context = {}

      // Determine type and build appropriate context
      if (scope.view || scope.table) {
        // Database context when we have view or table
        context.type = 'database'

        if (scope.application) {
          context.database_id = scope.application
        }

        if (scope.table) {
          context.table_id = scope.table

          // If we have a table but no database_id, try to get it from the table
          if (!context.database_id) {
            const table = this.$store.getters['table/getSelected']
            if (table && table.id === scope.table && table.database_id) {
              context.database_id = table.database_id
            }
          }
        }

        if (scope.view) {
          context.view_id = scope.view

          // If we have a view but no table_id, try to get it from the view
          if (!context.table_id) {
            const view = this.$store.getters['view/get'](scope.view)
            if (view && view.table_id) {
              context.table_id = view.table_id

              // Also try to get database_id from the table if not set
              if (!context.database_id) {
                const table = this.$store.getters['table/getSelected']
                if (table && view.table_id === table.id && table.database_id) {
                  context.database_id = table.database_id
                }
              }
            }
          }
        }
      } else {
        // Workspace context as fallback
        context.type = 'workspace'

        if (scope.workspace) {
          context.workspace_id = scope.workspace
        } else if (this.workspace) {
          context.workspace_id = this.workspace.id
        }
      }

      return context
    },
  },
  watch: {
    messages: {
      handler(newMessages) {
        // Scroll to bottom when messages change
        if (newMessages && newMessages.length > 0) {
          this.$nextTick(() => {
            this.scrollToBottom()
          })
        }
      },
      deep: true,
    },
    workspace: {
      handler(newWorkspace) {
        this.fetchChats(newWorkspace.id)
      },
      immediate: true,
    },
  },
  methods: {
    ...mapActions('aiAssistant', {
      createConversation: 'createConversation',
      sendMessageToStore: 'sendMessage',
      confirmPendingActionStore: 'confirmPendingAction',
      cancelPendingActionStore: 'cancelPendingAction',
      toggleToolStore: 'toggleTool',
      refreshMessageStore: 'refreshMessage',
      fetchChats: 'fetchChats',
      selectChat: 'selectChat',
      deleteChat: 'deleteChat',
    }),
    likeMessage(message) {
      // TODO: Implement like functionality
      // this.$toast.info('Feedback recorded: Liked')
    },
    dislikeMessage(message) {
      // TODO: Implement dislike functionality
      // this.$toast.info('Feedback recorded: Disliked')
    },
    copyMessage(message) {
      navigator.clipboard.writeText(message.content)
      // this.$toast.success(
      //   this.$t('aiAssistantPanel.copied', 'Copied to clipboard')
      // )
    },
    async undo() {
      try {
        await this.$store.dispatch('aiAssistant/undo')
      } catch (error) {
        notifyIf(error, 'aiAssistant')
      }
    },
    async refreshMessage(message) {
      try {
        await this.refreshMessageStore(message)
      } catch (error) {
        notifyIf(error, 'aiAssistant')
      }
    },
    async tableNavigationDone() {
      try {
        await this.sendMessageToStore({
          message: 'navigation done',
          context: this.contextData,
          actionResponse: {
            type: 'confirmation',
            action_id: '1',
            value: true,
          },
        })
      } catch (error) {
        notifyIf(error, 'aiAssistant')
      }
    },
    async sendMessage(text) {
      const message = text
      if (!message || this.loading) return

      try {
        await this.sendMessageToStore({
          message,
          context: this.contextData,
        })
      } catch (error) {
        notifyIf(error, 'aiAssistant')
      }
    },
    async confirmPendingAction(actionId) {
      await this.confirmPendingActionStore(actionId)
    },

    async cancelPendingAction(actionId) {
      await this.cancelPendingActionStore(actionId)
    },
    scrollToBottom() {
      const container = this.$refs.messagesContainer
      if (container) {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'instant',
        })
      }
    },
    toggleTool(toolId) {
      this.toggleToolStore(toolId)
    },

    async selectConversation(chat) {
      try {
        this.messagesLoading = true
        await this.selectChat({ chatUid: chat.uid })
        // Scroll to bottom after messages are loaded
        this.$nextTick(() => {
          this.scrollToBottom()
        })
      } catch (error) {
        console.log('Failed to load conversation')
      } finally {
        this.messagesLoading = false
      }
    },

    async deleteConversation(chat) {
      if (confirm(`Are you sure you want to delete "${chat.title}"?`)) {
        try {
          await this.deleteChat(chat.uid)
        } catch (error) {
          console.error('Failed to delete conversation:', error)
        }
      }
    },

    clearConversation() {
      // Clear current conversation and go back to welcome state
      this.$store.commit('aiAssistant/CLEAR_MESSAGES')
      this.$store.commit('aiAssistant/SET_CURRENT_CONVERSATION_UID', null)
    },

    // History dropdown methods
    toggleHistoryDropdown() {
      this.$refs.history.toggle(
        this.$refs.historyButton.$el,
        'bottom',
        'left',
        4
      )
    },

    async selectConversationFromDropdown(chat) {
      await this.selectConversation(chat)
      this.$refs.history.hide()
    },

    async handleDeleteChatFromDropdown(chat) {
      await this.deleteConversation(chat)
    },
  },
}
</script>
