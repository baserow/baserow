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
        :running="isAssistantRunning"
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
import { notifyIf } from '@baserow/modules/core/utils/error'
import { provideNow } from '@baserow/modules/core/composables/useNow'
import { RUN_STATUS } from '@baserow/modules/core/chatRuns/constants'
import { SEND_OUTCOME } from '@baserow_enterprise/store/assistant'
import { navigateToAssistantLocation } from '@baserow_enterprise/utils/assistantNavigation'

const WAITING_FOR_WORKER_AFTER_MS = 3000

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
      const follower = this.activeFollower
      return Boolean(
        this.currentChat?.cancelling ||
        follower?.stopRequested ||
        follower?.view.cancelRequested
      )
    },
    assistantRunningMessage() {
      const follower = this.activeFollower
      if (!follower) {
        return ''
      }
      if (follower.stopRequested || follower.view.cancelRequested) {
        return this.$t('assistant.statusStopping')
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
      if (follower.view.answering) {
        return this.$t('assistant.statusAnswering')
      }
      return follower.view.progress || this.$t('assistant.statusThinking')
    },
  },
  watch: {
    workspace: {
      async handler(newWorkspace) {
        this.resetStore()
        // The selected workspace is an empty object once it goes away.
        if (newWorkspace.id === undefined) return
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
      handler(location) {
        if (!location) return
        const workspaceId = this.workspace.id
        const chatId = this.currentChatId
        // Loading may outlive this panel, chat, workspace or navigation event.
        const isCurrent = () =>
          this.$store.getters['assistant/isPanelOpen'] &&
          this.workspace.id === workspaceId &&
          this.currentChatId === chatId &&
          this.uiLocation === location
        navigateToAssistantLocation(
          this,
          workspaceId,
          location,
          isCurrent
        ).catch(notifyIf)
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

    // Hidden thinking text can change without growing its capped preview.
    let previousHeight = container.scrollHeight
    const observer = new MutationObserver(() => {
      const height = container.scrollHeight
      if (height === previousHeight) return
      previousHeight = height
      if (!isUserScrolling) {
        container.scrollTop = height
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
     * its own so it doesn't continue whatever was on screen before. The running
     * answer keeps going in its own chat.
     */
    async sendPendingPrompt(prompt) {
      const workspace = this.workspace
      await this.setPendingPrompt(null)
      if (this.workspace.id !== workspace.id) return
      await this.clearChat()
      this.$refs.message.focus()
      await this.sendMessage({ message: prompt, workspace })
    },

    async handleSendMessage(text) {
      if (!text) return

      const outcome = await this.sendMessage({
        message: text,
        workspace: this.workspace,
      })
      if (outcome === SEND_OUTCOME.BUSY) {
        this.$refs.message?.setCurrentMessage(text)
      }
    },

    async handleCancelMessage() {
      try {
        await this.cancelMessage()
      } catch (error) {
        notifyIf(error)
      }
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
