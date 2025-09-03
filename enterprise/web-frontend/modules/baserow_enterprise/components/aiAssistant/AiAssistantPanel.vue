<template>
  <div class="ai-assistant">
    <div class="ai-assistant__header">
      <a
        v-if="messages.length"
        :title="$t('aiAssistantPanel.back')"
        class="ai-assistant__header-icon"
        @click.prevent="clearChat"
      >
        <i class="iconoir-nav-arrow-left"></i>
      </a>
      <div class="ai-assistant__title">
        <i class="iconoir-sparks"></i>
        <span v-if="!currentChatTitle">{{ $t('aiAssistantPanel.title') }}</span>
        <span v-else>{{ currentChatTitle }}</span>
      </div>
      <div class="ai-assistant__header-actions">
        <AiAssistantChatHistoryContext
          ref="chatHistory"
          :current-chat-id="currentChatId"
          :chats="chats"
          :loading="isLoadingChats"
          @select-chat="selectAndCloseChat($event)"
        />
        <a
          v-if="chats.length"
          ref="chatHistoryButton"
          :title="$t('aiAssistantPanel.history')"
          class="ai-assistant__header-icon"
          @click.prevent="toggleChatHistoryContext"
          ><i class="iconoir-clock-rotate-right"></i
        ></a>
        <div v-if="chats.length" class="ai-assistant__header-separator"></div>
        <a
          :title="$t('aiAssistantPanel.close')"
          class="ai-assistant__header-icon"
          @click.prevent="$bus.$emit('toggle-right-sidebar')"
          ><i class="iconoir-cancel"></i
        ></a>
      </div>
    </div>
    <div ref="scrollContainer" class="ai-assistant__content">
      <AiAssistantWelcomeMessage
        v-if="!currentChatId"
        :name="user.first_name"
      ></AiAssistantWelcomeMessage>
      <AiAssistantMessageList
        v-else
        :messages="messages"
        @scroll-to-bottom="scrollToBottom"
      ></AiAssistantMessageList>
    </div>
    <div class="ai-assistant__footer">
      <AiAssistantInputMessage
        :context-display="workspace.name"
        :loading="isLoadingMessage"
        @send-message="handleSendMessage"
      ></AiAssistantInputMessage>
    </div>
  </div>
</template>

<script>
import AiAssistantWelcomeMessage from '@baserow_enterprise/components/aiAssistant/AiAssistantWelcomeMessage'
import AiAssistantInputMessage from '@baserow_enterprise/components/aiAssistant/AiAssistantInputMessage'
import AiAssistantMessageList from '@baserow_enterprise/components/aiAssistant/AiAssistantMessageList'
import AiAssistantChatHistoryContext from './AiAssistantChatHistoryContext'
import { mapGetters, mapActions } from 'vuex'

export default {
  name: 'AiAssistantPanel',
  components: {
    AiAssistantWelcomeMessage,
    AiAssistantInputMessage,
    AiAssistantMessageList,
    AiAssistantChatHistoryContext,
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
      messages: 'aiAssistant/messages',
      isLoadingMessage: 'aiAssistant/isLoadingMessage',
      currentChatId: 'aiAssistant/currentChatId',
      currentChat: 'aiAssistant/currentChat',
      chats: 'aiAssistant/chats',
      isLoadingChats: 'aiAssistant/isLoadingChats',
    }),
    currentChatTitle() {
      return this.currentChat?.title
    },
  },
  watch: {
    workspace: {
      handler(newWorkspace) {
        this.fetchChats(newWorkspace.id)
      },
      immediate: true,
    },
  },
  mounted() {
    const container = this.$refs.scrollContainer
    let isUserScrolling = false

    // Detect user scroll
    container.addEventListener('scroll', () => {
      const atBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight <
        5
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
      sendMessage: 'aiAssistant/sendMessage',
      createChat: 'aiAssistant/createChat',
      selectChat: 'aiAssistant/selectChat',
      clearChat: 'aiAssistant/clearChat',
      fetchChats: 'aiAssistant/fetchChats',
    }),

    async handleSendMessage(text) {
      const message = text
      if (!message || this.loading) return

      try {
        await this.sendMessage({
          message,
          workspace: this.workspace,
        })
      } catch (error) {
        console.trace(error)
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
    scrollToBottom() {
      this.$nextTick(() => {
        const el = this.$refs.scrollContainer
        if (el) el.scrollTop = el.scrollHeight
      })
    },
  },
}
</script>
