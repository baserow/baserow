import aiAssistant from '@baserow_enterprise/services/aiAssistant'
import { notifyIf } from '@baserow/modules/core/utils/error'
import Vue from 'vue'

// Local storage utilities
const LAST_CHAT_KEY = 'baserow_ai_assistant_last_chat'

const saveLastChatToLocalStorage = (workspaceId, chatUid) => {
  try {
    const data = JSON.parse(localStorage.getItem(LAST_CHAT_KEY) || '{}')
    data[workspaceId] = chatUid
    localStorage.setItem(LAST_CHAT_KEY, JSON.stringify(data))
  } catch (error) {
    console.warn('Failed to save last chat to localStorage:', error)
  }
}

const getLastChatFromLocalStorage = (workspaceId) => {
  try {
    const data = JSON.parse(localStorage.getItem(LAST_CHAT_KEY) || '{}')
    return data[workspaceId] || null
  } catch (error) {
    console.warn('Failed to get last chat from localStorage:', error)
    return null
  }
}

const removeLastChatFromLocalStorage = (workspaceId, chatUid) => {
  try {
    const data = JSON.parse(localStorage.getItem(LAST_CHAT_KEY) || '{}')
    if (data[workspaceId] === chatUid) {
      delete data[workspaceId]
      localStorage.setItem(LAST_CHAT_KEY, JSON.stringify(data))
    }
  } catch (error) {
    console.warn('Failed to remove last chat from localStorage:', error)
  }
}

export const state = () => ({
  currentConversationUid: null,
  workspaceId: null,
  messages: [],
  loading: false,
  pendingActions: {},
  availableTools: [
    { id: 'navigator', name: 'Navigator', icon: 'iconoir-nav-arrow-right' },
    { id: 'create', name: 'Create', icon: 'iconoir-plus' },
    { id: 'analyze', name: 'Analyze', icon: 'iconoir-graph-up' },
    { id: 'search', name: 'Search', icon: 'iconoir-search' },
  ],
  selectedTools: ['navigator', 'create', 'analyze', 'search'],
  chats: [],
  chatsLoading: false,
})

export const mutations = {
  SET_CURRENT_CONVERSATION_UID(state, uid) {
    state.currentConversationUid = uid
  },

  SET_WORKSPACE_ID(state, workspaceId) {
    state.workspaceId = workspaceId
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
      // Use Vue.set to ensure reactivity
      state.messages.splice(messageIndex, 1, updatedMessage)
    }
  },

  SET_LOADING(state, loading) {
    state.loading = loading
  },

  SET_PENDING_ACTION(state, { actionId, data }) {
    state.pendingActions[actionId] = data
  },

  CLEAR_PENDING_ACTION(state, actionId) {
    if (actionId) {
      delete state.pendingActions[actionId]
    } else {
      state.pendingActions = {}
    }
  },

  SET_SELECTED_TOOLS(state, tools) {
    state.selectedTools = tools
  },

  TOGGLE_TOOL(state, toolId) {
    const index = state.selectedTools.indexOf(toolId)
    if (index > -1) {
      state.selectedTools.splice(index, 1)
    } else {
      state.selectedTools.push(toolId)
    }
  },

  CLEAR_MESSAGES(state) {
    state.messages = []
  },

  SET_CHATS(state, chats) {
    state.chats = chats
  },

  SET_CHATS_LOADING(state, loading) {
    state.chatsLoading = loading
  },

  REMOVE_CHAT(state, chatUid) {
    const index = state.chats.findIndex((chat) => chat.uid === chatUid)
    if (index > -1) {
      state.chats.splice(index, 1)
    }
  },

  ADD_CHAT(state, chat) {
    state.chats = [chat, ...state.chats]
  },

  UPDATE_CHAT_TITLE(state, chatTitle) {
    const chat = state.chats.find((c) => c.uid === state.currentConversationUid)
    if (chat) {
      chat.title = chatTitle
    }
  },
  SET_UNDOABLE_FLAG(state, flag) {
    const chat = state.chats.find((c) => c.uid === state.currentConversationUid)
    if (chat) {
      Vue.set(chat, 'latestActionIsUndoable', flag)
    }
  },
}

export const actions = {
  createConversation({ commit }, workspaceId) {
    const uid = aiAssistant(this.$client).generateConversationUid()
    commit('SET_CURRENT_CONVERSATION_UID', uid)
    commit('SET_WORKSPACE_ID', workspaceId)
    commit('CLEAR_MESSAGES')
    commit('ADD_CHAT', { uid, title: '' })

    // Save new conversation to localStorage
    saveLastChatToLocalStorage(workspaceId, uid)

    return uid
  },

  async sendMessage(
    { commit, state, dispatch, rootState },
    { message, context = null, actionResponse = null }
  ) {
    if (!state.currentConversationUid) {
      await dispatch('createConversation', state.workspaceId)
    }

    commit('SET_LOADING', true)

    try {
      if (!actionResponse) {
        const userMessage = {
          id: Date.now(),
          role: 'user',
          content: message,
          timestamp: new Date(),
        }
        commit('ADD_MESSAGE', userMessage)
      }

      // Use provided context or fallback to basic workspace context
      const messageContext = context || {
        type: 'workspace',
        workspace_id: state.workspaceId,
      }

      messageContext.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone

      await aiAssistant(this.$client).sendMessage(
        state.currentConversationUid,
        message,
        state.workspaceId,
        state.selectedTools,
        messageContext,
        actionResponse,
        async (progressEvent) => {
          await dispatch('handleStreamingResponse', progressEvent)
        }
      )
    } catch (error) {
      // Add error message
      const errorMessage = {
        id: Date.now(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
        loading: false,
      }
      commit('ADD_MESSAGE', errorMessage)
      notifyIf(error, 'aiAssistant')
      throw error
    } finally {
      commit('SET_LOADING', false)
    }
  },

  handleVisualizationMessage({ commit, dispatch }, message) {
    const { type, tables } = message.action.visualization
    switch (type) {
      case 'table_navigation':
        if (tables.length === 1) {
          const table = tables[0]
          // TODO: Use i18n to make it translatable
          let content = `Navigating to table [${table.name}](${table.navigation_url})...`
          if (table.view_id != null) {
            content = `Navigating to view [${table.view_name}](${table.navigation_url})...`
          }
          commit('UPDATE_MESSAGE', {
            id: message.message_id,
            updates: {
              content,
              loading: false,
              action: {
                type: 'table_navigation',
                tableId: table.id,
                databaseId: table.database_id,
                url: table.navigation_url,
              },
            },
          })
        } else {
          // Multiple tables, let the user pick the right one
          commit('UPDATE_MESSAGE', {
            id: message.message_id,
            updates: {
              content: `Multiple tables found:\n\n${message.content}\n\nPlease specify which one to navigate to or click on a link to navigate there.`,
            },
          })
        }
        // Handle table navigation (e.g., update state, trigger navigation)
        break
    }
  },

  handleStreamingResponse({ commit, dispatch }, chunk) {
    console.log('Received chunk:', chunk)
    const data = chunk.data || {}
    switch (chunk.type) {
      case 'message_start':
        commit('SET_UNDOABLE_FLAG', false)
        commit('ADD_MESSAGE', {
          id: data.message_id,
          role: 'assistant',
          content: '',
          timestamp: data.timestamp,
          loading: true,
        })
        break

      case 'content_delta':
        console.log('Content delta:', data)
        if (data.action?.message_type === 'visualization') {
          dispatch('handleVisualizationMessage', data)
        } else {
          const updates = { content: data.content }
          if (data.action?.action_group_id) {
            updates.actionGroupId = data.action.action_group_id
          }
          commit('UPDATE_MESSAGE', {
            id: data.message_id,
            updates,
          })
        }
        break

      case 'message_end':
        commit('SET_UNDOABLE_FLAG', Boolean(data.latest_action_is_undoable))
        commit('UPDATE_MESSAGE', {
          id: data.message_id,
          updates: {
            loading: false,
          },
        })
        commit('UPDATE_CHAT_TITLE', data.chat_title)
        break

      case 'error':
        commit('UPDATE_MESSAGE', {
          id: data.message_id,
          updates: {
            content: `Error: ${data.error}`,
            loading: false,
          },
        })
        break
    }
  },

  handleNavigationAction({ dispatch }, action) {
    // Handle navigation based on action type
    if (action.target_type === 'table') {
      // TODO: Implement actual navigation logic
    } else if (action.target_type === 'view') {
      // TODO: Implement actual navigation logic
    }
  },

  async confirmPendingAction({ dispatch, commit, state }, actionId) {
    const pendingAction = state.pendingActions[actionId]
    if (pendingAction) {
      await dispatch('sendMessage', {
        message: 'Confirming action',
        actionResponse: {
          type: 'confirmation',
          action_id: actionId,
          value: true,
        },
      })
      commit('CLEAR_PENDING_ACTION', actionId)
    }
  },

  async cancelPendingAction({ commit, dispatch }, actionId) {
    const cancelMessage = {
      id: Date.now(),
      role: 'assistant',
      content: 'Action cancelled.',
      timestamp: new Date(),
      loading: false,
    }
    commit('ADD_MESSAGE', cancelMessage)
    commit('CLEAR_PENDING_ACTION', actionId)
  },

  toggleTool({ commit }, toolId) {
    commit('TOGGLE_TOOL', toolId)
  },

  setSelectedTools({ commit }, tools) {
    commit('SET_SELECTED_TOOLS', tools)
  },

  async refreshMessage({ dispatch, state, commit }, message) {
    const messageIndex = state.messages.findIndex((m) => m.id === message.id)
    if (messageIndex > 0) {
      const previousMessage = state.messages[messageIndex - 1]
      if (previousMessage.role === 'user') {
        // Mark message as loading
        commit('UPDATE_MESSAGE', {
          id: message.id,
          updates: { loading: true },
        })

        try {
          await dispatch('sendMessage', { message: previousMessage.content })
        } catch (error) {
          commit('UPDATE_MESSAGE', {
            id: message.id,
            updates: { loading: false },
          })
          throw error
        }
      }
    }
  },

  async fetchChats({ commit, state }, workspaceId) {
    commit('SET_WORKSPACE_ID', workspaceId)

    commit('SET_CHATS_LOADING', true)
    try {
      const chats = await aiAssistant(this.$client).fetchChats(
        state.workspaceId
      )
      commit('SET_CHATS', chats)
    } catch (error) {
      notifyIf(error, 'aiAssistant')
      throw error
    } finally {
      commit('SET_CHATS_LOADING', false)
    }
  },

  async loadChatMessages({ commit, state }, chatUid) {
    try {
      const { messages } = await aiAssistant(this.$client).fetchChatMessages(
        chatUid
      )
      return messages
    } catch (error) {
      notifyIf(error, 'aiAssistant')
      throw error
    }
  },

  async deleteChat({ commit, state }, chatUid) {
    try {
      await aiAssistant(this.$client).deleteChat(chatUid)
      commit('REMOVE_CHAT', chatUid)

      // Remove from localStorage
      removeLastChatFromLocalStorage(state.workspaceId, chatUid)

      // If we deleted the current conversation, create a new one
      if (state.currentConversationUid === chatUid) {
        const newUid = aiAssistant(this.$client).generateConversationUid()
        commit('SET_CURRENT_CONVERSATION_UID', newUid)
        commit('CLEAR_MESSAGES')
      }
    } catch (error) {
      notifyIf(error, 'aiAssistant')
      throw error
    }
  },

  async selectChat({ commit, dispatch, state }, { chatUid, messages = null }) {
    commit('SET_CURRENT_CONVERSATION_UID', chatUid)

    // Save to local storage
    if (state.workspaceId) {
      saveLastChatToLocalStorage(state.workspaceId, chatUid)
    }

    if (messages) {
      // Use provided messages
      commit('SET_MESSAGES', messages)
    } else {
      // Load messages from backend
      try {
        const loadedMessages = await dispatch('loadChatMessages', chatUid)
        commit('SET_MESSAGES', loadedMessages)
      } catch (error) {
        // If we can't load messages, start with empty conversation
        commit('CLEAR_MESSAGES')
      }
    }
  },

  async tryRestoreLastChat({ commit, dispatch, state }) {
    if (!state.workspaceId) return null

    const lastChatUid = getLastChatFromLocalStorage(state.workspaceId)
    if (!lastChatUid) return null

    // Check if the chat still exists in the fetched chats
    const chatExists = state.chats.find((chat) => chat.uid === lastChatUid)
    if (!chatExists) {
      // Clean up localStorage if chat no longer exists
      removeLastChatFromLocalStorage(state.workspaceId, lastChatUid)
      return null
    }

    try {
      await dispatch('selectChat', { chatUid: lastChatUid })
      return lastChatUid
    } catch (error) {
      // If we can't load the chat, remove it from localStorage
      removeLastChatFromLocalStorage(state.workspaceId, lastChatUid)
      return null
    }
  },

  async undo({ commit, state }) {
    try {
      await aiAssistant(this.$client).undo(state.currentConversationUid)
    } catch (error) {
      notifyIf(error, 'aiAssistant')
      throw error
    } finally {
      commit('SET_UNDOABLE_FLAG', false)
    }
  },
}

export const getters = {
  currentConversationUid: (state) => state.currentConversationUid,

  currentChat: (state) => {
    return state.chats.find((chat) => chat.uid === state.currentConversationUid)
  },

  messages: (state) => state.messages,

  isLoading: (state) => state.loading,

  hasPendingActions: (state) => Object.keys(state.pendingActions).length > 0,

  pendingActionIds: (state) => Object.keys(state.pendingActions),

  availableTools: (state) => state.availableTools,

  selectedTools: (state) => state.selectedTools,

  isToolSelected: (state) => (toolId) => state.selectedTools.includes(toolId),

  chats: (state) => state.chats,

  chatsLoading: (state) => state.chatsLoading,

  canUndo: (state) => (message) => {
    const currentChat = state.chats.find(
      (chat) => chat.uid === state.currentConversationUid
    )
    console.log(state.messages, currentChat)
    if (!currentChat?.latestActionIsUndoable) return false

    return state.messages.at(-1).id === message.id
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
