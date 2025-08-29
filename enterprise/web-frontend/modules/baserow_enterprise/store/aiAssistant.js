import aiAssistant from '@baserow_enterprise/services/aiAssistant'
import { v4 as uuidv4 } from 'uuid'

const MESSAGE_TYPE = {
  MESSAGE: 'ai/message',
  ERROR: 'ai/error',
  CHAT_TITLE: 'chat/title',
}

export const state = () => ({
  currentChatId: null,
  messages: [],
  loadingMessage: false,
  chats: [],
  loadingChats: false,
})

export const mutations = {
  SET_CURRENT_CHAT_ID(state, id) {
    state.currentChatId = id
  },

  SET_MESSAGES(state, messages) {
    state.messages = messages
  },

  ADD_MESSAGE(state, message) {
    state.messages.push(message)
  },

  UPDATE_MESSAGE(state, { id, updates }) {
    const messageIndex = state.messages.findIndex((m) => m.id === id)
    if (messageIndex !== -1) {
      const updatedMessage = {
        ...state.messages[messageIndex],
        ...updates,
      }
      state.messages.splice(messageIndex, 1, updatedMessage)
    }
  },

  SET_LOADING_MESSAGE(state, loading) {
    state.loadingMessage = loading
  },

  CLEAR_MESSAGES(state) {
    state.messages = []
  },

  SET_CHATS(state, chats) {
    state.chats = chats.map((chat) => ({
      id: chat.uuid,
      title: chat.title,
      createdAt: chat.created_on,
      updatedAt: chat.updated_on,
      status: chat.status,
    }))
  },

  SET_CHATS_LOADING(state, loading) {
    state.loadingChats = loading
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
}

export const actions = {
  createChat({ commit }) {
    const id = uuidv4()
    commit('ADD_CHAT', { id, title: '' })
    commit('CLEAR_MESSAGES')
    commit('SET_CURRENT_CHAT_ID', id)

    return id
  },

  async selectChat({ commit }, chat) {
    commit('CLEAR_MESSAGES')
    commit('SET_CURRENT_CHAT_ID', chat.id)

    commit('SET_LOADING_MESSAGE', false)
    try {
      const { messages } = await aiAssistant(this.$client).fetchChatMessages(
        chat.id
      )
      commit('SET_MESSAGES', messages)
    } finally {
      commit('SET_LOADING_MESSAGE', false)
    }
  },

  clearChat({ commit }) {
    commit('CLEAR_MESSAGES')
    commit('SET_CURRENT_CHAT_ID', null)
  },

  async fetchChats({ commit }, workspaceId) {
    commit('SET_CHATS_LOADING', true)

    try {
      const { results: chats } = await aiAssistant(this.$client).fetchChats(
        workspaceId
      )
      commit('SET_CHATS', chats)
    } finally {
      commit('SET_CHATS_LOADING', false)
    }
  },

  handleStreamingResponse({ commit, state }, { id, update }) {
    switch (update.type) {
      case MESSAGE_TYPE.MESSAGE:
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            content: update.content,
            loading: false,
          },
        })
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
          },
        })
        break
    }
  },

  async sendMessage({ commit, state, dispatch }, { message, workspace }) {
    if (!state.currentChatId) {
      await dispatch('createChat', workspace.id)
    }

    const userMessage = {
      id: uuidv4(),
      role: 'human',
      content: message,
      loading: false,
    }
    commit('ADD_MESSAGE', userMessage)
    const aiMessageId = uuidv4()
    const aiMessage = {
      id: aiMessageId,
      role: 'ai',
      content: '',
      loading: true,
    }
    commit('ADD_MESSAGE', aiMessage)
    commit('SET_LOADING_MESSAGE', true)
    const uiContext = { workspace: { id: workspace.id, name: workspace.name } }

    try {
      await aiAssistant(this.$client).sendMessage(
        state.currentChatId,
        message,
        uiContext,
        async (progressEvent) => {
          await dispatch('handleStreamingResponse', {
            id: aiMessageId,
            update: progressEvent,
          })
        }
      )
    } catch (error) {
      commit('UPDATE_MESSAGE', {
        id: aiMessageId,
        updates: {
          content: 'Oops! Something went wrong on the server...',
          loading: false,
        },
      })
      throw error
    } finally {
      commit('SET_LOADING_MESSAGE', false)
    }
  },
}

export const getters = {
  currentChatId: (state) => state.currentChatId,

  currentChat: (state) => {
    return state.chats.find((chat) => chat.id === state.currentChatId)
  },

  messages: (state) => state.messages,

  isLoadingMessage: (state) => state.loadingMessage,

  chats: (state) => state.chats,

  isLoadingChats: (state) => state.loadingChats,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
