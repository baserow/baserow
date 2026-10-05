import PublicAgentChatService from '@baserow_enterprise/services/publicAgentChat'

/**
 * One visitor's conversation on the public web chat page. Realtime events
 * arrive already filtered by the backend (answers and status only); polling
 * the transcript covers a missed or unavailable websocket.
 */
export const state = () => ({
  slug: null,
  token: null,
  info: null,
  conversationUuid: null,
  messages: [],
  // idle | working | waiting_for_approval | error
  status: 'idle',
  // The answer being streamed, shown before the final message arrives.
  partial: '',
  sending: false,
})

export const mutations = {
  SET_CHAT(state, { slug, token, info }) {
    state.slug = slug
    state.token = token
    state.info = info
  },
  SET_CONVERSATION(state, { uuid, messages, status }) {
    state.conversationUuid = uuid
    state.messages = messages
    state.status = status
    state.partial = ''
  },
  SET_MESSAGES(state, messages) {
    state.messages = messages
  },
  ADD_MESSAGE(state, message) {
    state.messages.push(message)
  },
  SET_MESSAGE_ID(state, { key, id }) {
    const message = state.messages.find((item) => item.key === key)
    if (message) {
      message.id = id
    }
  },
  SET_STATUS(state, status) {
    state.status = status
  },
  SET_PARTIAL(state, partial) {
    state.partial = partial
  },
  SET_SENDING(state, sending) {
    state.sending = sending
  },
}

const messageKey = (message) => `m-${message.id}`

export const actions = {
  async load({ commit }, { slug, token }) {
    const { data } = await PublicAgentChatService(this.$client).get(slug, token)
    commit('SET_CHAT', { slug, token, info: data })
  },
  async startConversation({ commit, state }) {
    const { data } = await PublicAgentChatService(
      this.$client
    ).createConversation(state.slug, state.token)
    commit('SET_CONVERSATION', {
      uuid: data.uuid,
      messages: [],
      status: data.status,
    })
  },
  async sendMessage({ commit, state }, content) {
    const key = `local-${Date.now()}`
    commit('ADD_MESSAGE', { key, id: null, role: 'human', content })
    commit('SET_SENDING', true)
    commit('SET_STATUS', 'working')
    commit('SET_PARTIAL', '')
    try {
      const { data } = await PublicAgentChatService(this.$client).sendMessage(
        state.slug,
        state.conversationUuid,
        content,
        state.token
      )
      commit('SET_MESSAGE_ID', { key, id: data.message_id })
    } catch (error) {
      commit('SET_STATUS', 'idle')
      commit(
        'SET_MESSAGES',
        state.messages.filter((message) => message.key !== key)
      )
      throw error
    } finally {
      commit('SET_SENDING', false)
    }
  },
  /**
   * Replaces the local view with the server transcript. Used by the polling
   * fallback, so a lost websocket event never leaves the page stuck.
   */
  async refresh({ commit, state }) {
    if (!state.conversationUuid) {
      return
    }
    const { data } = await PublicAgentChatService(this.$client).getConversation(
      state.slug,
      state.conversationUuid,
      state.token
    )
    commit(
      'SET_MESSAGES',
      data.messages.map((message) => ({ ...message, key: messageKey(message) }))
    )
    if (data.status !== 'working') {
      commit('SET_PARTIAL', '')
    }
    commit('SET_STATUS', data.status)
  },
  handleEvent({ commit, state }, event) {
    switch (event.type) {
      case 'ai/started':
        commit('SET_PARTIAL', '')
        commit('SET_STATUS', 'working')
        break
      case 'ai/answer_chunk':
        // Chunks carry the whole answer so far, not a delta.
        commit('SET_PARTIAL', event.content || '')
        break
      case 'ai/message': {
        // The transcript poll may already hold this answer, and a run can
        // emit the final message more than once; never show it twice.
        const last = state.messages[state.messages.length - 1]
        const duplicate =
          last?.role === 'ai' &&
          ((event.id && last.id === event.id) || last.content === event.content)
        if (event.content && !duplicate) {
          commit('ADD_MESSAGE', {
            key: messageKey(event),
            id: event.id,
            role: 'ai',
            content: event.content,
          })
        }
        commit('SET_PARTIAL', '')
        break
      }
      case 'ai/error':
        commit('SET_PARTIAL', '')
        commit('SET_STATUS', 'error')
        break
      case 'ai/cancelled':
        commit('SET_PARTIAL', '')
        commit('SET_STATUS', 'idle')
        break
    }
  },
  handleStatus({ commit }, status) {
    commit('SET_STATUS', status)
  },
}

export const getters = {
  getInfo: (state) => state.info,
  getSlug: (state) => state.slug,
  getToken: (state) => state.token,
  getConversationUuid: (state) => state.conversationUuid,
  getMessages: (state) => state.messages,
  getStatus: (state) => state.status,
  getPartial: (state) => state.partial,
  isSending: (state) => state.sending,
  isBusy: (state) =>
    state.sending ||
    state.status === 'working' ||
    state.status === 'waiting_for_approval',
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
