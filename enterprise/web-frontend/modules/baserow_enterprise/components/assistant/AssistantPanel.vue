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
import ApplicationService from '@baserow/modules/core/services/application'
import { provideNow } from '@baserow/modules/core/composables/useNow'
import { RUN_STATUS } from '@baserow/modules/core/chatRuns/constants'
import { SEND_OUTCOME } from '@baserow_enterprise/store/assistant'
import { usesBackgroundRuns } from '@baserow_enterprise/utils/assistant'

const WAITING_FOR_WORKER_AFTER_MS = 3000
const BROADCAST_WAIT_MS = 3000
const READY_WAIT_MS = 10000

export default {
  name: 'AssistantPanel',
  emits: ['toggle-right-sidebar'],
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
  setup() {
    return { now: provideNow(1000) }
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
      activeFollower: 'assistant/activeFollower',
      chats: 'assistant/chats',
      isLoadingChats: 'assistant/isLoadingChats',
      pendingPrompt: 'assistant/pendingPrompt',
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
      return Boolean(this.currentChat?.running || this.activeFollower)
    },
    isAssistantCancelling() {
      return Boolean(this.currentChat?.cancelling)
    },
    assistantRunningMessage() {
      const follower = this.activeFollower
      if (!follower) {
        return this.currentChat?.runningMessage || ''
      }
      if (follower.replayUnavailable || !follower.streaming) {
        return this.$t('assistant.statusWaitingForOutput')
      }
      // Unknown before the first catch-up, and every run queues for a moment.
      if (
        follower.cursor &&
        follower.view.status === RUN_STATUS.QUEUED &&
        this.now - follower.followedAt >= WAITING_FOR_WORKER_AFTER_MS
      ) {
        return this.$t('assistant.statusWaitingForWorker')
      }
      return follower.view.progress || this.$t('assistant.statusThinking')
    },
  },
  watch: {
    workspace: {
      async handler(newWorkspace) {
        this.resetStore()
        await this.fetchChats(newWorkspace.id)
        // The user can have switched workspaces again while the chats loaded.
        if (this.workspace.id === newWorkspace.id) {
          await this.restoreOpenChat()
        }
      },
      immediate: true,
    },
    // Declared after the workspace watcher, so the reset above has already run
    // when a prompt is waiting for the panel to open.
    pendingPrompt: {
      handler(prompt) {
        if (prompt) {
          this.sendPendingPrompt(prompt)
        }
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

        const store = this.$store
        if (
          newLocation.type === 'database-table' ||
          newLocation.type === 'database-view'
        ) {
          this.navigateOnceLoaded({
            applicationId: newLocation.database_id,
            findTarget: (database) =>
              database.tables.find(
                (table) => table.id === newLocation.table_id
              ),
            addTarget: (database, table) =>
              store.dispatch('table/forceUpsert', { database, data: table }),
            isReady: () => {
              const isCurrentlyOnTable =
                this.$route.name === 'database-table' &&
                parseInt(this.$route.params.tableId) ===
                  parseInt(newLocation.table_id)
              return (
                !isCurrentlyOnTable ||
                !newLocation.view_id ||
                store.getters['view/get'](newLocation.view_id)
              )
            },
            route: {
              name: 'database-table',
              params: {
                workspaceId: this.workspace.id,
                databaseId: newLocation.database_id,
                tableId: newLocation.table_id,
                viewId: newLocation.view_id,
              },
            },
          })
        } else if (newLocation.type === 'workspace') {
          this.$router.push({
            name: 'workspace',
            params: {
              workspaceId: this.workspace.id,
            },
          })
        } else if (newLocation.type === 'builder-page') {
          this.navigateOnceLoaded({
            applicationId: newLocation.application_id,
            findTarget: (builder) =>
              builder.pages.find((page) => page.id === newLocation.page_id),
            addTarget: (builder, page) =>
              store.dispatch('page/forceCreate', { builder, page }),
            route: {
              name: 'builder-page',
              params: {
                builderId: newLocation.application_id,
                pageId: newLocation.page_id,
              },
            },
          })
        } else if (newLocation.type === 'automation-workflow') {
          this.navigateOnceLoaded({
            applicationId: newLocation.automation_id,
            findTarget: (automation) =>
              automation.workflows.find(
                (workflow) => workflow.id === newLocation.workflow_id
              ),
            addTarget: (automation, workflow) =>
              store.dispatch('automationWorkflow/forceCreate', {
                automation,
                workflow,
              }),
            route: {
              name: 'automation-workflow',
              params: {
                automationId: newLocation.automation_id,
                workflowId: newLocation.workflow_id,
              },
            },
          })
        }
      },
    },
  },
  mounted() {
    this.setPanelOpen(true)
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

  beforeUnmount() {
    this.setPanelOpen(false)
    if (this.scrollObserver) {
      this.scrollObserver.disconnect()
    }
  },
  methods: {
    /**
     * Opens what Kuma just created once the store has it. The realtime
     * broadcast usually adds it within a moment; when it is late, for example
     * because a single Celery process is busy running Kuma, the application is
     * fetched instead.
     *
     * @param {object} target
     * @param {number} target.applicationId The application holding the target.
     * @param {function(object): object|undefined} target.findTarget Finds the
     *   table, page or workflow in an application, in the store or as fetched.
     * @param {function(object, object): Promise} target.addTarget Adds the
     *   fetched target to the application in the store.
     * @param {function(): boolean} [target.isReady] Any other condition the
     *   route needs.
     * @param {object} target.route Where to navigate.
     */
    async navigateOnceLoaded({
      applicationId,
      findTarget,
      addTarget,
      isReady = () => true,
      route,
    }) {
      const findStoredTarget = () => {
        const application =
          this.$store.getters['application/get'](applicationId)
        return application && findTarget(application)
      }
      try {
        await waitFor(findStoredTarget, 5, BROADCAST_WAIT_MS)
      } catch {
        try {
          await this.loadNavigationTarget(applicationId, findTarget, addTarget)
        } catch {
          return
        }
        if (!findStoredTarget()) {
          return
        }
      }
      try {
        // A new view only arrives through its broadcast, so it keeps the longer wait.
        await waitFor(isReady, 5, READY_WAIT_MS)
      } catch {
        return
      }
      this.$router.push(route)
    },
    /**
     * Adds only the missing target so the application keeps its selected state.
     */
    async loadNavigationTarget(applicationId, findTarget, addTarget) {
      const { data } = await ApplicationService(this.$client).get(applicationId)
      const application = this.$store.getters['application/get'](applicationId)
      if (!application) {
        await this.$store.dispatch('application/forceCreate', data)
        return
      }
      const target = findTarget(data)
      if (target && !findTarget(application)) {
        await addTarget(application, target)
      }
    },
    ...mapActions({
      sendMessage: 'assistant/sendMessage',
      cancelMessage: 'assistant/cancelMessage',
      createChat: 'assistant/createChat',
      selectChat: 'assistant/selectChat',
      clearChat: 'assistant/clearChat',
      fetchChats: 'assistant/fetchChats',
      resetStore: 'assistant/reset',
      setPendingPrompt: 'assistant/setPendingPrompt',
      setPanelOpen: 'assistant/setPanelOpen',
      restoreOpenChat: 'assistant/restoreOpenChat',
    }),

    /**
     * Sends a message that was typed somewhere else, always in a conversation of
     * its own so it doesn't continue whatever was on screen before. With
     * background runs the running answer keeps going in its own chat.
     */
    async sendPendingPrompt(prompt) {
      const workspace = this.workspace
      await this.setPendingPrompt(null)
      if (!usesBackgroundRuns(this)) {
        // A streamed reply would keep updating the conversation this prompt starts.
        await this.cancelMessage()
      }
      // The user can have left the prompt's workspace while the steps above ran.
      if (this.workspace.id !== workspace.id) {
        return
      }
      await this.clearChat()
      this.$refs.message.focus()
      await this.sendMessage({ message: prompt, workspace })
    },

    async handleSendMessage(text) {
      if (!text || this.loading) return

      const outcome = await this.sendMessage({
        message: text,
        workspace: this.workspace,
      })
      if (outcome === SEND_OUTCOME.BUSY) {
        this.$refs.message?.setCurrentMessage(text)
      }
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
