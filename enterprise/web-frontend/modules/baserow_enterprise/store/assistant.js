import assistant from '@baserow_enterprise/services/assistant'
import { v4 as uuidv4 } from 'uuid'
import Vue from 'vue'

const MESSAGE_TYPE = {
  MESSAGE: 'ai/message', // The main AI message content, both for partial and final answers
  THINKING: 'ai/thinking', // Update the status bar in the UI
  REASONING: 'ai/reasoning', // Show reasoning steps before the final answer
  NAVIGATION: 'ai/navigation', // Navigate the user to a specific location in the UI
  ERROR: 'ai/error', // Show an error message
  CHAT_TITLE: 'chat/title', // Update the chat title
  AI_STARTED: 'ai/started', // Indicates the AI started generating a response
  AI_CANCELLED: 'ai/cancelled', // Indicates the AI generation was cancelled
}

export const state = () => ({
  currentChatId: null,
  messages: [],
  chats: [],
  isLoadingChats: false,
  uiLocation: null,
})

export const mutations = {
  SET_CURRENT_CHAT_ID(state, id) {
    state.currentChatId = id
  },

  SET_CHAT_LOADING(state, { chat, value }) {
    Vue.set(chat, 'loading', value)
  },

  SET_ASSISTANT_RUNNING(state, { chat, value }) {
    Vue.set(chat, 'running', value)
  },

  SET_ASSISTANT_RUNNING_MESSAGE(state, { chat, message = '' }) {
    Vue.set(chat, 'runningMessage', message)
  },

  SET_ASSISTANT_CANCELLING(state, { chat, value }) {
    Vue.set(chat, 'cancelling', value)
  },

  SET_MESSAGES(state, messages) {
    state.messages = messages
  },

  ADD_MESSAGE(state, message) {
    state.messages.push(message)
  },

  UPDATE_MESSAGE(state, { id, updates }) {
    const messageIndex = state.messages.findIndex(
      (m) => m.id === id || m._uuid === id
    )
    if (messageIndex !== -1) {
      const updatedMessage = {
        ...state.messages[messageIndex],
        ...updates,
      }
      state.messages.splice(messageIndex, 1, updatedMessage)
    }
  },

  CLEAR_MESSAGES(state) {
    state.messages = []
  },

  SET_CURRENT_MESSAGE_ID(state, { chat, messageId }) {
    Vue.set(chat, 'currentMessageId', messageId)
  },

  SET_CHATS(state, chats) {
    state.chats = chats.map((chat) => ({
      id: chat.uuid,
      title: chat.title,
      createdAt: chat.created_on,
      updatedAt: chat.updated_on,
      status: chat.status,
      loading: false,
      running: false,
      reasoning: false,
      cancelling: false,
      currentMessageId: null,
    }))
  },

  SET_CHATS_LOADING(state, loading) {
    state.isLoadingChats = loading
  },

  REMOVE_CHAT(state, chatId) {
    const index = state.chats.findIndex((chat) => chat.uid === chatId)
    if (index > -1) {
      state.chats.splice(index, 1)
    }
  },

  ADD_CHAT(state, chat) {
    state.chats = [chat, ...state.chats]
  },

  UPDATE_CHAT(state, { id, updates }) {
    const chat = state.chats.find((c) => c.id === id)
    if (chat) {
      Object.assign(chat, updates)
    }
  },

  SET_UI_LOCATION(state, location) {
    state.uiLocation = location || null
  },
}

export const actions = {
  reset({ commit }) {
    commit('CLEAR_MESSAGES')
    commit('SET_CURRENT_CHAT_ID', null)
    commit('SET_CHATS', [])
  },

  createChat({ commit }) {
    const id = uuidv4()
    commit('ADD_CHAT', { id, title: '' })
    commit('CLEAR_MESSAGES')
    commit('SET_CURRENT_CHAT_ID', id)

    return id
  },

  async selectChat({ commit }, chat) {
    commit('SET_CHAT_LOADING', { chat, value: true })

    // Set role and loading state for each message
    const parseMessage = (msg) => ({
      role: msg.type === 'human' ? 'human' : 'ai',
      loading: false,
      ...msg,
    })

    try {
      const { messages } = await assistant(this.$client).fetchChatMessages(
        chat.id
      )
      commit('SET_CURRENT_CHAT_ID', chat.id)
      commit('SET_MESSAGES', messages.map(parseMessage))
    } finally {
      commit('SET_CHAT_LOADING', { chat, value: false })
    }
  },

  clearChat({ commit }) {
    commit('CLEAR_MESSAGES')
    commit('SET_CURRENT_CHAT_ID', null)
  },

  async fetchChats({ commit }, workspaceId) {
    commit('SET_CHATS_LOADING', true)

    try {
      const { results: chats } = await assistant(this.$client).fetchChats(
        workspaceId
      )
      commit('SET_CHATS', chats)
    } finally {
      commit('SET_CHATS_LOADING', false)
    }
  },

  handleStreamingResponse({ commit, state }, { chat, id, update }) {
    switch (update.type) {
      case MESSAGE_TYPE.AI_STARTED:
        commit('SET_CURRENT_MESSAGE_ID', { chat, messageId: update.message_id })
        break
      case MESSAGE_TYPE.AI_CANCELLED:
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            content: this.$i18n.t('assistant.messageCancelled'),
            loading: false,
            error: false,
            reasoning: false,
            cancelled: true,
          },
        })
        commit('SET_ASSISTANT_CANCELLING', { chat, value: false })
        commit('SET_ASSISTANT_RUNNING', { chat, value: false })
        commit('SET_CURRENT_MESSAGE_ID', { chat, messageId: null })
        break
      case MESSAGE_TYPE.MESSAGE:
        commit('SET_ASSISTANT_RUNNING_MESSAGE', {
          chat,
          message: this.$i18n.t('assistant.statusAnswering'),
        })
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            id: update.id || id,
            content: update.content,
            sources: update.sources,
            can_submit_feedback: update.can_submit_feedback,
            loading: false,
            reasoning: false,
          },
        })
        break
      case MESSAGE_TYPE.REASONING:
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            id: update.id || id,
            content: update.content,
            can_submit_feedback: false,
            loading: false,
            reasoning: true,
          },
        })
        break
      case MESSAGE_TYPE.THINKING:
        commit('SET_ASSISTANT_RUNNING_MESSAGE', {
          chat,
          message: update.content,
        })
        break
      case MESSAGE_TYPE.NAVIGATION:
        commit('SET_UI_LOCATION', update.location)
        break
      case MESSAGE_TYPE.CHAT_TITLE:
        commit('UPDATE_CHAT', {
          id: state.currentChatId,
          updates: { title: update.content },
        })
        break
      case MESSAGE_TYPE.ERROR:
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            content: update.content,
            loading: false,
            error: true,
            reasoning: false,
            can_submit_feedback: false,
          },
        })
        break
    }
  },

  async sendMessage(
    { commit, state, dispatch, getters },
    { message, workspace }
  ) {
    if (!state.currentChatId) {
      await dispatch('createChat', workspace.id)
    }
    const chat = state.chats.find((c) => c.id === state.currentChatId)

    const userMessage = {
      id: uuidv4(),
      role: 'human',
      content: message,
      loading: false,
    }
    commit('ADD_MESSAGE', userMessage)
    const aiMessageId = uuidv4()
    const aiMessage = {
      _uuid: aiMessageId,
      id: aiMessageId, // Temporary ID, will be updated when the final message arrives
      role: 'ai',
      content: '',
      loading: true,
      reasoning: false,
    }
    commit('ADD_MESSAGE', aiMessage)
    commit('SET_ASSISTANT_RUNNING', { chat, value: true })
    commit('SET_ASSISTANT_RUNNING_MESSAGE', {
      chat,
      message: this.$i18n.t('assistant.statusThinking'),
    })
    const uiContext = getters.uiContext

    try {
      await assistant(this.$client).sendMessage(
        state.currentChatId,
        message,
        uiContext,
        async (progressEvent) => {
          await dispatch('handleStreamingResponse', {
            chat,
            id: aiMessageId,
            update: progressEvent,
          })
        }
      )
      // If the AI message was never updated but the request finished, set a generic error message.
      if (
        state.messages.find((m) => m.id === aiMessageId && m.content === '')
      ) {
        throw new Error('The assistant did not provide a response.')
      }
    } catch (error) {
      // Don't show error if the request was cancelled by user
      if (error.cancelled) {
        return
      }
      commit('UPDATE_MESSAGE', {
        id: aiMessageId,
        updates: {
          content:
            error.data?.detail ||
            error.message ||
            'Oops! Something went wrong on the server. Please try again.',
          loading: false,
          error: true,
          reasoning: false,
        },
      })
    } finally {
      commit('SET_ASSISTANT_RUNNING', { chat, value: false })
      commit('SET_CURRENT_MESSAGE_ID', { chat, messageId: null })
    }
  },

  async cancelMessage({ commit, state }) {
    if (!state.currentChatId) {
      return
    }

    const chat = state.chats.find((c) => c.id === state.currentChatId)
    if (!chat || !chat.running) {
      return
    }

    commit('SET_ASSISTANT_CANCELLING', { chat, value: true })
    commit('SET_ASSISTANT_RUNNING_MESSAGE', {
      chat,
      message: this.$i18n.t('assistant.statusCancelling'),
    })

    try {
      await assistant(this.$client).cancelMessage(state.currentChatId)
    } catch (error) {
      commit('SET_ASSISTANT_CANCELLING', { chat, value: false })
      commit('SET_ASSISTANT_RUNNING', { chat, value: false })
      commit('SET_CURRENT_MESSAGE_ID', { chat, messageId: null })
    }
  },

  async submitFeedback({ commit, state }, { messageId, sentiment, feedback }) {
    const message = state.messages.find((m) => m.id === messageId)
    if (!message) {
      return
    }

    const originalSentiment = message.human_sentiment
    // Optimistically update the message with the new sentiment
    commit('UPDATE_MESSAGE', {
      id: messageId,
      updates: {
        human_sentiment: sentiment,
      },
    })

    try {
      await assistant(this.$client).submitFeedback(
        message.id,
        sentiment,
        feedback?.trim()
      )
    } catch (error) {
      // Revert the optimistic update
      commit('UPDATE_MESSAGE', {
        id: messageId,
        updates: {
          human_sentiment: originalSentiment,
        },
      })
      throw error
    }
  },
}

export const getters = {
  currentChatId: (state) => state.currentChatId,

  currentChat: (state) => {
    return state.chats.find((chat) => chat.id === state.currentChatId)
  },

  messages: (state) => state.messages,

  chats: (state) => state.chats,

  isLoadingChats: (state) => state.isLoadingChats,

  uiContext: (state, getters, rootState, rootGetters) => {
    const scope = rootGetters['undoRedo/getCurrentScope']
    const workspace = rootGetters['workspace/get'](scope.workspace)

    const application = scope.application
      ? rootGetters['application/get'](scope.application)
      : null

    const table =
      application?.type === 'database' && scope.table
        ? application.tables?.find((t) => t.id === scope.table)
        : null

    const view =
      table && scope.view ? rootGetters['view/get'](scope.view) : null

    const uiContext = {
      applicationType: application?.type || null,
      workspace: { id: workspace.id, name: workspace.name },
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    }

    if (application) {
      const appType =
        application.type === 'builder' ? 'application' : application.type
      uiContext[appType] = {
        id: application.id,
        name: application.name,
      }
    }
    if (table) {
      uiContext.table = { id: table.id, name: table.name }
    }
    if (view) {
      uiContext.view = { id: view.id, name: view.name, type: view.type }
    }

    try {
      const workflow =
        application?.type === 'automation' && scope.workflow
          ? rootGetters['automationWorkflow/getById'](
              application,
              scope.workflow
            )
          : null
      if (workflow) {
        uiContext.workflow = { id: workflow.id, name: workflow.name }
      }
    } catch {}
    return uiContext
  },

  uiLocation: (state) => {
    return state.uiLocation
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
